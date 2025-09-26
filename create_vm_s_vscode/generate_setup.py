import json

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT,
    VOLUME_DIR="/opt/code-server",
    WEBHOOK_URL="",
    location="",
    resource_group=""
):
    SERVICE_USER = "coder"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"
    
    
    # Webhook helper
    if WEBHOOK_URL:
        webhook_notification = f'''
notify_webhook() {{
  local status=$1
  local step=$2
  local message=$3

  if [ -z "${{WEBHOOK_URL}}" ]; then
    return 0
  fi

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Notifying webhook: status=$status step=$step"

  JSON_PAYLOAD=$(cat <<EOF
{{
  "vm_name": "$(hostname)",
  "status": "$status",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "location": {location},
  "resource_group": {resource_group},
  "details": {{
    "step": "$step",
    "message": "$message"
  }}
}}
EOF
  )

  curl -s -X POST \\
    "${{WEBHOOK_URL}}" \\
    -H "Content-Type: application/json" \\
    -d "$JSON_PAYLOAD" \\
    --connect-timeout 10 \\
    --max-time 30 \\
    --retry 2 \\
    --retry-delay 5 \\
    --output /dev/null \\
    --write-out "Webhook result: %{{http_code}}"

  return $?
}}
'''
    else:
        webhook_notification = '''
notify_webhook() {
  # No webhook configured - silently ignore
  return 0
}
'''

    script_template = f"""#!/bin/bash
set -e
set -o pipefail

# ----------------------------------------------------------------------
#  Helper: webhook notification
# ----------------------------------------------------------------------
{webhook_notification}

# If any command later fails we will report it
trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code ${{?}}."' ERR

# ========== VALIDATION ==========
echo "[1/20] Validating inputs..."
notify_webhook "provisioning" "validation" "Validating inputs"
LOG_FILE="/var/log/code-server-install.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# Validate domain
if [[ ! "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain format '{DOMAIN_NAME}'"
    notify_webhook "failed" "validation" "Invalid domain format"
    exit 1
fi

# Validate port
if [[ ! "{PORT}" =~ ^[0-9]+$ ]] || [ "{PORT}" -lt 1024 ] || [ "{PORT}" -gt 65535 ]; then
    echo "ERROR: Invalid port number '{PORT}' (must be 1024-65535)"
    notify_webhook "failed" "validation" "Invalid port number"
    exit 1
fi

# Port conflict resolution
notify_webhook "provisioning" "port_check" "Checking for port conflicts"
if ss -tulnp | grep -q ":{PORT}"; then
    echo "WARNING: Port {PORT} is in use, attempting to resolve..."
    PROCESS_INFO=$(ss -tulnp | grep ":{PORT}")
    echo "Conflict details: $PROCESS_INFO"
    systemctl stop code-server@{SERVICE_USER} || true
    pkill -f "code-server" || true
    sleep 2
    if ss -tulnp | grep -q ":{PORT}"; then
        PID=$(ss -tulnp | grep ":{PORT}" | awk '{{print $7}}' | cut -d= -f2 | cut -d, -f1 | head -1)
        PROCESS_NAME=$(ps -p "$PID" -o comm= 2>/dev/null || echo "unknown")
        echo "ERROR: Could not free port {PORT}, process $PID ($PROCESS_NAME) still using it"
        notify_webhook "failed" "port_conflict" "Could not free port {PORT}"
        exit 1
    else
        echo "Successfully freed port {PORT}"
    fi
fi

# ========== SYSTEM SETUP ==========
echo "[2/20] Updating system and installing dependencies..."
notify_webhook "provisioning" "system_update" "Updating system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q \\
    curl \\
    nginx \\
    certbot \\
    python3-certbot-nginx \\
    ufw \\
    git \\
    build-essential \\
    sudo \\
    cron \\
    python3 \\
    python3-pip \\
    gnupg \\
    software-properties-common \\
    libssl-dev \\
    zlib1g-dev \\
    libbz2-dev \\
    libreadline-dev \\
    libsqlite3-dev \\
    libffi-dev

# ========== NODE.JS INSTALLATION ==========
echo "[3/20] Installing Node.js LTS..."
notify_webhook "provisioning" "nodejs" "Installing Node.js"
apt-get remove -y nodejs npm || true
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y -q nodejs

NODE_VERSION=$(node --version)
echo "Node.js version: $NODE_VERSION"

npm install -g npm@latest

# ========== DEVELOPMENT TOOLS ==========
echo "[4/20] Installing development tools..."
notify_webhook "provisioning" "dev_tools" "Installing development tools"

echo "Installing Azure CLI..."
curl -sL https://aka.ms/InstallAzureCLIDeb | bash

echo "Installing Netlify CLI..."
npm install -g netlify-cli --force 2>&1 | while read line; do echo "[npm] $line"; done

echo "Installing Yarn..."
npm install -g yarn

# ========== PYTHON ==========
echo "[5/20] Installing pyenv and Python..."
notify_webhook "provisioning" "python" "Installing Python with pyenv"
export HOME=/root
if [ -d "$HOME/.pyenv" ]; then
    echo "Found existing pyenv installation, updating..."
    cd "$HOME/.pyenv" && git pull
else
    echo "Installing fresh pyenv..."
    curl -fsSL https://pyenv.run | bash
fi

# Setup pyenv environment for root
cat >> ~/.bashrc <<'EOF'

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv 1>/dev/null 2>&1; then
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"
fi
EOF

# Source bashrc to get pyenv available in this shell session
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"

apt-get install -y -q make build-essential libssl-dev zlib1g-dev \\
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \\
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

if ! pyenv versions | grep -q 3.9.7; then
    pyenv install 3.9.7 --verbose
fi
pyenv global 3.9.7

PYTHON_VERSION=$(python --version)
echo "Python version: $PYTHON_VERSION"

# ========== ELECTRON ==========
echo "[6/20] Installing Electron dependencies..."
notify_webhook "provisioning" "electron" "Installing Electron dependencies"
add-apt-repository universe || true
apt-get update -q
apt-get install -y -q \\
    libgtk-3-0 \\
    libnotify4 \\
    libnss3 \\
    libxss1 \\
    libasound2-data \\
    libasound2-plugins \\
    libxtst6 \\
    xauth \\
    xvfb
npm install electron --save-dev

# ========== DOCKER ==========
echo "[7/20] Installing Docker..."
notify_webhook "provisioning" "docker" "Installing Docker"
curl -fsSL https://get.docker.com | sh
usermod -aG docker {SERVICE_USER} || true

# ========== KUBERNETES ==========
echo "[8/20] Installing kubectl..."
notify_webhook "provisioning" "kubectl" "Installing Kubernetes CLI"
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

# ========== TERRAFORM ==========
echo "[9/20] Installing Terraform..."
notify_webhook "provisioning" "terraform" "Installing Terraform"
curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor --batch --yes -o /usr/share/keyrings/hashicorp.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" > /etc/apt/sources.list.d/hashicorp.list
apt-get update -q && apt-get install -y terraform

# ========== CODE-SERVER ==========
echo "[10/20] Installing code-server..."
notify_webhook "provisioning" "code_server" "Installing code-server"
curl -fsSL https://code-server.dev/install.sh | HOME=/root sh

# ========== USER SETUP ==========
echo "[11/20] Creating user '{SERVICE_USER}'..."
notify_webhook "provisioning" "user_setup" "Creating service user"
id -u {SERVICE_USER} &>/dev/null || useradd -m -s /bin/bash {SERVICE_USER}
echo "{SERVICE_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/{SERVICE_USER}
chmod 440 /etc/sudoers.d/{SERVICE_USER}

# Install pyenv for the service user
su - {SERVICE_USER} -c 'curl -fsSL https://pyenv.run | bash'
su - {SERVICE_USER} -c 'echo '\''export PYENV_ROOT="$HOME/.pyenv"'\'' >> ~/.bashrc'
su - {SERVICE_USER} -c 'echo '\''export PATH="$PYENV_ROOT/bin:$PATH"'\'' >> ~/.bashrc'
su - {SERVICE_USER} -c 'echo '\''eval "$(pyenv init --path)"'\'' >> ~/.bashrc'
su - {SERVICE_USER} -c 'echo '\''eval "$(pyenv init -)"'\'' >> ~/.bashrc'

# Install Python for the service user
su - {SERVICE_USER} -c 'export PYENV_ROOT="$HOME/.pyenv"; export PATH="$PYENV_ROOT/bin:$PATH"; eval "$(pyenv init --path)"; eval "$(pyenv init -)"; pyenv install -s 3.9.7; pyenv global 3.9.7'

# ========== CONFIG ==========
echo "[12/20] Configuring code-server..."
notify_webhook "provisioning" "config" "Configuring code-server"
mkdir -p {VOLUME_DIR}/config
cat > {VOLUME_DIR}/config/config.yaml <<EOF
bind-addr: 0.0.0.0:{PORT}
auth: password
password: {ADMIN_PASSWORD}
cert: false
EOF

chown -R {SERVICE_USER}:{SERVICE_USER} {VOLUME_DIR}
chmod 700 {VOLUME_DIR}/config
chmod 600 {VOLUME_DIR}/config/config.yaml
mkdir -p /home/{SERVICE_USER}/.config
ln -sf {VOLUME_DIR}/config /home/{SERVICE_USER}/.config/code-server

# ========== EXTENSIONS ==========
echo "[13/20] Installing VSCode extensions..."
notify_webhook "provisioning" "extensions" "Installing VSCode extensions"

extensions=(
    "ms-azuretools.vscode-azureterraform"
    "ms-azuretools.vscode-azureappservice"
    "ms-azuretools.vscode-azurefunctions"
    "ms-azuretools.vscode-azurestaticwebapps"
    "ms-azuretools.vscode-azurestorage"
    "ms-azuretools.vscode-cosmosdb"
    "ms-azuretools.vscode-docker"
    "ms-kubernetes-tools.vscode-kubernetes-tools"
    "netlify.netlify-vscode"
    "dbaeumer.vscode-eslint"
    "esbenp.prettier-vscode"
    "ms-vscode.vscode-typescript-next"
    "eamodio.gitlens"
    "ms-vscode-remote.remote-containers"
    "ms-vscode-remote.remote-ssh"
    "ms-vscode.powershell"
    "ms-python.python"
    "ms-toolsai.jupyter"
    "hashicorp.terraform"
    "redhat.vscode-yaml"
    "EliotVU.uc"
    "stefan-h-at.source-engine-support"
    "LionDoge.vscript-debug"
    "NilsSoderman.ue-python"
    "mjxcode.vscode-q3shader"
    "shd101wyy.markdown-preview-enhanced"
    "formulahendry.code-runner"
    "donjayamanne.githistory"
    "humao.rest-client"
    "streetsidesoftware.code-spell-checker"
    "Cardinal90.multi-cursor-case-preserve"
    "alefragnani.Bookmarks"
    "WallabyJs.quokka-vscode"
    "ritwickdey.LiveServer"
    "WallabyJs.console-ninja"
    "Monish.regexsnippets"
    "GitHub.copilot"
    "pnp.polacode"
    "Codeium.codeium"
    "oouo-diogo-perdigao.docthis"
    "johnpapa.vscode-peacock"
    "Postman.postman-for-vscode"
)

# Ensure extension and user data directories are correctly set
EXT_DIR="{VOLUME_DIR}/data/extensions"
USER_DATA_DIR="{VOLUME_DIR}/data"
mkdir -p "$EXT_DIR"
mkdir -p "$USER_DATA_DIR"
chown -R {SERVICE_USER}:{SERVICE_USER} "$USER_DATA_DIR"

# Install extensions
for extension in "${{extensions[@]}}"; do
    retries=3
    for i in $(seq 1 $retries); do
        echo "🔧 Installing extension: $extension (attempt $i)"
        if sudo -u "$SERVICE_USER" code-server \
            --install-extension "$extension" \
            --extensions-dir="$EXT_DIR" \
            --user-data-dir="$USER_DATA_DIR"; then
            echo "✅ Installed $extension"
            break
        else
            echo "⚠️ Attempt $i failed for $extension"
            sleep 5
        fi
    done
done


# ========== SYSTEMD ==========
echo "[14/20] Configuring systemd service..."
notify_webhook "provisioning" "systemd" "Configuring systemd service"
mkdir -p /etc/systemd/system/code-server@.service.d
cat > /etc/systemd/system/code-server@.service.d/override.conf <<EOF
[Service]
Restart=on-failure
RestartSec=5s
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/{SERVICE_USER}/.pyenv/shims:/home/{SERVICE_USER}/.pyenv/bin"
EOF

systemctl daemon-reexec
systemctl daemon-reload
systemctl enable --now code-server@{SERVICE_USER}

# Wait for code-server to start
sleep 5
if ! systemctl is-active --quiet code-server@{SERVICE_USER}; then
    echo "ERROR: code-server service failed to start"
    journalctl -u code-server@{SERVICE_USER} --no-pager -n 20
    notify_webhook "failed" "service_start" "code-server service failed to start"
    exit 1
fi

# ========== FIREWALL ==========
echo "[15/20] Configuring firewall..."
notify_webhook "provisioning" "firewall" "Configuring firewall"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow {PORT}/tcp
ufw --force enable

# ========== NGINX ==========
echo "[16/20] Configuring Nginx..."
notify_webhook "provisioning" "nginx" "Configuring Nginx"

# Remove default nginx config if exists
rm -f /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-available/default

# Temporary HTTP-only config for certbot validation
cat > /etc/nginx/sites-available/vscode <<EOF
server {{
    listen 80;
    server_name {DOMAIN_NAME};
    root /var/www/html;

    location / {{
        return 200 'Certbot validation ready';
        add_header Content-Type text/plain;
    }}
}}
EOF

ln -sf /etc/nginx/sites-available/vscode /etc/nginx/sites-enabled/vscode
nginx -t && systemctl restart nginx

# ========== SSL ==========
echo "[17/20] Setting up SSL..."
notify_webhook "provisioning" "ssl" "Setting up SSL with Let's Encrypt"
mkdir -p /etc/letsencrypt
curl -s "{letsencrypt_options_url}" > /etc/letsencrypt/options-ssl-nginx.conf
curl -s "{ssl_dhparams_url}" > /etc/letsencrypt/ssl-dhparams.pem

# Stop nginx temporarily for certbot standalone verification
systemctl stop nginx

# Obtain SSL certificate
if certbot certonly --standalone -d {DOMAIN_NAME} --non-interactive --agree-tos --email {ADMIN_EMAIL}; then
    echo "SSL certificate obtained successfully"
else
    echo "WARNING: Failed to obtain SSL certificate with standalone method, trying webroot method"
    systemctl start nginx
    certbot certonly --webroot -d {DOMAIN_NAME} --non-interactive --agree-tos --email {ADMIN_EMAIL} -w /var/www/html
fi

# Verify certificate exists
if [ -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
    echo "SSL certificate verified: /etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem"
else
    echo "ERROR: SSL certificate not found at /etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem"
    notify_webhook "failed" "ssl" "SSL certificate not found"
    exit 1
fi

systemctl start nginx

# Replace nginx config with HTTPS proxy version
cat > /etc/nginx/sites-available/vscode <<EOF
server {{
    listen 80;
    server_name {DOMAIN_NAME};
    return 301 https://\\$host\\$request_uri;
}}

server {{
    listen 443 ssl;
    server_name {DOMAIN_NAME};
    ssl_certificate /etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN_NAME}/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    
    location / {{
        proxy_pass http://localhost:{PORT}/;
        proxy_set_header Host \\$host;
        proxy_set_header Upgrade \\$http_upgrade;
        proxy_set_header Connection upgrade;
        proxy_set_header Accept-Encoding gzip;
        proxy_set_header X-Real-IP \\$remote_addr;
        proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\$scheme;
        
        # WebSocket support
        proxy_set_header Connection "Upgrade";
        proxy_read_timeout 86400;
    }}
}}
EOF

nginx -t && systemctl reload nginx

# ========== RENEWAL ==========
echo "[18/20] Setting certbot auto-renewal..."
notify_webhook "provisioning" "renewal" "Setting up certificate renewal"
CRON_CMD="0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
( crontab -l 2>/dev/null | grep -v -F "$CRON_CMD" ; echo "$CRON_CMD" ) | crontab -

# ========== FINALIZE ==========
echo "[19/20] Verifying installation..."
notify_webhook "provisioning" "verification" "Verifying installation"

if ! nginx -t; then
    echo "ERROR: Nginx config test failed"
    notify_webhook "failed" "verification" "Nginx config test failed"
    exit 1
fi

if [ ! -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
    echo "ERROR: SSL cert not found!"
    notify_webhook "failed" "verification" "SSL certificate not found"
    exit 1
fi

# Test code-server accessibility
if ! curl -s -o /dev/null -w "%{{http_code}}" http://localhost:{PORT} | grep -q 200; then
    echo "WARNING: Cannot access code-server on port {PORT}, but continuing..."
    notify_webhook "warning" "verification" "Cannot access code-server directly on port {PORT}"
fi

# Test HTTPS accessibility
HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{{http_code}}" https://{DOMAIN_NAME} || echo "000")
if [[ "$HTTPS_RESPONSE" != "200" ]]; then
    echo "WARNING: HTTPS check returned $HTTPS_RESPONSE (expected 200)"
    notify_webhook "warning" "verification" "HTTPS endpoint returned $HTTPS_RESPONSE"
else
    echo "✅ HTTPS access verified"
fi

echo "[20/20] Setup complete!"
notify_webhook "completed" "finished" "Code-server setup completed successfully"

cat <<EOF_FINAL
=============================================
✅ Code Server Setup Complete!
---------------------------------------------
🔗 Access URL     : https://{DOMAIN_NAME}
👤 Admin password : {ADMIN_PASSWORD}
---------------------------------------------
⚙️ Useful commands
   - Check status: systemctl status code-server@{SERVICE_USER}
   - View logs   : journalctl -u code-server@{SERVICE_USER} -f
   - Restart     : systemctl restart code-server@{SERVICE_USER}
   - Nginx status: systemctl status nginx
---------------------------------------------
⚠️ Post-install notes
1️⃣  First visit https://{DOMAIN_NAME} to access your code server
2️⃣  To renew SSL certificates: certbot renew --quiet
3️⃣  Extensions installed in: {VOLUME_DIR}/data/extensions
---------------------------------------------
Enjoy your new code server!
=============================================
EOF_FINAL
"""
    return script_template