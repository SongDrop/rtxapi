#!/bin/bash
set -euo pipefail

# -----------------------------
# Usage / Argument Parsing
# -----------------------------
usage() {
    echo "Usage: $0 -d DOMAIN -e ADMIN_EMAIL -p ADMIN_PASSWORD [-P PORT] [-v VOLUME_DIR] [-w WEBHOOK_URL] [-l LOCATION] [-r RESOURCE_GROUP]"
    exit 1
}

# Defaults
PORT=8080
VOLUME_DIR="/opt/code-server"
WEBHOOK_URL=""
LOCATION=""
RESOURCE_GROUP=""

while getopts "d:e:p:P:v:w:l:r:" opt; do
    case "$opt" in
        d) DOMAIN="$OPTARG" ;;
        e) ADMIN_EMAIL="$OPTARG" ;;
        p) ADMIN_PASSWORD="$OPTARG" ;;
        P) PORT="$OPTARG" ;;
        v) VOLUME_DIR="$OPTARG" ;;
        w) WEBHOOK_URL="$OPTARG" ;;
        l) LOCATION="$OPTARG" ;;
        r) RESOURCE_GROUP="$OPTARG" ;;
        *) usage ;;
    esac
done

# Required checks
if [ -z "${DOMAIN:-}" ] || [ -z "${ADMIN_EMAIL:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
    echo "ERROR: DOMAIN, ADMIN_EMAIL, and ADMIN_PASSWORD are required."
    usage
fi

SERVICE_USER="coder"
EXTENSIONS=(
    "ms-azuretools.vscode-azureappservice"
    "ms-azuretools.vscode-azurefunctions"
    "ms-azuretools.vscode-azureresourcegroups"
    "ms-azuretools.vscode-docker"
    "ms-azuretools.vscode-containers"
    "ms-azuretools.vscode-azurestaticwebapps"
    "ms-azuretools.vscode-azurite"
    "ms-azuretools.vscode-cosmosdb"
    "ms-kubernetes-tools.vscode-kubernetes-tools"
    "hashicorp.terraform"
    "azurerm-tools.azurerm-vscode-tools"
    "ms-python.python"
    "ms-python.debugpy"
    "ms-toolsai.jupyter"
    "ms-toolsai.jupyter-keymap"
    "ms-toolsai.vscode-jupyter-cell-tags"
    "ms-toolsai.vscode-jupyter-slideshow"
    "ms-toolsai.jupyter-renderers"
    "ms-vscode.powershell"
    "dbaeumer.vscode-eslint"
    "esbenp.prettier-vscode"
    "eamodio.gitlens"
    "redhat.vscode-yaml"
    "ritwickdey.liveserver"
    "formulahendry.code-runner"
    "humao.rest-client"
    "streetsidesoftware.code-spell-checker"
    "wallabyjs.quokka-vscode"
    "donjayamanne.githistory"
    "github.copilot"
)

# -----------------------------
# Webhook function
# -----------------------------
notify_webhook() {
    if [ -z "$WEBHOOK_URL" ]; then
        return 0
    fi
    local status="$1"
    local step="$2"
    local message="$3"
    local payload=$(cat <<JSON
{
  "vm_name": "$(hostname)",
  "status": "$status",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "location": "$LOCATION",
  "resource_group": "$RESOURCE_GROUP",
  "details": {
    "step": "$step",
    "message": "$message"
  }
}
JSON
)
    curl -s -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d "$payload" --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 5 --output /dev/null || true
}

# -----------------------------
# Validation
# -----------------------------
[[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]] && { echo "Invalid domain format"; exit 1; }
[[ ! "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ] && { echo "Invalid port"; exit 1; }
notify_webhook "provisioning" "validation" "Inputs validated"

# -----------------------------
# System update
# -----------------------------
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q curl wget gnupg2 lsb-release ca-certificates apt-transport-https \
  nginx certbot python3-certbot-nginx ufw git build-essential sudo cron \
  python3 python3-pip jq software-properties-common

# -----------------------------
# Service user
# -----------------------------
id "$SERVICE_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$SERVICE_USER"
echo "$SERVICE_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/"$SERVICE_USER"
chmod 440 /etc/sudoers.d/"$SERVICE_USER"

# -----------------------------
# Node.js, Docker
# -----------------------------
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y -q nodejs
npm install -g npm@latest --no-progress
curl -fsSL https://get.docker.com | sh
usermod -aG docker "$SERVICE_USER"

# -----------------------------
# Code-server
# -----------------------------
curl -fsSL https://code-server.dev/install.sh | bash
CONFIG_DIR="/home/$SERVICE_USER/.config/code-server"
DATA_DIR="/home/$SERVICE_USER/.local/share/code-server"
EXT_DIR="$DATA_DIR/extensions"
mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$EXT_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR" "$DATA_DIR" "$EXT_DIR"

cat > "$CONFIG_DIR/config.yaml" <<EOF
bind-addr: 127.0.0.1:$PORT
auth: password
password: $ADMIN_PASSWORD
cert: false
EOF
chown "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR/config.yaml"
chmod 600 "$CONFIG_DIR/config.yaml"

# -----------------------------
# Systemd service
# -----------------------------
cat > /etc/systemd/system/code-server.service <<EOF
[Unit]
Description=code-server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=/home/$SERVICE_USER
Environment=HOME=/home/$SERVICE_USER
ExecStart=$(command -v code-server) --config $CONFIG_DIR/config.yaml --user-data-dir $DATA_DIR --extensions-dir $EXT_DIR
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable code-server.service
systemctl restart code-server.service
notify_webhook "provisioning" "service_start" "code-server started"

# -----------------------------
# Install extensions
# -----------------------------
for ext in "${EXTENSIONS[@]}"; do
    sudo -u "$SERVICE_USER" code-server --install-extension "$ext" --force || true
done

# -----------------------------
# Firewall
# -----------------------------
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "$PORT"/tcp
ufw --force enable

# -----------------------------
# Nginx reverse proxy + SSL
# -----------------------------
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/html
chown www-data:www-data /var/www/html

# Temporary HTTP server for certbot validation
cat > /etc/nginx/sites-available/code-server <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    root /var/www/html;
    location / {
        return 200 'Certbot validation ready';
        add_header Content-Type text/plain;
    }
}
EOF
ln -sf /etc/nginx/sites-available/code-server /etc/nginx/sites-enabled/code-server
nginx -t && systemctl restart nginx

# Obtain SSL
if ! certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL"; then
    echo "Certbot nginx plugin failed, trying webroot fallback"
    systemctl start nginx || true
    certbot certonly --webroot -w /var/www/html -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL"
fi

# Verify certificate
[ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] && { echo "SSL certificate not found"; exit 1; }

# Full HTTPS proxy for code-server
cat > /etc/nginx/sites-available/code-server <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

ln -sf /etc/nginx/sites-available/code-server /etc/nginx/sites-enabled/code-server
nginx -t && systemctl reload nginx

notify_webhook "provisioning" "complete" "Setup complete"
echo "✅ Code-server setup complete at https://$DOMAIN"
