import textwrap

def generate_plane_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    PORT=80,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DATA_DIR="/opt/plane",
    DOCKER_COMPOSE_VERSION="v2.27.0",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a full bash provisioning script for Plane, in Forgejo style.
    """

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__PORT__": str(PORT),
        "__DATA_DIR__": DATA_DIR,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DOCKER_COMPOSE_VERSION__": DOCKER_COMPOSE_VERSION,
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__LETSENCRYPT_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Plane Provisioning Script (Forgejo style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/plane_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    PORT="__PORT__"
    DATA_DIR="__DATA_DIR__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"

    echo "[1/15] Starting Plane provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Plane setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/15] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and port"

    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "ERROR: Invalid domain $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain format"
        exit 1
    fi

    if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
        echo "ERROR: Invalid port $PORT"
        notify_webhook "failed" "validation" "Invalid port number"
        exit 1
    fi

    # ========== SYSTEM DEPENDENCIES ==========
    echo "[3/15] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get upgrade -y -q
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx openssl ufw

    # ========== DOCKER INSTALLATION ==========
    echo "[4/15] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    apt-get install -y -q ca-certificates curl gnupg lsb-release || {
        notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
        exit 1
    }

    apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

    mkdir -p /etc/apt/keyrings
    if ! curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; then
        echo "❌ Failed to download Docker GPG key"
        notify_webhook "failed" "docker_gpg" "Failed to download Docker GPG key"
        exit 1
    fi
    chmod a+r /etc/apt/keyrings/docker.gpg

    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list

    for i in {1..3}; do
        if apt-get update -q && apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
            break
        fi
        echo "⚠️ Docker install attempt $i failed; retrying..."
        sleep 5
[ $i -eq 3 ] && {
            echo "❌ Docker installation failed after 3 attempts"
            notify_webhook "failed" "docker_install" "Docker install failed after 3 attempts"
            exit 1
        }
    done

    systemctl enable docker
    systemctl start docker

    # ========== DOCKER COMPOSE ==========
    echo "[5/15] Installing Docker Compose..."
    notify_webhook "provisioning" "docker_compose_install" "Installing Docker Compose plugin"
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -fsSL "https://github.com/docker/compose/releases/download/__DOCKER_COMPOSE_VERSION__/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/bin/docker-compose || true
    docker --version
    docker-compose --version
    systemctl enable --now docker

    # ========== PLANE DIRECTORY ==========
    echo "[6/15] Setting up Plane directory..."
    notify_webhook "provisioning" "directory_setup" "Creating Plane directory"
    mkdir -p "$DATA_DIR"
    chown -R 1000:1000 "$DATA_DIR"
    cd "$DATA_DIR"

    # ========== PLANE INSTALL ==========
    echo "[7/15] Downloading and running Plane setup..."
    notify_webhook "provisioning" "plane_install" "Downloading Plane setup script"
    curl -fsSL -o setup.sh "https://github.com/makeplane/plane/releases/latest/download/setup.sh"
    chmod +x setup.sh
    ./setup.sh <<EOF
1
8
EOF
    notify_webhook "provisioning" "plane_install" "Plane installed successfully"

    # ========== FIREWALL ==========
    echo "[8/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable

    # ========== SSL CERTIFICATE ==========
    echo "[9/15] Configuring SSL..."
    notify_webhook "provisioning" "ssl" "Obtaining Let's Encrypt certificate"
    mkdir -p /etc/letsencrypt
    curl -s "__LETSENCRYPT_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/plane <<'EOF_TEMP'
server {
    listen 80;
    server_name __DOMAIN__;
    root /var/www/html;

    location / {
        return 200 'Certbot validation ready';
        add_header Content-Type text/plain;
    }
}
EOF_TEMP
    ln -sf /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/plane
    rm -f /etc/nginx/sites-enabled/default
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html
    nginx -t && systemctl restart nginx

    if [ -x "$DNS_HOOK_SCRIPT" ]; then
        chmod +x "$DNS_HOOK_SCRIPT"
        certbot certonly --manual --preferred-challenges dns --manual-auth-hook "$DNS_HOOK_SCRIPT add" \
            --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" --agree-tos --email "$ADMIN_EMAIL" \
            -d "$DOMAIN" -d "*.$DOMAIN" --non-interactive --manual-public-ip-logging-ok
    else
        systemctl stop nginx || true
        certbot certonly --standalone --preferred-challenges http --agree-tos --email "$ADMIN_EMAIL" \
            -d "$DOMAIN" --non-interactive
        systemctl start nginx || true
    fi

    # ========== NGINX REVERSE PROXY ==========
    echo "[10/15] Configuring Nginx..."
    notify_webhook "provisioning" "nginx_setup" "Setting up reverse proxy"
    cat > /etc/nginx/sites-available/plane <<'EOF_NGINX'
server {
    listen 80;
    server_name __DOMAIN__;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl http2;
    server_name __DOMAIN__;
    ssl_certificate /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
EOF_NGINX

    ln -sf /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/plane
    nginx -t && systemctl reload nginx

    # ========== FINAL CHECKS ==========
    echo "[11/15] Performing verification..."
    notify_webhook "provisioning" "verification" "Checking Plane container and SSL"
    if ! docker ps | grep -q "plane"; then
        echo "ERROR: Plane container not running!"
        notify_webhook "failed" "verification" "Plane container not running"
        exit 1
    fi
    if ! nginx -t; then
        echo "ERROR: Nginx configuration failed"
        notify_webhook "failed" "verification" "Nginx config test failed"
        exit 1
    fi
    if [ ! -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        echo "ERROR: SSL certificate missing!"
        notify_webhook "failed" "verification" "SSL cert missing"
        exit 1
    fi

    echo "✅ Plane setup complete!"
    notify_webhook "completed" "finished" "Plane deployment succeeded"

    cat <<EOF_SUMMARY
=============================================
🔗 Access URL: https://__DOMAIN__
👤 Admin email: __ADMIN_EMAIL__
⚙️ Useful commands:
- Status: cd $DATA_DIR && docker compose ps
- Logs: cd $DATA_DIR && docker compose logs -f
- Restart: cd $DATA_DIR && docker compose restart
- Update: cd $DATA_DIR && docker compose pull && docker compose up -d
=============================================
EOF_SUMMARY
    """)

    # ========== WEBHOOK FUNCTION HANDLING ==========
    if WEBHOOK_URL:
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
            curl -s -X POST "__WEBHOOK_URL__" -H "Content-Type: application/json" -d "$JSON_PAYLOAD" --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 5 --output /dev/null || true
        }
""")
    else:
        webhook_fn = textwrap.dedent("""
        notify_webhook() {
            return 0
        }
        """)

   # ========== TOKEN REPLACEMENT ==========
    # Replace webhook function first
    final = script_template.replace("__WEBHOOK_FUNCTION__", webhook_fn)

    # Replace all other tokens
    for token, value in tokens.items():
        final = final.replace(token, value)

    # Replace webhook-specific tokens in the webhook function
    final = final.replace("__LOCATION__", tokens["__LOCATION__"])
    final = final.replace("__RESOURCE_GROUP__", tokens["__RESOURCE_GROUP__"])
    final = final.replace("__WEBHOOK_URL__", tokens["__WEBHOOK_URL__"])
    # Replace SSL configuration URLs
    final = final.replace("__LET_OPTIONS_URL__", tokens["__LET_OPTIONS_URL__"])
    final = final.replace("__SSL_DHPARAMS_URL__", tokens["__SSL_DHPARAMS_URL__"])

    # Replace CERTBOT_CRON token
    certbot_cron = "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
    final = final.replace("__CERTBOT_CRON__", certbot_cron)

    # Replace remaining tokens for password, admin email, domain, port
    final = final.replace("__ADMIN_PASSWORD__", tokens["__ADMIN_PASSWORD__"])
    final = final.replace("__ADMIN_EMAIL__", tokens["__ADMIN_EMAIL__"])
    final = final.replace("__DOMAIN__", tokens["__DOMAIN__"])
    final = final.replace("__PORT__", tokens["__PORT__"])

    return final
