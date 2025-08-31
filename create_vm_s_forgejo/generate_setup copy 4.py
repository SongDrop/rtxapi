def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
    WEBHOOK_URL="",
    ALLOW_EMBED_WEBSITE="",
    location="",
    resource_group=""
):
    # ========== CONFIGURABLE URLs ==========
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"
    MAX_UPLOAD_FILE_SIZE_IN_MB = 1024
    LFS_MAX_FILE_SIZE_IN_BYTES = MAX_UPLOAD_FILE_SIZE_IN_MB * 1024 * 1024
    forgejo_dir = "/opt/forgejo"

    # ---------- Webhook helper ----------
    if WEBHOOK_URL:
        webhook_notification = f'''
notify_webhook() {{
  local status=$1
  local step=$2
  local message=$3
  if [ -z "${{WEBHOOK_URL}}" ]; then return 0; fi
  JSON_PAYLOAD=$(cat <<EOF
{{
  "vm_name": "$(hostname)",
  "status": "$status",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "location": "{location}",
  "resource_group": "{resource_group}",
  "details": {{
    "step": "$step",
    "message": "$message"
  }}
}}
EOF
  )
  curl -s -X POST "${{WEBHOOK_URL}}" -H "Content-Type: application/json" -d "$JSON_PAYLOAD" --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 5 --output /dev/null
}}
'''
    else:
        webhook_notification = 'notify_webhook() { return 0; }'

    # ---------------- SCRIPT TEMPLATE ----------------
    script_template = f"""#!/bin/bash
set -e
set -o pipefail
export HOME=/root
LOG_FILE="/var/log/forgejo_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

{webhook_notification}

trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code $?"' ERR

# ---------------- VALIDATION ----------------
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    notify_webhook "failed" "validation" "Invalid domain format"
    exit 1
fi

DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
ADMIN_PASSWORD="{ADMIN_PASSWORD}"
PORT="{PORT}"
FORGEJO_DIR="{forgejo_dir}"
DNS_HOOK_SCRIPT="{DNS_HOOK_SCRIPT}"
WEBHOOK_URL="{WEBHOOK_URL}"
LFS_JWT_SECRET=$(openssl rand -hex 32) || {{ notify_webhook "failed" "failed" "Failed to generate LFS secret"; exit 1; }}

notify_webhook "provisioning" "starting" "Beginning Forgejo setup"

# ---------------- SYSTEM SETUP ----------------
notify_webhook "provisioning" "system_update" "Installing dependencies"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx openssl ufw

# ---------------- DOCKER SETUP ----------------
notify_webhook "provisioning" "docker_setup" "Installing Docker & CLI plugins"
apt-get remove -y docker docker-engine docker.io containerd runc || true
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
ARCH=$(dpkg --print-architecture)
CODENAME=$(lsb_release -cs)
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" != "root" ]; then usermod -aG docker "$CURRENT_USER" || true; fi
systemctl enable docker && systemctl start docker

timeout=180
while [ $timeout -gt 0 ]; do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 5
    timeout=$((timeout - 5))
done
if [ $timeout -eq 0 ]; then
    notify_webhook "failed" "docker_failed" "Docker daemon startup timeout"
    exit 1
fi

notify_webhook "provisioning" "docker_setup_complete" "Docker installed successfully"

# ---------------- FORGEJO SETUP ----------------
echo "[3/9] Setting up Forgejo..."
notify_webhook "provisioning" "forgejo_setup" "Setting up Forgejo directories and config"

mkdir -p "$FORGEJO_DIR"/{{data,config,ssl}}
chown -R 1000:1000 "$FORGEJO_DIR"/data "$FORGEJO_DIR"/config
mkdir -p "$FORGEJO_DIR/data/gitea/lfs"
chown -R 1000:1000 "$FORGEJO_DIR/data/gitea"
cd "$FORGEJO_DIR"

# Docker Compose for Forgejo
cat > docker-compose.yml <<EOF
version: "3.8"
services:
  server:
    image: codeberg.org/forgejo/forgejo:latest
    container_name: forgejo
    restart: unless-stopped
    environment:
      - FORGEJO__server__DOMAIN=$DOMAIN_NAME
      - FORGEJO__server__ROOT_URL=https://$DOMAIN_NAME
      - FORGEJO__server__HTTP_PORT=3000
      - FORGEJO__server__LFS_START_SERVER=true
      - FORGEJO__server__LFS_CONTENT_PATH=/data/gitea/lfs
      - FORGEJO__server__LFS_JWT_SECRET=$LFS_JWT_SECRET
      - FORGEJO__server__LFS_MAX_FILE_SIZE={LFS_MAX_FILE_SIZE_IN_BYTES}
    volumes:
      - ./data:/data
      - ./config:/etc/gitea
      - ./ssl:/ssl
    ports:
      - "${{PORT}}:3000"
      - "222:22"
    healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000"]
    interval: 15s
    timeout: 10s
    retries: 40
EOF

# Ensure Docker socket is usable
if ! docker ps >/dev/null 2>&1; then
    echo "⚠️ Docker socket not accessible. Trying to fix permissions..."
    chmod 666 /var/run/docker.sock || true
fi

# Start Forgejo with retries
attempt=1
max_attempts=3
while [ $attempt -le $max_attempts ]; do
    echo "Starting Forgejo (attempt $attempt/$max_attempts)..."
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose up -d && break
    elif docker compose version >/dev/null 2>&1; then
        docker compose up -d && break
    else
        notify_webhook "failed" "compose_failed" "Docker Compose not available"
        exit 1
    fi
    attempt=$((attempt+1))
    sleep 5
done

if [ $attempt -gt $max_attempts ]; then
    notify_webhook "failed" "forgejo_start_failed" "Forgejo failed to start after $max_attempts attempts"
    exit 1
fi

# Wait for Forgejo container to become healthy
for i in {{1..60}}; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' forgejo 2>/dev/null || echo "none")
    if [ "$STATUS" = "healthy" ]; then
        echo "✅ Forgejo is healthy"
        break
    fi
    sleep 2
done

# ---------------- NETWORK SECURITY ----------------
notify_webhook "provisioning" "firewall_setup" "Configuring firewall"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "{PORT}/tcp"
ufw --force enable

# ---------------- SSL ----------------
notify_webhook "provisioning" "ssl_setup" "Setting up SSL certificate"
mkdir -p /etc/letsencrypt
curl -s "{letsencrypt_options_url}" > /etc/letsencrypt/options-ssl-nginx.conf
curl -s "{ssl_dhparams_url}" > /etc/letsencrypt/ssl-dhparams.pem

if [ -f "$DNS_HOOK_SCRIPT" ]; then
    chmod +x "$DNS_HOOK_SCRIPT"
    certbot certonly --manual --preferred-challenges=dns --manual-auth-hook "$DNS_HOOK_SCRIPT add" --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" -d "*.{DOMAIN_NAME}" --non-interactive --manual-public-ip-logging-ok
else
    systemctl stop nginx || true
    certbot certonly --standalone --preferred-challenges http --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" --non-interactive
    systemctl start nginx || true
fi

# ---------------- NGINX ----------------
notify_webhook "provisioning" "nginx_setup" "Configuring Nginx"
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/forgejo <<EOF
server {{
    listen 80;
    server_name {DOMAIN_NAME};
    return 301 https://$host$request_uri;
}}
server {{
    listen 443 ssl http2;
    server_name {DOMAIN_NAME};
    ssl_certificate /etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN_NAME}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    client_max_body_size {MAX_UPLOAD_FILE_SIZE_IN_MB}M;
    location / {{
        proxy_pass http://localhost:{PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        add_header Content-Security-Policy "frame-ancestors 'self' {ALLOW_EMBED_WEBSITE}" always;
    }}
}}
EOF
ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# ---------------- FINAL CONFIG ----------------
sleep 30
docker exec forgejo forgejo admin user create --username admin --password "{ADMIN_PASSWORD}" --email "{ADMIN_EMAIL}" --admin || true
notify_webhook "completed" "finished" "Forgejo deployment succeeded"
"""
    return script_template
