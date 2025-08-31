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

  curl -s -X POST \
    "${{WEBHOOK_URL}}" \
    -H "Content-Type: application/json" \
    -d "$JSON_PAYLOAD" \
    --connect-timeout 10 \
    --max-time 30 \
    --retry 2 \
    --retry-delay 5 \
    --output /dev/null \
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

# ========== SYSTEM SETUP ==========
echo "[1/9] System updates and dependencies..."
notify_webhook "provisioning" "system_update" "Running apt-get update & install"

for i in {{1..5}}; do
    if apt-get update; then
        break
    fi
    sleep 10
    if [ $i -eq 5 ]; then
        notify_webhook "failed" "system_update" "Failed to update package lists"
        exit 1
    fi
done

for i in {{1..5}}; do
    if DEBIAN_FRONTEND=noninteractive apt-get install -y \
        curl git nginx certbot \
        python3-pip python3-venv jq make net-tools \
        python3-certbot-nginx git git-lfs openssl ufw; then
        break
    fi
    sleep 10
    if [ $i -eq 5 ]; then
        notify_webhook "failed" "system_update" "Failed to install packages"
        exit 1
    fi
done

# ========== DOCKER SETUP ==========
echo "[2/9] Configuring Docker..."
notify_webhook "provisioning" "docker_setup" "Installing Docker & CLI plugins"

for i in {{1..5}}; do
    if apt-get install -y docker.io docker-compose-plugin; then
        break
    fi
    sleep 10
    if [ $i -eq 5 ]; then
        notify_webhook "failed" "docker_setup" "Failed to install Docker"
        exit 1
    fi
done

CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" != "root" ]; then
    usermod -aG docker "$CURRENT_USER" || true
fi

echo "Starting Docker service..."
for i in {{1..10}}; do
    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable docker
        if systemctl start docker; then
            break
        fi
    elif command -v service >/dev/null 2>&1; then
        if service docker start; then
            break
        fi
    else
        nohup dockerd > /var/log/dockerd.log 2>&1 &
    fi
    if [ $i -eq 10 ]; then
        notify_webhook "failed" "docker_start" "Failed to start Docker"
        exit 1
    fi
    sleep 5
done

timeout=120
while [ $timeout -gt 0 ]; do
    if docker info >/dev/null 2>&1; then
        break
    fi
    sleep 5
    timeout=$((timeout - 5))
done

if [ $timeout -eq 0 ]; then
    notify_webhook "failed" "docker_failed" "Docker startup timeout"
    exit 1
fi

mkdir -p /usr/lib/docker/cli-plugins
curl -fSL "{docker_compose_url}" -o /usr/lib/docker/cli-plugins/docker-compose
chmod +x /usr/lib/docker/cli-plugins/docker-compose

curl -fSL "{buildx_url}" -o /usr/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/lib/docker/cli-plugins/docker-buildx

echo "Verifying Docker installation..."
docker --version || (echo "ERROR: Docker not working" && exit 1)

if command -v docker-compose >/dev/null 2>&1; then
    docker-compose --version || (echo "ERROR: docker-compose v1 not working" && exit 1)
elif docker compose version >/dev/null 2>&1; then
    docker compose version || (echo "ERROR: docker compose v2 not working" && exit 1)
else
    echo "ERROR: Neither docker-compose nor docker compose found"
    exit 1
fi

docker buildx version || (echo "ERROR: Docker Buildx not working" && exit 1)

# ========== FORGEJO SETUP ==========
echo "[3/9] Setting up Forgejo..."
notify_webhook "provisioning" "forgejo_setup" "Configuring Forgejo"

mkdir -p "$FORGEJO_DIR"
cat > "$FORGEJO_DIR/docker-compose.yml" <<EOL
version: '3'
services:
  db:
    image: postgres:13
    restart: always
    environment:
      POSTGRES_USER: forgejo
      POSTGRES_PASSWORD: forgejopassword
      POSTGRES_DB: forgejo
    volumes:
      - db-data:/var/lib/postgresql/data

  forgejo:
    image: codeberg.org/forgejo/forgejo:latest
    restart: always
    depends_on:
      - db
    ports:
      - "${{PORT}}:3000"
    environment:
      USER_UID: 1000
      USER_GID: 1000
      DB_TYPE: postgres
      DB_HOST: db
      DB_NAME: forgejo
      DB_USER: forgejo
      DB_PASSWD: forgejopassword
      LFS_JWT_SECRET: ${{LFS_JWT_SECRET}}
      MAX_UPLOAD_FILE_SIZE: {MAX_UPLOAD_FILE_SIZE_IN_MB}
      LFS_MAX_FILE_SIZE: {LFS_MAX_FILE_SIZE_IN_BYTES}
    volumes:
      - forgejo-data:/data

volumes:
  db-data:
  forgejo-data:
EOL

cd "$FORGEJO_DIR"
docker compose up -d

# ========== NGINX CONFIGURATION ==========
echo "[4/9] Configuring Nginx..."
notify_webhook "provisioning" "nginx_setup" "Setting up reverse proxy"

cat > /etc/nginx/sites-available/forgejo <<EOL
server {{
    listen 80;
    server_name ${{DOMAIN_NAME}};

    location / {{
        proxy_pass http://127.0.0.1:${{PORT}};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
EOL

ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/forgejo
nginx -t && systemctl reload nginx

# ========== SSL CONFIGURATION ==========
echo "[5/9] Obtaining SSL certificates..."
notify_webhook "provisioning" "ssl_setup" "Requesting Let's Encrypt cert"

mkdir -p /etc/letsencrypt
curl -o /etc/letsencrypt/options-ssl-nginx.conf {letsencrypt_options_url}
curl -o /etc/letsencrypt/ssl-dhparams.pem {ssl_dhparams_url}

certbot --nginx --non-interactive --agree-tos -m "$ADMIN_EMAIL" -d "$DOMAIN_NAME"

# ========== FIREWALL ==========
echo "[6/9] Configuring firewall..."
notify_webhook "provisioning" "firewall_setup" "Configuring ufw"

ufw allow OpenSSH
ufw allow 'Nginx Full'
echo "y" | ufw enable || true

# ========== VERIFY ==========
echo "[7/9] Verifying deployment..."
notify_webhook "provisioning" "verification" "Checking service status"

sleep 20
if ! curl -fs "https://${{DOMAIN_NAME}}/" >/dev/null; then
    notify_webhook "failed" "verification" "Forgejo not reachable"
    exit 1
fi

# ========== ADMIN USER ==========
echo "[8/9] Creating admin user..."
notify_webhook "provisioning" "admin_setup" "Creating admin account"

for i in {{1..10}}; do
    docker compose exec -T forgejo bash -c "gitea admin user create --username admin --password '${{ADMIN_PASSWORD}}' --email '${{ADMIN_EMAIL}}' --admin || true"
    if [ $? -eq 0 ]; then
        break
    fi
    sleep 10
done

# ========== DONE ==========
echo "[9/9] Setup complete!"
notify_webhook "succeeded" "completed" "Forgejo installation finished"

echo "Forgejo is ready at: https://${{DOMAIN_NAME}}"
echo "Admin user: admin / ${{ADMIN_PASSWORD}}"

echo "Installation log saved to: $LOG_FILE"
"""
    return script_template