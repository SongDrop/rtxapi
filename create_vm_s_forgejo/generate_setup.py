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

    script_template = f"""#!/bin/bash

set -e
set -o pipefail
export HOME=/root

# ----------------------------------------------------------------------
#  Webhook helper
# ----------------------------------------------------------------------
{webhook_notification}

trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code ${{?}}."' ERR

# Validate domain
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain format"
    notify_webhook "failed" "validation" "Invalid domain format"
    exit 1
fi

# Configuration
DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
ADMIN_PASSWORD="{ADMIN_PASSWORD}"
PORT="{PORT}"
FORGEJO_DIR="{forgejo_dir}"
DNS_HOOK_SCRIPT="{DNS_HOOK_SCRIPT}"
WEBHOOK_URL="{WEBHOOK_URL}"

LFS_JWT_SECRET=$(openssl rand -hex 32)

notify_webhook "provisioning" "starting" "Beginning Forgejo setup"

# ========== SYSTEM SETUP ==========
echo "[1/9] System updates and dependencies..."
notify_webhook "provisioning" "system_update" "Running apt-get update & install"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \\
    curl git nginx certbot \\
    python3-pip python3-venv jq make net-tools \\
    python3-certbot-nginx \\
    git git-lfs openssl

# ========== DOCKER SETUP ==========
echo "[2/9] Configuring Docker..."
notify_webhook "provisioning" "docker_setup" "Installing Docker & CLI plugins"

# Install Docker from Ubuntu repositories (more stable)
apt-get install -y docker.io

# Add current user to docker group
CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" != "root" ]; then
    usermod -aG docker "$CURRENT_USER" || true
fi

# Start Docker service
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable docker
    systemctl start docker
elif command -v service >/dev/null 2>&1; then
    service docker start
fi

# Wait for Docker to start
echo "Waiting for Docker to start..."
timeout=30
while [ $timeout -gt 0 ]; do
    if docker info >/dev/null 2>&1; then
        echo "Docker started successfully"
        break
    fi
    sleep 1
    timeout=$((timeout - 1))
done

if [ $timeout -eq 0 ]; then
    echo "ERROR: Docker did not start within 30 seconds"
    notify_webhook "failed" "docker_failed" "Docker startup timeout"
    exit 1
fi

# Install Docker Compose
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "{docker_compose_url}" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/bin/docker-compose

# Install Docker Buildx
echo "Installing Docker Buildx..."
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "{buildx_url}" -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
ln -sf /usr/local/lib/docker/cli-plugins/docker-buildx /usr/bin/docker-buildx

# Verify Docker tools are working
docker --version
docker-compose --version
docker buildx version

# ========== FORGEJO SETUP ==========
echo "[3/9] Setting up Forgejo..."
notify_webhook "provisioning" "forgejo_setup" "Setting up Forgejo directories and config"

mkdir -p "$FORGEJO_DIR"/{{data,config,ssl}}
cd "$FORGEJO_DIR"

# Create app.ini with LFS support
cat > "$FORGEJO_DIR/config/app.ini" <<EOF_APPINI
[server]
LFS_START_SERVER = true
LFS_CONTENT_PATH = /data/gitea/lfs
LFS_JWT_SECRET = $LFS_JWT_SECRET
LFS_MAX_FILE_SIZE = {LFS_MAX_FILE_SIZE_IN_BYTES}

[lfs]
PATH = /data/gitea/lfs

[repository]
UPLOAD_ENABLED = true
UPLOAD_FILE_MAX_SIZE = {LFS_MAX_FILE_SIZE_IN_BYTES}
EOF_APPINI

# ========== DOCKER COMPOSE ==========
echo "[4/9] Configuring Docker Compose..."
notify_webhook "provisioning" "compose_setup" "Configuring Docker Compose"

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
      - FORGEJO__lfs__PATH=/data/gitea/lfs
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

docker compose up -d

# Wait for Forgejo container to be healthy
echo "Waiting for Forgejo container health..."
for i in $(seq 1 60); do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' forgejo 2>/dev/null || echo "none")
    if [ "$STATUS" = "healthy" ]; then
        echo "✅ Forgejo container is healthy"
        break
    fi
    sleep 2
done

# ========== NETWORK SECURITY ==========
echo "[5/9] Configuring firewall..."
notify_webhook "provisioning" "firewall_setup" "Configuring firewall"

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "{PORT}/tcp"
ufw --force enable

# ========== SSL CERTIFICATE ==========
echo "[6/9] Setting up SSL certificate..."
notify_webhook "provisioning" "ssl_setup" "Setting up SSL certificate"

# Download Let's Encrypt configuration files
mkdir -p /etc/letsencrypt
curl -s "{letsencrypt_options_url}" > /etc/letsencrypt/options-ssl-nginx.conf
curl -s "{ssl_dhparams_url}" > /etc/letsencrypt/ssl-dhparams.pem

if [ -f "$DNS_HOOK_SCRIPT" ]; then
    echo "Using DNS hook script at $DNS_HOOK_SCRIPT"
    chmod +x "$DNS_HOOK_SCRIPT"
    
    # Obtain certificate
    certbot certonly --manual \\
        --preferred-challenges=dns \\
        --manual-auth-hook "$DNS_HOOK_SCRIPT add" \\
        --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" \\
        --agree-tos --email "{ADMIN_EMAIL}" \\
        -d "{DOMAIN_NAME}" -d "*.{DOMAIN_NAME}" \\
        --non-interactive \\
        --manual-public-ip-logging-ok
else
    echo "Warning: No DNS hook script found at $DNS_HOOK_SCRIPT"
    echo "Falling back to standard certificate"
    systemctl stop nginx || true
    certbot certonly --standalone --preferred-challenges http --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" --non-interactive
    systemctl start nginx || true
fi

# ========== NGINX CONFIG ==========
echo "[7/9] Configuring Nginx..."
notify_webhook "provisioning" "nginx_setup" "Configuring Nginx"

# Remove default Nginx config
rm -f /etc/nginx/sites-enabled/default

cat > /etc/nginx/sites-available/forgejo <<EOF
map \$http_upgrade \$connection_upgrade {{
    default upgrade;
    '' close;
}}

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

# ========== VERIFICATION ==========
echo "[8/9] Verifying setup..."
notify_webhook "provisioning" "verification" "Running post-install checks"

# Verify container is running
if ! docker ps --filter "name=forgejo" --filter "status=running" | grep -q forgejo; then
    echo "ERROR: Forgejo container is not running!"
    notify_webhook "failed" "verification" "Forgejo container not running"
    docker logs forgejo
    exit 1
fi

# Verify Nginx config
if ! nginx -t; then
    echo "ERROR: Nginx configuration test failed"
    notify_webhook "failed" "verification" "Nginx configuration failed"
    exit 1
fi

# Verify SSL certificate
if [ ! -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
    echo "ERROR: SSL certificate not found!"
    notify_webhook "failed" "verification" "SSL cert missing"
    exit 1
fi

# ========== FINAL CONFIG ==========
echo "[9/9] Final configuration..."
notify_webhook "provisioning" "final_config" "Final configuration"

echo "Creating admin user..."
sleep 30  # Wait for Forgejo initialization

# Try to create admin user (may fail if already exists)
docker exec forgejo forgejo admin user create \\
    --username admin \\
    --password "{ADMIN_PASSWORD}" \\
    --email "{ADMIN_EMAIL}" \\
    --admin || echo "Admin user may already exist"

notify_webhook "completed" "finished" "Forgejo deployment succeeded"

echo "============================================"
echo "✅ Forgejo Setup Complete!"
echo ""
echo "🔗 Access: https://{DOMAIN_NAME}"
echo "👤 Admin: {ADMIN_EMAIL}
echo "🔒 Password: {ADMIN_PASSWORD}"
echo ""
echo "⚙️ Verification:"
echo "   - Container status: docker ps"
echo "   - Nginx status: systemctl status nginx"
echo "   - SSL certificate: certbot certificates"
echo "   - Port accessibility: curl -v http://localhost:{PORT}"
echo ""
echo "⚠️ Important:"
echo "1. If you see Nginx default page:"
echo "   sudo rm -f /etc/nginx/sites-enabled/default"
echo "   sudo systemctl restart nginx"
echo "2. If SSL fails:"
echo "   sudo certbot --nginx -d {DOMAIN_NAME} --non-interactive --agree-tos --email {ADMIN_EMAIL} --redirect"
echo "3. First-time setup may require visiting https://{DOMAIN_NAME} to complete installation"
echo "============================================"
"""
    return script_template