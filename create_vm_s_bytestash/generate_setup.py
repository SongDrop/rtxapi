import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT=3000,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    UPLOAD_SIZE_MB=256,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
):
    """
    Returns a full 15-step Bytestash provisioning script in your style.
    """
    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__WEBHOOK_URL__": WEBHOOK_URL,
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

    # ----------------------------------------------------------------------
    # Plane Provisioning Script (Forgejo style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    # Enhanced error logging
    error_handler() {
        local exit_code=$?
        local line_number=$1
        echo "ERROR: Script failed at line $line_number with exit code $exit_code"
        notify_webhook "failed" "unexpected_error" "Script exited on line $line_number with code $exit_code"
        exit $exit_code
    }
    trap 'error_handler ${LINENO}' ERR
                                      
    # --- Logging ---
    LOG_FILE="/var/log/bytestash_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1
                                      
    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    PORT="__PORT__"
    BYTESTASH_DIR="__BYTESTASH_DIR__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    MAX_UPLOAD_SIZE_MB="__MAX_UPLOAD_SIZE_MB__"
    MAX_UPLOAD_SIZE_BYTES="__MAX_UPLOAD_SIZE_BYTES__"

    # Add missing variables
    READY_TIMEOUT=300
    SLEEP_INTERVAL=10

    echo "[1/15] Starting Bytestash provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Bytestash setup"  

    # --- Step 1: Validate Inputs ---
    echo "[2/15] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and port"
   
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

    # Generate JWT secret without openssl
    if [ -z "${BYTESTASH_JWT_SECRET:-}" ]; then
        BYTESTASH_JWT_SECRET=$(head -c 32 /dev/urandom | xxd -p -c 32 | head -1)
        export BYTESTASH_JWT_SECRET
    fi
    
    echo "[2/15] JWT secret generated"
    notify_webhook "provisioning" "jwt_generated" "JWT secret generated"
    sleep 5

   
    # --- Step 3: System dependencies ---
    echo "[3/15] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"

    export DEBIAN_FRONTEND=noninteractive

    notify_webhook "provisioning" "apt_update" "Running apt-get update"
    apt-get update -q || { notify_webhook "failed" "apt_update" "apt-get update failed"; exit 1; }

    notify_webhook "provisioning" "apt_upgrade" "Running apt-get upgrade"
    apt-get upgrade -y -q || { notify_webhook "failed" "apt_upgrade" "apt-get upgrade failed"; exit 1; }

    notify_webhook "provisioning" "apt_install" "Installing required packages"
    apt-get install -y -q \
        curl git nginx certbot python3-pip python3-venv jq make ufw xxd \
        software-properties-common docker-compose-plugin \
        || { notify_webhook "failed" "apt_install" "apt-get install failed"; exit 1; }


    # ========== DOCKER INSTALLATION ==========
    echo "[4/15] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    # Install prerequisites
    apt-get install -y -q ca-certificates curl gnupg lsb-release apt-transport-https || {
        echo "❌ Failed to install Docker prerequisites"
        notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
        exit 1
    }

    # Remove old versions (ignore errors)
    apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

    # Setup Docker's official GPG key
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg || {
        echo "❌ Failed to download Docker GPG key"
        notify_webhook "failed" "docker_gpg" "Failed to download Docker GPG key"
        exit 1
    }
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Update package list with new repository
    apt-get update -q || {
        echo "❌ Failed to update package list after adding Docker repo"
        notify_webhook "failed" "docker_repo" "Failed to update package list"
        exit 1
    }

    # Install Docker with retries
    for i in {1..3}; do
        echo "Docker install attempt $i/3..."
        if apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
            break
        fi
        echo "⚠️ Docker install attempt $i failed; retrying in 5 seconds..."
        sleep 5
        if [ $i -eq 3 ]; then
            echo "❌ Docker installation failed after 3 attempts"
            notify_webhook "failed" "docker_install" "Docker install failed after 3 attempts"
            exit 1
        fi
    done

    # Enable and start Docker
    systemctl enable docker
    if ! systemctl start docker; then
        echo "❌ Failed to start Docker service"
        journalctl -u docker --no-pager | tail -n 20
        notify_webhook "failed" "docker_service" "Failed to start Docker service"
        exit 1
    fi

    # Wait for Docker to be ready
    sleep 3
    
    # Verify Docker works
    if ! docker info >/dev/null 2>&1; then
        echo "❌ Docker daemon did not start correctly"
        journalctl -u docker --no-pager | tail -n 30
        notify_webhook "failed" "docker_daemon" "Docker daemon failed to start"
        exit 1
    fi

    echo "✅ Docker installed and running"
    notify_webhook "provisioning" "docker_ready" "✅ Docker installed successfully"
    sleep 2
                                      
    # ========== BYTESTASH DIRECTORY SETUP ==========
    echo "[5/15] Creating Bytestash directories..."
    notify_webhook "provisioning" "directories" "Creating Bytestash directories"

    mkdir -p "$BYTESTASH_DIR" || {
        echo "ERROR: Failed to create Plane data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Plane directory"
        exit 1
    }
    chown -R 1000:1000 "$BYTESTASH_DIR"
    cd "$BYTESTASH_DIR"
    echo "✅ Bytestash directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ Bytestash directory created successfully"
    
    sleep 5
                                      
   # --- Step 4: Docker Compose ---
    echo "[6/15] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose" "Creating docker-compose.yml"

    cat > "$BYTESTASH_DIR/docker-compose.yml" <<'EOF'
version: "3.8"

services:
  bytestash:
    image: "ghcr.io/jordan-dalby/bytestash:latest"
    container_name: bytestash
    restart: always
    volumes:
      - ./data:/data/snippets
    ports:
      - "${PORT}:5000"
    environment:
      # See https://github.com/jordan-dalby/ByteStash/wiki/FAQ#environment-variables
      BASE_PATH: ""
      JWT_SECRET: "${BYTESTASH_JWT_SECRET}"
      TOKEN_EXPIRY: "24h"
      ALLOW_NEW_ACCOUNTS: "true"
      DEBUG: "true"
      DISABLE_ACCOUNTS: "false"
      DISABLE_INTERNAL_ACCOUNTS: "false"
      # Optional host restriction (uncomment and edit as needed)
      # ALLOWED_HOSTS: "localhost,${DOMAIN}"
      # See https://github.com/jordan-dalby/ByteStash/wiki/Single-Sign%E2%80%90on-Setup for SSO config
      OIDC_ENABLED: "false"
      OIDC_DISPLAY_NAME: ""
      OIDC_ISSUER_URL: ""
      OIDC_CLIENT_ID: ""
      OIDC_CLIENT_SECRET: ""
      OIDC_SCOPES: ""
EOF

    sleep 5

    # --- Step 5: Start Docker container ---
    echo "[7/15] Starting Bytestash container..."
    notify_webhook "provisioning" "container_start" "Starting Bytestash container"
    cd "$BYTESTASH_DIR"

    # Try both docker compose commands with fallback
    if docker compose version &> /dev/null; then
        echo "Using 'docker compose'"
        docker compose up -d || {
            echo "ERROR: docker compose failed"
            docker compose logs || true
            exit 1
        }
    elif command -v docker-compose &> /dev/null; then
        echo "Using 'docker-compose'"
        docker-compose up -d || {
            echo "ERROR: docker-compose failed"
            docker-compose logs || true
            exit 1
        }
    else
        echo "ERROR: Neither docker compose nor docker-compose available"
        notify_webhook "failed" "container_start" "Docker compose not available"
        exit 1
    fi
                     
    echo "✅ Docker Compose configured"
    notify_webhook "provisioning" "docker_configured" "✅ Docker Compose configured"
    sleep 5

    # ========== FIREWALL ==========
    echo "[8/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8080/tcp
    ufw allow 5432/tcp
    ufw allow 6379/tcp  
    ufw allow 9090/tcp                             
    ufw allow "$PORT"/tcp
    ufw --force enable

    # --- Step 10: Wait for readiness (HTTP probe) ---
    echo "[10/15] Waiting for Bytestash readiness..."
    notify_webhook "provisioning" "http_probe" "Waiting for HTTP readiness"
    
    elapsed=0
    READY=false
    while [ $elapsed -lt $READY_TIMEOUT ]; do
        if curl -fsS "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
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
    sleep 5

    # ========== NGINX CONFIG + SSL (Forgejo / fail-safe) ==========
    echo "[11/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/bytestash

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/bytestash <<EOF_TEMP
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

    ln -sf /etc/nginx/sites-available/bytestash /etc/nginx/sites-enabled/bytestash
    nginx -t && systemctl restart nginx

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html

    # Attempt to obtain SSL certificate
    if ! certbot --nginx -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__"; then
        echo "⚠️ Certbot nginx plugin failed; trying webroot fallback"
        systemctl start nginx || true
        certbot certonly --webroot -w /var/www/html -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__" || true
    fi

    # Fail-safe check
    if [ ! -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        echo "⚠️ SSL certificate not found! Continuing without SSL..."
        notify_webhook "warning" "ssl" "Forgejo Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/bytestash <<EOF_SSL
server {
    listen 80;
    server_name __DOMAIN__;
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl http2;
    server_name __DOMAIN__;

    ssl_certificate /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size __MAX_UPLOAD_SIZE_MB__;

    location / {
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
EOF_SSL

        ln -sf /etc/nginx/sites-available/bytestash /etc/nginx/sites-enabled/bytestash
        nginx -t && systemctl reload nginx
    fi

    echo "[12/15] Setup Cron for renewal..."
    notify_webhook "provisioning" "cron_setup" "Setup Cron for renewal..."
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "certbot renew" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FINAL CHECKS ==========
    echo "[13/15] Final verification..."
    notify_webhook "provisioning" "verification" "Performing verification checks"

    if ! nginx -t; then
        echo "ERROR: nginx config test failed"
        notify_webhook "failed" "verification" "Nginx config test failed"
        exit 1
    fi

    if [ -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://__DOMAIN__ || echo "000")
        echo "HTTPS check returned: $HTTPS_RESPONSE"
        if [ "$HTTPS_RESPONSE" != "200" ]; then
            notify_webhook "warning" "verification" "HTTPS check returned $HTTPS_RESPONSE"
        else
            notify_webhook "provisioning" "verification" "HTTPS OK"
        fi
    fi

    # Test and apply the new config
    if nginx -t; then
        systemctl reload nginx
        echo "✅ Nginx configuration test passed"
        notify_webhook "provisioning" "verification" "✅ Nginx configuration test passed"
    else
        echo "❌ Nginx configuration test failed"
        notify_webhook "failed" "verification" "Nginx config test failed"
        exit 1
    fi

    echo "[14/15] Final system checks..."
    # Verify Docker container is running
    if ! docker ps | grep -q bytestash; then
        echo "❌ Bytestash container is not running"
        notify_webhook "failed" "verification" "Bytestash container not running"
        exit 1
    fi
                                      
    # --- Step 15: Final summary ---
    echo "[15/15] Bytestash provisioning complete!"
    notify_webhook "provisioning" "bytestash_installed" "✅ Bytestash setup completed successfully"
    

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

    return final