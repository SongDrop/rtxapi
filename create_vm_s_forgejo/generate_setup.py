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
  # No webhook configured - silently ignore
  return 0
}
'''

    # ---------- Bash script ----------
    script_template = f"""#!/usr/bin/env bash
set -e
set -o pipefail
# ----------------------------------------------------------------------
#  Set essential environment variables
# ----------------------------------------------------------------------
export HOME=/root  # Required for Git operations under Azure CustomScript

# ----------------------------------------------------------------------
#  Helper: webhook notification
# ----------------------------------------------------------------------
{webhook_notification}

# If any command later fails we will report it (if a webhook is configured)
trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code ${{?}}."' ERR

# ----------------------------------------------------------------------
#  Validate the supplied domain name
# ----------------------------------------------------------------------
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
  echo "ERROR: Invalid domain name \"{DOMAIN_NAME}\""
  notify_webhook "failed" "validation" "Invalid domain format"
  exit 1
fi

# ----------------------------------------------------------------------
#  Validate the port number
# ----------------------------------------------------------------------
if ! [[ "{FRONTEND_PORT}" =~ ^[0-9]+$ ]] || [ "{FRONTEND_PORT}" -lt 1 ] || [ "{FRONTEND_PORT}" -gt 65535 ]; then
  echo "ERROR: Invalid port number \"{FRONTEND_PORT}\""
  notify_webhook "failed" "validation" "Invalid port number"
  exit 1
fi

notify_webhook "provisioning" "starting" "Beginning Forgejo setup"

# ----------------------------------------------------------------------
#  Configuration (available to the whole script)
# ----------------------------------------------------------------------
DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
ADMIN_PASSWORD="{ADMIN_PASSWORD}"
PORT="{FRONTEND_PORT}"
FORGEJO_DIR="{forgejo_dir}"
DNS_HOOK_SCRIPT="{DNS_HOOK_SCRIPT}"
WEBHOOK_URL="{WEBHOOK_URL}"

# Random secret for Git-LFS JWT
LFS_JWT_SECRET=$(openssl rand -hex 32)

# ----------------------------------------------------------------------
#  System updates & required packages
# ----------------------------------------------------------------------
echo "[1/10] Updating system & installing dependencies..."
notify_webhook "provisioning" "system_update" "Running apt-get update & install"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq \\
    curl git docker.io nginx certbot ufw \\
    python3-pip python3-venv jq make net-tools \\
    python3-certbot-nginx git-lfs openssl

# ----------------------------------------------------------------------
#  Docker (Compose + Buildx) setup
# ----------------------------------------------------------------------
notify_webhook "provisioning" "docker_setup" "Installing Docker components"

# Use the most basic Docker installation approach
notify_webhook "provisioning" "docker_install" "Installing Docker from Ubuntu repository"
if ! apt-get install -y docker.io; then
    notify_webhook "failed" "docker_install" "Failed to install docker.io package"
    exit 1
fi

# Create docker group and add user
notify_webhook "provisioning" "docker_setup" "Creating docker group and adding user"
groupadd docker 2>/dev/null || true
# Use whoami to get the current user instead of SUDO_USER
CURRENT_USER=$(whoami)
usermod -aG docker "$CURRENT_USER" 2>/dev/null || true

# Start Docker with the most basic approach
notify_webhook "provisioning" "docker_start" "Starting Docker service"
systemctl enable docker

# Try to start Docker with multiple approaches
notify_webhook "provisioning" "docker_start" "Attempting to start Docker service"
if ! systemctl start docker; then
    notify_webhook "warning" "docker_start" "systemctl start docker failed, trying service command"
    service docker start || true
    sleep 3
fi

# Check if Docker is running
notify_webhook "provisioning" "docker_check" "Checking if Docker is running"
if ! systemctl is-active --quiet docker; then
    notify_webhook "failed" "docker_start" "Docker is not running. Checking status and logs"
    systemctl status docker --no-pager || true
    journalctl -u docker --no-pager -n 20 || true
    
    # Try to start Docker manually as a last resort
    notify_webhook "provisioning" "docker_manual" "Attempting to start Docker daemon manually"
    nohup dockerd > /var/log/dockerd.log 2>&1 &
    sleep 5
fi

# Final check if Docker is working
notify_webhook "provisioning" "docker_check" "Final check if Docker is working"
if ! docker info >/dev/null 2>&1; then
    notify_webhook "failed" "docker_failed" "Docker is not working. Detailed diagnostics"
    journalctl -u docker --no-pager -n 30 2>/dev/null || \
    cat /var/log/dockerd.log 2>/dev/null || \
    echo "No Docker logs available"
    
    echo "System information:"
    uname -a
    lsb_release -a
    
    exit 1
fi

# Install docker-compose (CLI-plugin)
notify_webhook "provisioning" "compose_install" "Installing Docker Compose"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSfSL "${docker_compose_url}" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/bin/docker-compose || true

# Install Buildx if missing
notify_webhook "provisioning" "buildx_install" "Installing Docker Buildx"
if ! docker buildx version >/dev/null 2>&1; then
    mkdir -p ~/.docker/cli-plugins
    curl -sSfSL "${buildx_url}" -o ~/.docker/cli-plugins/docker-buildx
    chmod +x ~/.docker/cli-plugins/docker-buildx
fi

# Debug: Show Docker information
notify_webhook "provisioning" "docker_success" "Docker installation completed successfully"
docker --version
docker-compose --version
docker buildx version

# ----------------------------------------------------------------------
#  Create Forgejo directory structure
# ----------------------------------------------------------------------
echo "[3/10] Preparing Forgejo directories..."
notify_webhook "provisioning" "forgejo_setup" "Creating directories"

mkdir -p "$FORGEJO_DIR"
cd "$FORGEJO_DIR"
mkdir -p data config ssl

# ----------------------------------------------------------------------
#  Create a custom app.ini with LFS configuration
# ----------------------------------------------------------------------
echo "[4/10] Creating custom app.ini..."
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
#  Docker-Compose file (using official Forgejo image)
# ----------------------------------------------------------------------
echo "[5/10] Generating docker-compose.yml..."
cat > docker-compose.yml <<EOF_COMPOSE
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
      retries: 6
EOF_COMPOSE

# ----------------------------------------------------------------------
#  Start the stack (Docker-Compose)
# ----------------------------------------------------------------------
echo "[6/10] Starting containers..."
docker compose up -d

# Wait until the container reports a healthy status (max ~2 min)
echo "Waiting for Forgejo container to become healthy..."
for i in $(seq 1 60); do
  STATUS=$(docker inspect --format='{{{{.State.Health.Status}}}}' forgejo 2>/dev/null || echo "none")
  if [ "$STATUS" = "healthy" ]; then
    echo "✅ Container is healthy"
    break
  fi
  sleep 2
done

# ----------------------------------------------------------------------
#  Firewall (UFW)
# ----------------------------------------------------------------------
echo "[7/10] Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "{FRONTEND_PORT}/tcp"
ufw --force enable

# ----------------------------------------------------------------------
#  SSL certificate acquisition
# ----------------------------------------------------------------------
echo "[8/10] Obtaining Let's Encrypt certificate..."
notify_webhook "provisioning" "ssl" "Running certbot"

mkdir -p /etc/letsencrypt
curl -sSf "{letsencrypt_options_url}" -o /etc/letsencrypt/options-ssl-nginx.conf
curl -sSf "{ssl_dhparams_url}" -o /etc/letsencrypt/ssl-dhparams.pem

if [ -x "$DNS_HOOK_SCRIPT" ]; then
  echo "Using DNS-01 challenge via hook script"
  chmod +x "$DNS_HOOK_SCRIPT"
  certbot certonly --manual \\
    --preferred-challenges dns \\
    --manual-auth-hook "$DNS_HOOK_SCRIPT add" \\
    --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" \\
    --agree-tos --email "{ADMIN_EMAIL}" \\
    -d "{DOMAIN_NAME}" -d "*.{DOMAIN_NAME}" \\
    --non-interactive \\
    --manual-public-ip-logging-ok
else
  echo "Falling back to standalone HTTP-01 challenge (wildcard not supported)"
  systemctl stop nginx || true
  certbot certonly --standalone \\
    --preferred-challenges http \\
    --agree-tos --email "{ADMIN_EMAIL}" \\
    -d "{DOMAIN_NAME}" \\
    --non-interactive
  systemctl start nginx
fi

# ----------------------------------------------------------------------
#  Nginx reverse-proxy configuration
# ----------------------------------------------------------------------
echo "[9/10] Configuring Nginx..."
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
echo "[10/10] Performing final checks..."
notify_webhook "provisioning" "verification" "Running post-install checks"

if ! docker ps --filter "name=forgejo" --filter "status=running" | grep -q forgejo; then
  echo "ERROR: Forgejo container is not running!"
  docker logs forgejo || true
  notify_webhook "failed" "verification" "Forgejo container not running"
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

HTTPS_CODE=$(curl -k -s -o /dev/null -w "%{{http_code}}" https://{DOMAIN_NAME} || echo "000")
if [[ "$HTTPS_CODE" != "200" ]]; then
  echo "ERROR: HTTPS check returned $HTTPS_CODE (expected 200)"
  notify_webhook "failed" "verification" "HTTPS endpoint not reachable"
  exit 1
fi

# ----------------------------------------------------------------------
#  Wait for Forgejo's web UI to be ready
# ----------------------------------------------------------------------
echo "Waiting for Forgejo UI to become ready..."
while ! curl -s http://localhost:{FRONTEND_PORT} | grep -q "Initial configuration"; do
  sleep 5
done

notify_webhook "completed" "finished" "Forgejo deployment succeeded"

cat <<EOF_FINAL
=============================================
✅ Forgejo Setup Complete!
---------------------------------------------
🔗 Access URL     : https://{DOMAIN_NAME}
👤 Admin login    : {ADMIN_EMAIL}
🔑 Admin password : {ADMIN_PASSWORD}
---------------------------------------------
⚙️ Useful commands
   - Check container: docker ps --filter "name=forgejo"
   - View logs      : docker logs -f forgejo
   - Nginx status   : systemctl status nginx
   - Certbot list   : certbot certificates
   - Firewall status: ufw status numbered
---------------------------------------------
⚠️ Post-install notes
1️⃣  First visit https://{DOMAIN_NAME} to finish the Forgejo web-setup.
2️⃣  If you ever see the default Nginx page:
      sudo rm -f /etc/nginx/sites-enabled/default
      sudo systemctl restart nginx
3️⃣  To renew the certificate later simply run:
      sudo certbot renew --quiet && sudo systemctl reload nginx
---------------------------------------------
Enjoy your new Forgejo instance!
=============================================
EOF_FINAL
"""
    return script_template