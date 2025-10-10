import textwrap

def generate_bytestash_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
    WEBHOOK_URL="",
    ALLOW_EMBED_WEBSITE="",
    location="",
    resource_group="",
    UPLOAD_SIZE_MB=1024
):
    """
    Returns a full 15-step Bytestash provisioning script in your style.
    """

    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__ALLOW_EMBED_WEBSITE__": ALLOW_EMBED_WEBSITE,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__BYTESTASH_DIR__": "/opt/bytestash",
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__MAX_UPLOAD_SIZE_MB__": f"{UPLOAD_SIZE_MB}M",
        "__MAX_UPLOAD_SIZE_BYTES__": str(UPLOAD_SIZE_MB * 1024 * 1024),
    }

    # ------------------ SCRIPT TEMPLATE ------------------
    script_template = textwrap.dedent(r"""
#!/bin/bash
set -euo pipefail

LOG_FILE="/var/log/bytestash_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

__WEBHOOK_FUNCTION__

DOMAIN="__DOMAIN__"
ADMIN_EMAIL="__ADMIN_EMAIL__"
ADMIN_PASSWORD="__ADMIN_PASSWORD__"
PORT="__PORT__"
BYTESTASH_DIR="__BYTESTASH_DIR__"
DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"
WEBHOOK_URL="__WEBHOOK_URL__"
ALLOW_EMBED_WEBSITE="__ALLOW_EMBED_WEBSITE__"
MAX_UPLOAD_SIZE_MB="__MAX_UPLOAD_SIZE_MB__"
MAX_UPLOAD_SIZE_BYTES="__MAX_UPLOAD_SIZE_BYTES__"

# Generate JWT secret without openssl
if [ -z "$BYTESTASH_JWT_SECRET" ]; then
    BYTESTASH_JWT_SECRET=$(head -c 32 /dev/urandom | xxd -p)
fi
echo "[0/15] JWT secret generated"
notify_webhook "provisioning" "jwt_generated" "JWT secret generated"
sleep 2

# --- Step 1: Validate Inputs ---
echo "[1/15] Validating inputs..."
notify_webhook "provisioning" "validation" "Validating domain and port"
sleep 2
if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
    echo "ERROR: Invalid domain format: $DOMAIN"
    notify_webhook "failed" "validation" "Invalid domain format: $DOMAIN"
    exit 1
fi
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
    echo "ERROR: Invalid port number: $PORT"
    notify_webhook "failed" "validation" "Invalid port: $PORT"
    exit 1
fi
sleep 1

# --- Step 2: System dependencies ---
echo "[2/15] Installing system dependencies..."
notify_webhook "provisioning" "system_dependencies" "Installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq make ufw xxd docker.io docker-compose
sleep 3

# --- Step 3: Create directories ---
echo "[3/15] Creating Bytestash directories..."
notify_webhook "provisioning" "directories" "Creating Bytestash directories"
mkdir -p "$BYTESTASH_DIR"/{data,config,ssl}
chown -R 1000:1000 "$BYTESTASH_DIR"
sleep 2

# --- Step 4: Docker Compose ---
echo "[4/15] Creating Docker Compose configuration..."
notify_webhook "provisioning" "docker_compose" "Creating docker-compose.yml"
cat > "$BYTESTASH_DIR/docker-compose.yml" <<EOF
version: "3.8"
services:
  bytestash:
    image: bytestash/bytestash:latest
    container_name: bytestash
    restart: always
    environment:
      - BYTESTASH_ADMIN_EMAIL=$ADMIN_EMAIL
      - BYTESTASH_ADMIN_PASSWORD=$ADMIN_PASSWORD
      - BYTESTASH_JWT_SECRET=$BYTESTASH_JWT_SECRET
      - BYTESTASH_MAX_FILE_SIZE=$MAX_UPLOAD_SIZE_BYTES
    volumes:
      - ./data:/data
      - ./config:/config
      - ./ssl:/ssl
    ports:
      - "$PORT:8080"
EOF
sleep 2

# --- Step 5: Start Docker container ---
echo "[5/15] Starting Bytestash container..."
notify_webhook "provisioning" "container_start" "Starting Bytestash container"
cd "$BYTESTASH_DIR"
docker-compose up -d
sleep 5

# --- Step 6: Configure firewall ---
echo "[6/15] Configuring firewall..."
notify_webhook "provisioning" "firewall" "Setting up firewall rules"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "$PORT"/tcp
ufw --force enable
sleep 2

# --- Step 7: Nginx setup ---
echo "[7/15] Configuring Nginx reverse proxy..."
notify_webhook "provisioning" "nginx" "Setting up Nginx"
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/bytestash <<'EOF_NGINX'
server {
    listen 80;
    server_name __DOMAIN__;
    location / {
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF_NGINX
ln -sf /etc/nginx/sites-available/bytestash /etc/nginx/sites-enabled/bytestash
nginx -t && systemctl reload nginx
sleep 2

# --- Step 8: SSL certificate ---
echo "[8/15] Obtaining SSL certificate..."
notify_webhook "provisioning" "ssl" "Obtaining SSL certificate"
mkdir -p /etc/letsencrypt
curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem
certbot --nginx -d "__DOMAIN__" --non-interactive --agree-tos -m "$ADMIN_EMAIL"
sleep 3

# --- Step 9: Health check ---
echo "[9/15] Checking container health..."
notify_webhook "provisioning" "health_check" "Checking container status"
READY_TIMEOUT=300
SLEEP_INTERVAL=5
elapsed=0
while [ $elapsed -lt $READY_TIMEOUT ]; do
    state=$(docker inspect -f '{{.State.Status}}' bytestash 2>/dev/null || echo "unknown")
    if [ "$state" = "running" ]; then
        break
    fi
    sleep $SLEEP_INTERVAL
    elapsed=$((elapsed + SLEEP_INTERVAL))
done
if [ "$state" != "running" ]; then
    echo "ERROR: Bytestash container not running!"
    docker logs bytestash --tail=50
    notify_webhook "failed" "container_health" "Bytestash container not running"
    exit 1
fi
sleep 2

# --- Step 10: Wait for readiness (HTTP probe) ---
echo "[10/15] Waiting for Bytestash readiness..."
notify_webhook "provisioning" "http_probe" "Waiting for HTTP readiness"
elapsed=0
READY=false
while [ $elapsed -lt $READY_TIMEOUT ]; do
    if curl -fsS "http://127.0.0.1:8080" >/dev/null 2>&1; then
        READY=true
        break
    fi
    sleep $SLEEP_INTERVAL
    elapsed=$((elapsed + SLEEP_INTERVAL))
done
if [ "$READY" = false ]; then
    echo "ERROR: Bytestash not responding on HTTP"
    notify_webhook "failed" "http_probe" "Bytestash not responding on HTTP"
    exit 1
fi
sleep 2

# --- Step 11: Setup Cron for SSL renewal ---
echo "[11/15] Setting up SSL renewal cron..."
notify_webhook "provisioning" "cron" "Setting up SSL renewal cron"
(crontab -l 2>/dev/null | grep -v -F "__CERTBOT_CRON__" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
sleep 1

# --- Step 12: Logging completion ---
echo "[12/15] Logging completion..."
notify_webhook "provisioning" "completed" "Bytestash container deployed and ready"
sleep 1

# --- Step 13: Display access info ---
echo "[13/15] Access details:"
echo "URL: https://__DOMAIN__"
echo "Admin email: $ADMIN_EMAIL"
notify_webhook "provisioning" "access_info" "Displayed access info"
sleep 1

# --- Step 14: Test Nginx SSL ---
echo "[14/15] Testing Nginx SSL..."
HTTPS_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://__DOMAIN__)
echo "HTTPS returned: $HTTPS_CODE"
notify_webhook "provisioning" "ssl_test" "HTTPS returned $HTTPS_CODE"
sleep 1

# --- Step 15: Final summary ---
echo "[15/15] Bytestash provisioning complete!"
notify_webhook "provisioning" "bytestash_installed" "✅ Bytestash setup completed successfully"
sleep 2
""")

    # ------------------ WEBHOOK FUNCTION HANDLING ------------------
    if tokens["__WEBHOOK_URL__"]:
        webhook_fn = textwrap.dedent(r"""
            notify_webhook() {
                local status="$1"
                local step="$2"
                local message="$3"
                JSON_PAYLOAD=$(cat <<JSON_EOF
            {
                "vm_name": "$(hostname)",
                "status": "$status",
                "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
                "location": "__LOCATION__",
                "resource_group": "__RESOURCE_GROUP__",
                "details": {
                    "step": "$step",
                    "message": "$message"
                }
            }
            JSON_EOF
        )
                curl -s -X POST "__WEBHOOK_URL__" \
                    -H "Content-Type: application/json" \
                    -d "$JSON_PAYLOAD" \
                    --retry 2 --retry-delay 5 --connect-timeout 10 --max-time 30 || true
            }
        """)
    else:
        webhook_fn = textwrap.dedent(r"""
            notify_webhook() {
                # Webhook disabled - stub function
                return 0
            }
        """)

    # ------------------ TOKEN REPLACEMENT ------------------
    final = script_template.replace("__WEBHOOK_FUNCTION__", webhook_fn)

    for token, value in tokens.items():
        final = final.replace(token, value)

    final = final.replace("__LOCATION__", tokens["__LOCATION__"])
    final = final.replace("__RESOURCE_GROUP__", tokens["__RESOURCE_GROUP__"])
    final = final.replace("__WEBHOOK_URL__", tokens["__WEBHOOK_URL__"])

    # CERTBOT_CRON token
    certbot_cron = "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
    final = final.replace("__CERTBOT_CRON__", certbot_cron)

    return final
