def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    FRONTEND_PORT,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
    WEBHOOK_URL="",
    ALLOW_EMBED_WEBSITE="",
    location="",
    resource_group=""
):
    """
    Returns a Bash script that installs Forgejo behind Nginx,
    obtains a Let's Encrypt certificate, configures a firewall,
    and (optionally) reports progress to a webhook.
    """

    # ---------- URLs ----------
    docker_compose_url = "https://github.com/docker/compose/releases/download/v2.38.1/docker-compose-linux-x86_64"
    buildx_url = "https://github.com/docker/buildx/releases/download/v0.11.2/buildx-v0.11.2.linux-amd64"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"

    # ---------- Constants ----------
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

    # ---------- Bash script ----------
    script_template = f"""#!/usr/bin/env bash
set -e
set -o pipefail
export HOME=/root

# ----------------------------------------------------------------------
#  Webhook helper
# ----------------------------------------------------------------------
{webhook_notification}

trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code ${{?}}."' ERR

# ----------------------------------------------------------------------
#  Validate inputs
# ----------------------------------------------------------------------
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
  echo "ERROR: Invalid domain name '{DOMAIN_NAME}'"
  notify_webhook "failed" "validation" "Invalid domain format"
  exit 1
fi

if ! [[ "{FRONTEND_PORT}" =~ ^[0-9]+$ ]] || [ "{FRONTEND_PORT}" -lt 1 ] || [ "{FRONTEND_PORT}" -gt 65535 ]; then
  echo "ERROR: Invalid port number '{FRONTEND_PORT}'"
  notify_webhook "failed" "validation" "Invalid port number"
  exit 1
fi

notify_webhook "provisioning" "starting" "Beginning Forgejo setup"

DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
ADMIN_PASSWORD="{ADMIN_PASSWORD}"
PORT="{FRONTEND_PORT}"
FORGEJO_DIR="{forgejo_dir}"
DNS_HOOK_SCRIPT="{DNS_HOOK_SCRIPT}"
WEBHOOK_URL="{WEBHOOK_URL}"

LFS_JWT_SECRET=$(openssl rand -hex 32)

# ----------------------------------------------------------------------
#  System updates & required packages
# ----------------------------------------------------------------------
echo "[1/10] Updating system & installing dependencies..."
notify_webhook "provisioning" "system_update" "Running apt-get update & install"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq \\
    curl gnupg lsb-release software-properties-common \\
    git nginx certbot ufw \\
    python3-pip python3-venv jq make net-tools \\
    python3-certbot-nginx git-lfs openssl

# ----------------------------------------------------------------------
#  Install Docker from official repo
# ----------------------------------------------------------------------
notify_webhook "provisioning" "docker_setup" "Installing Docker & CLI plugins"

# Remove any existing Docker installations to avoid conflicts
apt-get remove -y docker docker-engine docker.io containerd runc || true

# Install prerequisites
apt-get install -yq ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# Add current user to docker group
CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" != "root" ]; then
    usermod -aG docker "$CURRENT_USER" || true
fi

# ----------------------------------------------------------------------
#  Start Docker with proper init system detection
# ----------------------------------------------------------------------
notify_webhook "provisioning" "docker_start" "Starting Docker service"

# Check if systemd is available
if [ "$(ps --no-headers -o comm 1)" = "systemd" ]; then
    systemctl enable docker
    systemctl start docker
else
    # Fallback to service command
    service docker start
fi

# Wait for Docker to start with timeout
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
    
    # Attempt to start manually as fallback
    echo "Attempting manual Docker startup..."
    nohup dockerd > /var/log/dockerd.log 2>&1 &
    sleep 5
    
    if ! docker info >/dev/null 2>&1; then
        echo "Docker manual startup also failed"
        cat /var/log/dockerd.log 2>/dev/null || true
        exit 1
    fi
fi

# ----------------------------------------------------------------------
#  Docker Compose & Buildx
# ----------------------------------------------------------------------
notify_webhook "provisioning" "compose_install" "Installing Docker Compose"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSfSL "{docker_compose_url}" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/bin/docker-compose

# Install Docker Compose plugin as well for compatibility
apt-get install -yq docker-compose-plugin

notify_webhook "provisioning" "buildx_install" "Installing Docker Buildx"
if ! docker buildx version >/dev/null 2>&1; then
    BUILDX_DIR="/usr/local/lib/docker/cli-plugins"
    mkdir -p "$BUILDX_DIR"
    curl -sSfSL "{buildx_url}" -o "$BUILDX_DIR/docker-buildx"
    chmod +x "$BUILDX_DIR/docker-buildx"
    ln -sf "$BUILDX_DIR/docker-buildx" /usr/bin/docker-buildx
fi

docker --version
docker-compose --version
docker buildx version

# ----------------------------------------------------------------------
#  Forgejo directories & configuration
# ----------------------------------------------------------------------
mkdir -p "$FORGEJO_DIR"/{{data,config,ssl}}
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

# ----------------------------------------------------------------------
#  Docker Compose file
# ----------------------------------------------------------------------
cat > "$FORGEJO_DIR/docker-compose.yml" <<EOF_COMPOSE
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
      - "{FRONTEND_PORT}:3000"
      - "222:22"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 10s
      timeout: 5s
      retries: 12
EOF_COMPOSE

cd "$FORGEJO_DIR"

# Try both docker compose and docker-compose commands
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d
elif docker compose version >/dev/null 2>&1; then
    docker compose up -d
else
    echo "ERROR: Neither docker-compose nor docker compose command found"
    notify_webhook "failed" "compose_failed" "Docker Compose not available"
    exit 1
fi

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

# ----------------------------------------------------------------------
#  Firewall
# ----------------------------------------------------------------------
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "{FRONTEND_PORT}/tcp"
ufw --force enable

# ----------------------------------------------------------------------
#  SSL certificate
# ----------------------------------------------------------------------
mkdir -p /etc/letsencrypt
curl -sSf "{letsencrypt_options_url}" -o /etc/letsencrypt/options-ssl-nginx.conf
curl -sSf "{ssl_dhparams_url}" -o /etc/letsencrypt/ssl-dhparams.pem

if [ -x "$DNS_HOOK_SCRIPT" ]; then
    chmod +x "$DNS_HOOK_SCRIPT"
    certbot certonly --manual --preferred-challenges dns --manual-auth-hook "$DNS_HOOK_SCRIPT add" --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" -d "*.{DOMAIN_NAME}" --non-interactive --manual-public-ip-logging-ok
else
    systemctl stop nginx || true
    certbot certonly --standalone --preferred-challenges http --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" --non-interactive
    systemctl start nginx || true
fi

# ----------------------------------------------------------------------
#  Nginx configuration
# ----------------------------------------------------------------------
cat > /etc/nginx/sites-available/forgejo <<EOF_NGINX
map \$http_upgrade \$connection_upgrade {{
    default upgrade;
    ''      close;
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
        proxy_pass http://127.0.0.1:{FRONTEND_PORT};
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
EOF_NGINX

ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# ----------------------------------------------------------------------
#  Final verification
# ----------------------------------------------------------------------
notify_webhook "provisioning" "verification" "Running post-install checks"
if ! docker ps --filter "name=forgejo" --filter "status=running" | grep -q forgejo; then
    notify_webhook "failed" "verification" "Forgejo container not running"
    exit 1
fi

if ! nginx -t; then
    notify_webhook "failed" "verification" "Nginx configuration failed"
    exit 1
fi

if [ ! -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
    notify_webhook "failed" "verification" "SSL cert missing"
    exit 1
fi

notify_webhook "completed" "finished" "Forgejo deployment succeeded"

echo "============================================="
echo "✅ Forgejo Setup Complete!"
echo "🔗 Access URL     : https://{DOMAIN_NAME}"
echo "👤 Admin login    : {ADMIN_EMAIL}"
echo "🔑 Admin password : {ADMIN_PASSWORD}"
echo "============================================="
"""

    return script_template