def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
    WEBHOOK_URL="",
):
    """
    Return a Bash‑script string that provisions a Forgejo instance behind Nginx,
    obtains a Let’s Encrypt certificate, and (optionally) posts status updates
    to a webhook URL.

    The script has been updated to:

    • Install ``ufw`` (the original script tried to call it without installing it).
    • Use ``docker compose`` (no ``--wait`` flag – it’s not universally supported).
    • Open firewall ports with separate ``ufw`` commands (avoids syntax errors).
    • Obtain certificates with ``certbot certonly --standalone`` when no DNS‑hook
      is provided (the original ``--nginx`` fallback ran before the site existed).
    • Verify the HTTPS endpoint rather than the plain‑HTTP port.
    • Wait for the Forgejo container to report a healthy status before final checks.
    • Minor robustness tweaks (``set -o pipefail``, Docker‑group refresh, etc.).
    """
    # ----- URLs that can be overridden if needed -----
    forgejo_git = "https://codeberg.org/forgejo/forgejo.git"
    docker_compose_url = (
        "https://github.com/docker/compose/releases/download/v2.38.1/docker-compose-linux-x86_64"
    )
    buildx_url = (
        "https://github.com/docker/buildx/releases/download/v0.11.2/buildx-v0.11.2.linux-amd64"
    )
    letsencrypt_options_url = (
        "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/"
        "certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    )
    ssl_dhparams_url = (
        "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"
    )

    # Misc constants
    MAX_UPLOAD_FILE_SIZE_IN_MB = 1024
    LFS_MAX_FILE_SIZE_IN_BYTES = MAX_UPLOAD_FILE_SIZE_IN_MB * 1024 * 1024
    forgejo_dir = "/opt/forgejo"

    # ----- Webhook helper (if a URL is supplied) -----
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
  # No webhook URL configured – silently ignore
  return 0
}
'''

    # ----------------------------------------------------------------------
    # The actual script – heavily commented so you can see what each part does
    # ----------------------------------------------------------------------
    script_template = f"""#!/usr/bin/env bash
set -e
set -o pipefail

# ----------------------------------------------------------------------
#  Helper: webhook notification
# ----------------------------------------------------------------------
{webhook_notification}

# ----------------------------------------------------------------------
#  Input validation
# ----------------------------------------------------------------------
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
  echo "ERROR: Invalid domain name \"{DOMAIN_NAME}\""
  notify_webhook "failed" "validation" "Invalid domain format"
  exit 1
fi

notify_webhook "provisioning" "starting" "Beginning Forgejo set‑up"

# ----------------------------------------------------------------------
#  Global configuration variables (used throughout the script)
# ----------------------------------------------------------------------
DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
ADMIN_PASSWORD="{ADMIN_PASSWORD}"
FORGEJO_HOST_PORT="{PORT}"      # port that the container will publish on the host
FORGEJO_DIR="{forgejo_dir}"
DNS_HOOK_SCRIPT="{DNS_HOOK_SCRIPT}"
WEBHOOK_URL="{WEBHOOK_URL}"

# Random secret for Git‑LFS JWT
LFS_JWT_SECRET=$(openssl rand -hex 32)

# ----------------------------------------------------------------------
#  System updates & required packages
# ----------------------------------------------------------------------
echo "[1/10] Updating system and installing dependencies..."
notify_webhook "provisioning" "system_update" "Running apt‑get update & install"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq \\
    curl git docker.io nginx certbot \\
    python3-pip python3-venv jq make net-tools \\
    python3-certbot-nginx git-lfs openssl ufw

# ----------------------------------------------------------------------
#  Docker configuration
# ----------------------------------------------------------------------
echo "[2/10] Installing Docker Compose plugin & preparing Docker"
notify_webhook "provisioning" "docker_setup" "Installing docker‑compose plugin"

# Install docker‑compose (CLI‑plugin)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSfSL "{docker_compose_url}" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Make sure the plugin is on the PATH (Ubuntu links /usr/bin/docker-compose → the plugin)
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/bin/docker-compose || true

# Add the current user to the docker group so ‘docker’ works without sudo
usermod -aG docker ${{SUDO_USER:-$USER}} || true
newgrp docker 2>/dev/null || true   # refresh group membership in the current shell

systemctl enable --now docker
# Simple loop that waits until the daemon reports it’s ready
until docker info >/dev/null 2>&1; do
  sleep 2
done

# Install Buildx (only if it’s missing)
if ! docker buildx version >/dev/null 2>&1; then
  echo "[2/10] Installing Docker Buildx ..."
  mkdir -p ~/.docker/cli-plugins
  curl -sSfSL "{buildx_url}" -o ~/.docker/cli-plugins/docker-buildx
  chmod +x ~/.docker/cli-plugins/docker-buildx
fi

# ----------------------------------------------------------------------
#  Forgejo source checkout
# ----------------------------------------------------------------------
echo "[3/10] Preparing Forgejo source tree ..."
notify_webhook "provisioning" "forgejo_source" "Cloning/fetching Forgejo"

mkdir -p "$FORGEJO_DIR"
cd "$FORGEJO_DIR"

# If a .git directory already exists, just pull the latest changes;
# otherwise clone a fresh copy.
if [ -d ".git" ]; then
  echo "Existing repository – pulling latest..."
  git pull
elif [ -n "$(ls -A . 2>/dev/null)" ]; then
  echo "Directory not empty – moving contents to a backup and cloning fresh"
  mkdir -p ../forgejo_backup
  mv ./* ../forgejo_backup/ || true
  git clone "{forgejo_git}" .
else
  echo "Cloning Forgejo repository..."
  git clone "{forgejo_git}" .
fi

# Initialise Git‑LFS (required for some assets in the repo)
git lfs install
git lfs pull || true

# ----------------------------------------------------------------------
#  Build a local Forgejo Docker image (so we control the tag)
# ----------------------------------------------------------------------
echo "[4/10] Building Forgejo Docker image ..."
notify_webhook "provisioning" "docker_build" "Running docker‑buildx"

docker buildx create --use --name forgejo-builder || true
docker buildx inspect --bootstrap

docker buildx build --platform linux/amd64 -t forgejo:local --load .

# ----------------------------------------------------------------------
#  Docker‑Compose file (uses the image built above)
# ----------------------------------------------------------------------
echo "[5/10] Generating docker‑compose.yml ..."
notify_webhook "provisioning" "compose_file" "Writing docker‑compose.yml"

cat > docker-compose.yml <<'EOF_COMPOSE'
version: "3.8"

services:
  server:
    image: forgejo:local
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
      - "${FORGEJO_HOST_PORT}:3000"
      - "222:22"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 10s
      timeout: 5s
      retries: 6
EOF_COMPOSE

# ----------------------------------------------------------------------
#  Start the container stack
# ----------------------------------------------------------------------
echo "[6/10] Starting Forgejo container stack ..."
notify_webhook "provisioning" "docker_up" "Running docker compose up"

docker compose up -d

# Wait until the health‑check reports “healthy”
echo "Waiting for the Forgejo container to become healthy..."
for i in $(seq 1 30); do
  STATUS=$(docker inspect --format='{{{{.State.Health.Status}}}}' forgejo 2>/dev/null || echo "none")
  if [ "$STATUS" = "healthy" ]; then
    echo "Container is healthy."
    break
  fi
  echo "  ($i/30) still not healthy – sleeping 2s ..."
  sleep 2
done

# ----------------------------------------------------------------------
#  Firewall configuration (UFW)
# ----------------------------------------------------------------------
echo "[7/10] Configuring the firewall ..."
notify_webhook "provisioning" "firewall" "Opening required ports"

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "${FORGEJO_HOST_PORT}/tcp"
ufw --force enable

# ----------------------------------------------------------------------
#  SSL certificate acquisition
# ----------------------------------------------------------------------
echo "[8/10] Obtaining Let’s Encrypt certificate ..."
notify_webhook "provisioning" "ssl" "Running certbot"

mkdir -p /etc/letsencrypt
curl -sSf "{letsencrypt_options_url}" -o /etc/letsencrypt/options-ssl-nginx.conf
curl -sSf "{ssl_dhparams_url}" -o /etc/letsencrypt/ssl-dhparams.pem

if [ -x "$DNS_HOOK_SCRIPT" ]; then
  echo "Using DNS‑01 challenge via hook script"
  notify_webhook "provisioning" "ssl_dns" "Running DNS‑01 challenge"
  certbot certonly --manual \\
    --preferred-challenges dns \\
    --manual-auth-hook "$DNS_HOOK_SCRIPT add" \\
    --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" \\
    --agree-tos --email "{ADMIN_EMAIL}" \\
    -d "{DOMAIN_NAME}" -d "*.{DOMAIN_NAME}" \\
    --non-interactive \\
    --manual-public-ip-logging-ok
else
  echo "Falling back to standalone HTTP‑01 challenge (no DNS hook found)"
  notify_webhook "provisioning" "ssl_standalone" "Running certbot in standalone mode"
  # Stop any service that may already be listening on port 80 (Nginx isn’t started yet)
  certbot certonly --standalone \\
    --preferred-challenges http \\
    --agree-tos --email "{ADMIN_EMAIL}" \\
    -d "{DOMAIN_NAME}" -d "*.{DOMAIN_NAME}" \\
    --non-interactive
fi

# ----------------------------------------------------------------------
#  Nginx reverse‑proxy configuration
# ----------------------------------------------------------------------
echo "[9/10] Configuring Nginx ..."
notify_webhook "provisioning" "nginx_config" "Writing /etc/nginx/sites‑available/forgejo"

cat > /etc/nginx/sites-available/forgejo <<'EOF_NGINX'
map $http_upgrade $connection_upgrade {{
    default upgrade;
    ''      close;
}}

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
        proxy_pass http://127.0.0.1:${{FORGEJO_HOST_PORT}};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
    }}
}}
EOF_NGINX

ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# ----------------------------------------------------------------------
#  Final verification
# ----------------------------------------------------------------------
echo "[10/10] Performing final sanity checks ..."
notify_webhook "provisioning" "verification" "Running post‑install checks"

# Verify the container is up & healthy (already checked, but double‑check)
if ! docker ps --filter "name=forgejo" --filter "status=running" | grep -q forgejo; then
  echo "ERROR: Forgejo container is not running!"
  docker logs forgejo || true
  notify_webhook "failed" "verification" "Forgejo container not running"
  exit 1
fi

# Verify Nginx config (we already tested with nginx -t)
# Verify that the SSL certificate files exist
if [ ! -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
  echo "ERROR: SSL certificate not found!"
  notify_webhook "failed" "verification" "SSL certificate missing"
  exit 1
fi

# Verify HTTPS endpoint (ignore certificate verification on the first run)
HTTPS_CODE=$(curl -k -s -o /dev/null -w "%{{http_code}}" https://{DOMAIN_NAME} || echo "000")
if [[ "$HTTPS_CODE" != "200" ]]; then
  echo "ERROR: HTTPS request returned $HTTPS_CODE (expected 200)"
  notify_webhook "failed" "verification" "HTTPS endpoint not reachable"
  exit 1
fi

# ----------------------------------------------------------------------
#  All done – print useful information
# ----------------------------------------------------------------------
notify_webhook "completed" "finished" "Forgejo deployment succeeded"

cat <<'EOF_FINAL'
=============================================
✅ Forgejo Setup Complete!
---------------------------------------------
🔗 Access URL     : https://{DOMAIN_NAME}
👤 Admin login    : {ADMIN_EMAIL}
🔑 Admin password: {ADMIN_PASSWORD}
---------------------------------------------
⚙️ Useful commands
   - Check container: docker ps --filter "name=forgejo"
   - View logs       : docker logs -f forgejo
   - Nginx status    : systemctl status nginx
   - Certbot list    : certbot certificates
   - Firewall rules  : ufw status numbered
---------------------------------------------
⚠️  Post‑install notes
   1. First visit https://{DOMAIN_NAME} to finish the Forgejo web‑setup.
   2. If you ever see the default Nginx page, run:
        sudo rm -f /etc/nginx/sites-enabled/default
        sudo systemctl restart nginx
   3. If the certificate expires or you need to renew, simply run:
        sudo certbot renew --quiet && sudo systemctl reload nginx
---------------------------------------------
Enjoy your new Forgejo instance!
=============================================
EOF_FINAL
"""
    return script_template