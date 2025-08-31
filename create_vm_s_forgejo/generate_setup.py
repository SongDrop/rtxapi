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
    docker_compose_url = "https://github.com/docker/compose/releases/download/v2.38.1/docker-compose-linux-x86_64"
    buildx_url = "https://github.com/docker/buildx/releases/download/v0.11.2/buildx-v0.11.2.linux-amd64"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"
    # =======================================
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

  if [ -z "${{WEBHOOK_URL}}" ]; then
    return 0
  fi

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Notifying webhook: status=$status step=$step"

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
  return 0
}
'''

    # Full script template
    script_template = f"""#!/bin/bash

set -e
set -o pipefail
export HOME=/root

if [ -n "$DEBUG" ]; then
    set -x
fi

LOG_FILE="/var/log/forgejo_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================"
echo "Starting Forgejo installation script"
echo "Timestamp: $(date)"
echo "Log file: $LOG_FILE"
echo "============================================"

{webhook_notification}

trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code ${{?}}."' ERR

# ----------------- Validation -----------------
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain format"
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

LFS_JWT_SECRET=$(openssl rand -hex 32)

notify_webhook "provisioning" "starting" "Beginning Forgejo setup"

# ---------------- SYSTEM SETUP ----------------
echo "[1/9] System updates and dependencies..."
notify_webhook "provisioning" "system_update" "Running apt-get update & install"

for i in {{1..5}}; do
    if apt-get update; then break; fi
    echo "apt-get update failed (attempt $i/5), retrying..."
    sleep 10
done

for i in {{1..5}}; do
    if DEBIAN_FRONTEND=noninteractive apt-get install -y curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx git-lfs openssl ufw; then break; fi
    echo "Package installation failed (attempt $i/5), retrying..."
    sleep 10
done

# ========== DOCKER SETUP ==========
echo "[2/9] Installing and starting Docker..."
notify_webhook "provisioning" "docker_setup" "Installing Docker & CLI plugins"

# Remove old versions if any
apt-get remove -y docker docker-engine docker.io containerd runc || true

# Install dependencies for Docker repo
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker’s official GPG key and repository
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
ARCH=$(dpkg --print-architecture)
CODENAME=$(lsb_release -cs)
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list

apt-get update

# Install Docker packages with retries
for i in {1..5}; do
    if apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
        break
    fi
    echo "Docker package installation failed (attempt $i/5), retrying in 10s..."
    sleep 10
    if [ $i -eq 5 ]; then
        notify_webhook "failed" "docker_setup" "Failed to install Docker packages"
        exit 1
    fi
done

# Add current user to docker group if not root
CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" != "root" ]; then
    usermod -aG docker "$CURRENT_USER" || true
fi

# Start Docker service with retries
echo "Starting Docker service..."
for i in {1..10}; do
    if systemctl enable docker && systemctl start docker; then
        echo "Docker started via systemctl"
        break
    fi
    echo "Docker service failed to start (attempt $i/10), retrying in 5s..."
    sleep 5
    if [ $i -eq 10 ]; then
        echo "Docker failed to start after 10 attempts. Last 50 lines of journalctl:"
        journalctl -u docker -n 50 --no-pager
        notify_webhook "failed" "docker_start" "Docker service failed to start"
        exit 1
    fi
done

# Wait for Docker to respond
echo "Waiting for Docker daemon to be ready..."
timeout=180  # 3 minutes
while [ $timeout -gt 0 ]; do
    if docker info >/dev/null 2>&1; then
        echo "Docker daemon is ready"
        break
    fi
    sleep 5
    timeout=$((timeout - 5))
done

if [ $timeout -eq 0 ]; then
    echo "Docker did not become ready within 3 minutes"
    journalctl -u docker -n 50 --no-pager
    notify_webhook "failed" "docker_failed" "Docker daemon startup timeout"
    exit 1
fi

# Verify Docker CLI tools
docker --version || (echo "ERROR: Docker CLI not working" && exit 1)
docker compose version || (echo "ERROR: Docker Compose not working" && exit 1)
docker buildx version || (echo "ERROR: Docker Buildx not working" && exit 1)

notify_webhook "provisioning" "docker_setup_complete" "Docker & CLI plugins installed successfully"
echo "Docker setup complete ✅"

# ---------------- FORGEJO SETUP ----------------
echo "[3/9] Setting up Forgejo..."
notify_webhook "provisioning" "forgejo_setup" "Setting up Forgejo directories and config"

mkdir -p "$FORGEJO_DIR"/data
mkdir -p "$FORGEJO_DIR"/config
mkdir -p "$FORGEJO_DIR"/ssl
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
      - FORGEJO__server__DOMAIN={DOMAIN_NAME}
      - FORGEJO__server__ROOT_URL=https://{DOMAIN_NAME}
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
      - "{PORT}:3000"
      - "222:22"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 10s
      timeout: 5s
      retries: 12
EOF

# Start Forgejo
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d
elif docker compose version >/dev/null 2>&1; then
    docker compose up -d
else
    notify_webhook "failed" "compose_failed" "Docker Compose not available"
    exit 1
fi

# Wait for container healthy
for i in {{1..60}}; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' forgejo 2>/dev/null || echo "none")
    if [ "$STATUS" = "healthy" ]; then break; fi
    sleep 2
done

# ---------------- NETWORK SECURITY ----------------
echo "[4/9] Configuring firewall..."
notify_webhook "provisioning" "firewall_setup" "Configuring firewall"

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "{PORT}/tcp"
ufw --force enable

# ---------------- SSL ----------------
echo "[5/9] Setting up SSL certificate..."
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
echo "[6/9] Configuring Nginx..."
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
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        add_header Content-Security-Policy "frame-ancestors 'self' {ALLOW_EMBED_WEBSITE}" always;
    }}
}}
EOF

ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# ---------------- VERIFICATION ----------------
echo "[7/9] Verifying setup..."
notify_webhook "provisioning" "verification" "Running post-install checks"

if ! docker ps --filter "name=forgejo" --filter "status=running" | grep -q forgejo; then
    echo "ERROR: Forgejo container is not running!"
    notify_webhook "failed" "verification" "Forgejo container not running"
    docker logs forgejo
    exit 1
fi

if ! nginx -t; then
    echo "ERROR: Nginx configuration test failed"
    notify_webhook "failed" "verification" "Nginx configuration failed"
    exit 1
fi

if [ ! -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
    echo "ERROR: SSL certificate not found!"
    notify_webhook "failed" "verification" "SSL cert missing"
    exit 1
fi

# ---------------- FINAL CONFIG ----------------
echo "[8/9] Final configuration..."
notify_webhook "provisioning" "final_config" "Final configuration"

sleep 30  # Wait for Forgejo initialization
docker exec forgejo forgejo admin user create --username admin --password "{ADMIN_PASSWORD}" --email "{ADMIN_EMAIL}" --admin || echo "Admin user may already exist"

notify_webhook "completed" "finished" "Forgejo deployment succeeded"

echo "============================================"
echo "✅ Forgejo Setup Complete!"
echo "🔗 Access: https://{DOMAIN_NAME}"
echo "👤 Admin: {ADMIN_EMAIL}"
echo "🔒 Password: {ADMIN_PASSWORD}"
echo "Installation log saved to: $LOG_FILE"
"""
    return script_template
