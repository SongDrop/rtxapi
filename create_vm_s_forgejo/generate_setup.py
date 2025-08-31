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
    docker_gpg_url = "https://download.docker.com/linux/ubuntu/gpg"
    docker_repo = "https://download.docker.com/linux/ubuntu"
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
        webhook_notification = '''
notify_webhook() {
  return 0
}
'''

    # ========== Full Bash Script Template ==========
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

# Validate domain
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
echo "[1/9] Updating system and installing dependencies..."
for i in {{1..5}}; do
    if apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \\
        curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx git-lfs openssl ufw ca-certificates lsb-release gnupg; then
        break
    fi
    sleep 10
    if [ $i -eq 5 ]; then
        notify_webhook "failed" "system_update" "Failed to install packages"
        exit 1
    fi
done

# ========== DOCKER SETUP ==========
echo "[2/9] Installing Docker from official repo..."
apt-get remove -y docker docker-engine docker.io containerd runc || true
mkdir -p /etc/apt/keyrings
curl -fsSL {docker_gpg_url} | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
ARCH=$(dpkg --print-architecture)
CODENAME=$(lsb_release -cs)
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] {docker_repo} $CODENAME stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" != "root" ]; then usermod -aG docker "$CURRENT_USER" || true; fi

systemctl enable docker
systemctl start docker
timeout=120
while [ $timeout -gt 0 ]; do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 5
    timeout=$((timeout-5))
done
if [ $timeout -eq 0 ]; then notify_webhook "failed" "docker_failed" "Docker did not start"; exit 1; fi

docker --version
if command -v docker-compose >/dev/null 2>&1; then docker-compose --version; else docker compose version; fi
docker buildx version

# ========== FORGEJO SETUP ==========
echo "[3/9] Setting up Forgejo directories and Docker Compose..."
mkdir -p "$FORGEJO_DIR"
cat > "$FORGEJO_DIR/docker-compose.yml" <<EOF
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
      LFS_JWT_SECRET: $LFS_JWT_SECRET
    volumes:
      - forgejo-data:/data

volumes:
  db-data:
  forgejo-data:
EOF

cd "$FORGEJO_DIR"
docker compose up -d

# ========== NGINX ==========
echo "[4/9] Configuring Nginx..."
cat > /etc/nginx/sites-available/forgejo <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/forgejo
nginx -t && systemctl reload nginx

# ========== SSL ==========
echo "[5/9] Obtaining SSL certificates..."
mkdir -p /etc/letsencrypt
curl -o /etc/letsencrypt/options-ssl-nginx.conf {letsencrypt_options_url}
curl -o /etc/letsencrypt/ssl-dhparams.pem {ssl_dhparams_url}
certbot --nginx --non-interactive --agree-tos -m "$ADMIN_EMAIL" -d "$DOMAIN_NAME"

# ========== FIREWALL ==========
echo "[6/9] Configuring firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
echo "y" | ufw enable || true

# ========== VERIFY ==========
echo "[7/9] Verifying deployment..."
sleep 20
curl -fs "https://$DOMAIN_NAME/" || notify_webhook "failed" "verification" "Forgejo not reachable"

# ========== ADMIN USER ==========
echo "[8/9] Creating admin user..."
for i in {1..10}; do
    docker compose exec -T forgejo bash -c "gitea admin user create --username admin --password '$ADMIN_PASSWORD' --email '$ADMIN_EMAIL' --admin || true"
    if [ $? -eq 0 ]; then break; fi
    sleep 10
done

# ========== COMPLETION ==========
echo "[9/9] Forgejo setup complete!"
notify_webhook "succeeded" "completed" "Forgejo installation finished"
echo "Forgejo is ready at: https://$DOMAIN_NAME"
echo "Admin user: admin / $ADMIN_PASSWORD"
echo "Installation log: $LOG_FILE"
"""
    return script_template
