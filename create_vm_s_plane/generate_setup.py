import json

def generate_plane_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    NGINX_PORT=80,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DATA_DIR="/opt/plane",
    DOCKER_COMPOSE_VERSION="v2.27.0",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a Bash script that installs Plane Project Manager behind Nginx,
    obtains a Let's Encrypt certificate, configures a firewall,
    and optionally reports progress to a webhook.
    """
    # Escape variables for JSON
    location_escaped = json.dumps(location)
    resource_group_escaped = json.dumps(resource_group)

    # URLs
    docker_compose_url = f"https://github.com/docker/compose/releases/download/{DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"
    plane_setup_url = "https://github.com/makeplane/plane/releases/latest/download/setup.sh"

    # Webhook helper
    if WEBHOOK_URL:
        webhook_notification = f'''
notify_webhook() {{
    local status=$1
    local step=$2
    local message=$3

    echo "[\\$(date '+%Y-%m-%d %H:%M:%S')] Notifying webhook: status=$status step=$step"

    JSON_PAYLOAD=$(cat <<EOF
{{
  "vm_name": "\\$(hostname)",
  "status": "$status",
  "timestamp": "\\$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "location": {location_escaped},
  "resource_group": {resource_group_escaped},
  "details": {{
    "step": "$step",
    "message": "$message"
  }}
}}
EOF
    )

    curl -s -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d "$JSON_PAYLOAD" \\
        --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 5 --output /dev/null --write-out "Webhook result: %{{http_code}}"
}}
'''
    else:
        webhook_notification = '''
notify_webhook() {
    # No webhook configured - silently ignore
    return 0
}
'''

    # Bash script template
    script_template = f"""#!/usr/bin/env bash
set -e
set -o pipefail

# ----------------------------------------------------------------------
#  Helper: webhook notification
# ----------------------------------------------------------------------
{webhook_notification}

# Trap errors to notify webhook
trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code ${{?}}."' ERR

# ----------------------------------------------------------------------
#  Validate domain and port
# ----------------------------------------------------------------------
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain name {DOMAIN_NAME}"
    notify_webhook "failed" "validation" "Invalid domain format"
    exit 1
fi

if ! [[ "{NGINX_PORT}" =~ ^[0-9]+$ ]] || [ "{NGINX_PORT}" -lt 1 ] || [ "{NGINX_PORT}" -gt 65535 ]; then
    echo "ERROR: Invalid port number {NGINX_PORT}"
    notify_webhook "failed" "validation" "Invalid port number"
    exit 1
fi

notify_webhook "provisioning" "starting" "Beginning Plane setup"

# ----------------------------------------------------------------------
#  Install dependencies
# ----------------------------------------------------------------------
echo "[1/10] Updating system and installing dependencies..."
notify_webhook "provisioning" "system_update" "Installing required packages"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq \\
    curl git docker.io nginx certbot ufw \\
    python3-pip python3-venv jq make net-tools \\
    python3-certbot-nginx openssl

# ----------------------------------------------------------------------
#  Docker & Docker Compose
# ----------------------------------------------------------------------
notify_webhook "provisioning" "docker_setup" "Setting up Docker and Docker Compose"
systemctl enable --now docker

mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSfSL "{docker_compose_url}" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/bin/docker-compose || true

docker --version
docker-compose --version

# ----------------------------------------------------------------------
#  Plane setup
# ----------------------------------------------------------------------
echo "[2/10] Creating Plane directory..."
mkdir -p "{DATA_DIR}"
cd "{DATA_DIR}"

echo "[3/10] Downloading Plane setup script..."
curl -fsSL -o setup.sh "{plane_setup_url}"
chmod +x setup.sh

echo "[4/10] Installing Plane..."
./setup.sh <<EOF
1
8
EOF

# Configure environment
echo "[5/10] Configuring Plane environment..."
if [ -f "plane-app/plane.env" ]; then
    ENV_FILE="plane-app/plane.env"
elif [ -f "plane-app-preview/plane.env" ]; then
    ENV_FILE="plane-app-preview/plane.env"
else
    echo "ERROR: plane.env not found"
    notify_webhook "failed" "plane_config" "plane.env file not found"
    exit 1
fi

sed -i "s|NGINX_PORT=.*|NGINX_PORT={NGINX_PORT}|" "$ENV_FILE"
sed -i "s|WEB_URL=.*|WEB_URL=https://{DOMAIN_NAME}|" "$ENV_FILE"
sed -i "s|CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://{DOMAIN_NAME}|" "$ENV_FILE"
echo "DOMAIN={DOMAIN_NAME}" >> "$ENV_FILE"
echo "EMAIL={ADMIN_EMAIL}" >> "$ENV_FILE"

# ----------------------------------------------------------------------
#  Firewall
# ----------------------------------------------------------------------
echo "[6/10] Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "{NGINX_PORT}/tcp"
ufw --force enable

# ----------------------------------------------------------------------
#  SSL Certificate
# ----------------------------------------------------------------------
echo "[7/10] Obtaining SSL certificate..."
mkdir -p /etc/letsencrypt
curl -sSf "{letsencrypt_options_url}" -o /etc/letsencrypt/options-ssl-nginx.conf
curl -sSf "{ssl_dhparams_url}" -o /etc/letsencrypt/ssl-dhparams.pem

if [ -x "{DNS_HOOK_SCRIPT}" ]; then
    chmod +x "{DNS_HOOK_SCRIPT}"
    certbot certonly --manual --preferred-challenges dns --manual-auth-hook "{DNS_HOOK_SCRIPT} add" \\
        --manual-cleanup-hook "{DNS_HOOK_SCRIPT} clean" --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" -d "*.{DOMAIN_NAME}" --non-interactive --manual-public-ip-logging-ok
else
    systemctl stop nginx || true
    certbot certonly --standalone --preferred-challenges http --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" --non-interactive
    systemctl start nginx || true
fi

# ----------------------------------------------------------------------
#  Nginx Reverse Proxy
# ----------------------------------------------------------------------
echo "[8/10] Configuring Nginx..."
cat > /etc/nginx/sites-available/plane <<EOF_NGINX
server {{
    listen 80;
    server_name {DOMAIN_NAME};
    return 301 https://\$host\$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {DOMAIN_NAME};
    ssl_certificate /etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN_NAME}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    client_max_body_size 100M;

    location / {{
        proxy_pass http://127.0.0.1:{NGINX_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
    }}
}}
EOF_NGINX

ln -sf /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# ----------------------------------------------------------------------
#  Start Plane services
# ----------------------------------------------------------------------
echo "[9/10] Starting Plane services..."
./setup.sh <<EOF
2
8
EOF

# ----------------------------------------------------------------------
#  Final verification
# ----------------------------------------------------------------------
echo "[10/10] Performing final checks..."
if ! docker ps | grep -q "plane"; then
    echo "ERROR: Plane container is not running!"
    notify_webhook "failed" "verification" "Plane container not running"
    exit 1
fi

if ! nginx -t; then
    echo "ERROR: Nginx configuration test failed"
    notify_webhook "failed" "verification" "Nginx test failed"
    exit 1
fi

if [ ! -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
    echo "ERROR: SSL certificate not found!"
    notify_webhook "failed" "verification" "SSL cert missing"
    exit 1
fi

echo "✅ Plane setup complete! Access at https://{DOMAIN_NAME}"
notify_webhook "completed" "finished" "Plane deployment succeeded"
"""
    return script_template
