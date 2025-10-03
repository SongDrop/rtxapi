import textwrap

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
    """
    Returns a full bash provisioning script for Forgejo with robust SSL handling.
    """
    # ========== TOKEN DEFINITIONS ==========
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
        "__FORGEJO_DIR__": "/opt/forgejo",
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__MAX_UPLOAD_SIZE_MB__": "1024",
        "__MAX_UPLOAD_SIZE_BYTES__": str(1024 * 1024 * 1024),  # 1GB in bytes
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Forgejo Provisioning Script (generated)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    # Error handling with webhook notifications
    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging Setup ---
    LOG_FILE="/var/log/forgejo_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    PORT="__PORT__"
    FORGEJO_DIR="__FORGEJO_DIR__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    ALLOW_EMBED_WEBSITE="__ALLOW_EMBED_WEBSITE__"
    MAX_UPLOAD_SIZE_MB="__MAX_UPLOAD_SIZE_MB__"
    MAX_UPLOAD_SIZE_BYTES="__MAX_UPLOAD_SIZE_BYTES__"

    # Generate LFS JWT secret
    LFS_JWT_SECRET=$(openssl rand -hex 32)

    echo "[1/15] Starting Forgejo provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Forgejo setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/15] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and inputs"

    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "ERROR: Invalid domain format: $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain format: $DOMAIN"
        exit 1
    fi

    if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
        echo "ERROR: Invalid port number: $PORT (must be 1024-65535)"
        notify_webhook "failed" "validation" "Invalid port: $PORT"
        exit 1
    fi

    # ========== SYSTEM DEPENDENCIES ==========
    echo "[3/15] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"

    export DEBIAN_FRONTEND=noninteractive

    notify_webhook "provisioning" "apt_update" "Running apt-get update"
    apt-get update -q || { notify_webhook "failed" "apt_update" "apt-get update failed"; exit 1; }

    notify_webhook "provisioning" "apt_upgrade" "Running apt-get upgrade"
    apt-get upgrade -y -q || { notify_webhook "failed" "apt_upgrade" "apt-get upgrade failed"; exit 1; }

    notify_webhook "provisioning" "apt_install" "Installing required packages"
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq \
        make net-tools python3-certbot-nginx openssl ufw dnsutils || { notify_webhook "failed" "apt_install" "apt-get install failed"; exit 1; }

    # ========== GIT LFS INSTALLATION ==========
    notify_webhook "provisioning" "git_lfs_install" "Installing git-lfs"
    sleep 5

    if ! command -v git-lfs >/dev/null 2>&1; then
        notify_webhook "provisioning" "git_lfs_install" "git-lfs not found, installing from packagecloud"
        sleep 5
        curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash || {
            notify_webhook "failed" "git_lfs_install" "Failed to add git-lfs repository"
            exit 1
        }
        apt-get update -q || { 
            notify_webhook "failed" "apt_update" "apt-get update failed during git-lfs install"
            exit 1
        }
        apt-get install -y git-lfs || { 
            notify_webhook "failed" "git_lfs_install" "apt-get install git-lfs failed"
            exit 1
        }
        notify_webhook "provisioning" "git_lfs_install" "git-lfs installed successfully"
    else
        notify_webhook "provisioning" "git_lfs_install" "git-lfs already installed"
    fi
    sleep 5

    notify_webhook "provisioning" "git_lfs_init" "Initializing git-lfs globally"
    sleep 5
    if ! sudo git lfs install --system; then
        notify_webhook "warning" "git_lfs_init" "System-level git-lfs initialization failed, falling back to user-level"
        git lfs install --skip-repo || {
            notify_webhook "failed" "git_lfs_init" "User-level git-lfs initialization also failed"
            exit 1
        }
    fi
    notify_webhook "provisioning" "git_lfs_init" "git-lfs initialized successfully"
    sleep 5

    # ========== DOCKER INSTALLATION ==========
    echo "[4/15] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    apt-get remove -y docker docker-engine docker.io containerd runc || true
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list

    apt-get update -q
    apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    CURRENT_USER=$(whoami)
    if [ "$CURRENT_USER" != "root" ]; then
        usermod -aG docker "$CURRENT_USER" || true
    fi

    systemctl enable docker
    systemctl start docker

    echo "[5/15] Waiting for Docker to start..."
    notify_webhook "provisioning" "docker_wait" "Waiting for Docker daemon"
    sleep 5

    timeout=180
    while [ $timeout -gt 0 ]; do
        if docker info >/dev/null 2>&1; then
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done

    if [ $timeout -eq 0 ]; then
        echo "ERROR: Docker daemon failed to start"
        notify_webhook "failed" "docker_timeout" "Docker daemon startup timeout"
        exit 1
    fi

    notify_webhook "provisioning" "docker_ready" "Docker installed successfully"
    sleep 5

    # ========== FORGEJO DIRECTORY SETUP ==========
    echo "[6/15] Setting up Forgejo directories..."
    notify_webhook "provisioning" "directory_setup" "Creating Forgejo directory structure"
    sleep 5

    mkdir -p "$FORGEJO_DIR"/{data,config,ssl,data/gitea/lfs} || {
        echo "ERROR: Failed to create Forgejo directories"
        notify_webhook "failed" "directory_creation" "Failed to create Forgejo directories"
        exit 1
    }
    chown -R 1000:1000 "$FORGEJO_DIR"/data "$FORGEJO_DIR"/config "$FORGEJO_DIR"/data/gitea
    sleep 5
                                      
    # ========== DOCKER COMPOSE CONFIGURATION ==========
    echo "[7/15] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose" "Configuring Docker Compose"
    sleep 5

    cat > "$FORGEJO_DIR/docker-compose.yml" <<EOF
version: "3.8"
networks:
  forgejo:
    external: false

services:
  server:
    image: codeberg.org/forgejo/forgejo:12
    container_name: forgejo
    restart: unless-stopped
    environment:
      - USER_UID=1000
      - USER_GID=1000
      - FORGEJO__server__DOMAIN=$DOMAIN
      - FORGEJO__server__ROOT_URL=https://$DOMAIN
      - FORGEJO__server__HTTP_PORT=3000
      - FORGEJO__server__LFS_START_SERVER=true
      - FORGEJO__server__LFS_CONTENT_PATH=/data/gitea/lfs
      - FORGEJO__server__LFS_JWT_SECRET=$LFS_JWT_SECRET
      - FORGEJO__server__LFS_MAX_FILE_SIZE=$MAX_UPLOAD_SIZE_BYTES
    volumes:
      - ./data:/data
      - ./config:/data/config
      - ./ssl:/data/ssl
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "$PORT:3000"
      - "222:22"
    networks:
      - forgejo
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 15s
      timeout: 10s
      retries: 40
EOF

    sleep 5
    notify_webhook "provisioning" "docker_compose_ready" "Docker Compose configuration created"
    sleep 5

    # ========== FIREWALL CONFIGURATION ==========
    echo "[8/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW firewall"

    if ! ufw status | grep -q inactive; then
        echo "UFW already active; adding rules"
    fi

    ufw allow 22/tcp 
    ufw allow 80/tcp 
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable

    # ========== START FORGEJO CONTAINER ==========
    echo "[9/15] Starting Forgejo container..."
    notify_webhook "provisioning" "container_start" "Starting Forgejo Docker container"
    sleep 5

    cd "$FORGEJO_DIR"
    docker compose up -d || {
        echo "ERROR: Failed to start Forgejo container"
        notify_webhook "failed" "container_start" "Failed to start Forgejo container"
        exit 1
    }

    echo "[10/15] Waiting for Forgejo to initialize..."
    notify_webhook "provisioning" "forgejo_wait" "Waiting for Forgejo to become ready"
    sleep 30

    # Wait for Forgejo to be ready
    timeout=300
    while [ $timeout -gt 0 ]; do
        if curl -s http://localhost:$PORT >/dev/null 2>&1; then
            break
        fi
        sleep 10
        timeout=$((timeout - 10))
        echo "Waiting for Forgejo... ($timeout seconds remaining)"
    done

    if [ $timeout -eq 0 ]; then
        echo "WARNING: Forgejo taking longer than expected to start"
        notify_webhook "warning" "forgejo_timeout" "Forgejo startup taking longer than expected"
    fi

    # ========== DNS CHECK ==========
    echo "[11/15] Checking DNS configuration..."
    notify_webhook "provisioning" "dns_check" "Verifying domain DNS resolution"

    # Get public IP
    PUBLIC_IP=$(curl -s http://checkip.amazonaws.com || curl -s http://ifconfig.me || echo "unknown")
    echo "Server public IP: $PUBLIC_IP"
    
    # Check if domain resolves to this server
    echo "Checking DNS resolution for $DOMAIN..."
    DNS_IP=$(dig +short $DOMAIN | head -1 || echo "")
    
    if [ -n "$DNS_IP" ]; then
        echo "Domain $DOMAIN resolves to: $DNS_IP"
        if [ "$DNS_IP" = "$PUBLIC_IP" ]; then
            echo "✅ DNS is correctly configured"
            DNS_VALID=true
        else
            echo "⚠️ DNS points to $DNS_IP but server IP is $PUBLIC_IP"
            echo "This may cause SSL certificate validation to fail"
            DNS_VALID=false
        fi
    else
        echo "❌ Domain $DOMAIN does not resolve to any IP"
        DNS_VALID=false
    fi

    # ========== NGINX CONFIG + SSL ==========
    echo "[12/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "ssl_nginx" "Configuring nginx + SSL"

    # Stop any existing nginx
    systemctl stop nginx || true

    # Clean up existing configs
    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-enabled/forgejo
    rm -f /etc/nginx/sites-available/forgejo

    # Create nginx directories if they don't exist
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled /var/www/html

    # Download Let's Encrypt recommended configs with retry logic
    echo "Downloading SSL configurations..."
    for i in {1..5}; do
        if curl -s "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf" -o /etc/letsencrypt/options-ssl-nginx.conf; then
            break
        fi
        sleep 5
    done

    for i in {1..5}; do
        if curl -s "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem" -o /etc/letsencrypt/ssl-dhparams.pem; then
            break
        fi
        sleep 5
    done

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown -R www-data:www-data /var/www/html
    echo "Certbot validation ready" > /var/www/html/index.html

    # SSL CERTIFICATE HANDLING WITH GRACEFUL FALLBACK
    CERTBOT_SUCCESS=false
    SSL_ENABLED=false

    if [ "$DNS_VALID" = true ]; then
        echo "Attempting to obtain SSL certificate..."
        
        # Initial temporary HTTP server for certbot
        cat > /etc/nginx/sites-available/forgejo <<EOF_TEMP
server {
    listen 80;
    server_name $DOMAIN;
    root /var/www/html;

    location / {
        return 200 'Certbot validation ready';
        add_header Content-Type text/plain;
    }
}
EOF_TEMP

        ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/forgejo
        
        # Test nginx config
        if nginx -t; then
            systemctl start nginx || {
                echo "ERROR: Failed to start nginx"
                notify_webhook "failed" "nginx_start" "Failed to start nginx"
            }
        fi

        # Try certbot with different methods
        for method in "nginx" "webroot"; do
            echo "Trying certbot with method: $method"
            case $method in
                "nginx")
                    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL" --no-redirect; then
                        CERTBOT_SUCCESS=true
                        SSL_ENABLED=true
                        echo "✅ Certbot nginx plugin succeeded"
                        break
                    fi
                    ;;
                "webroot")
                    if certbot certonly --webroot -w /var/www/html -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL"; then
                        CERTBOT_SUCCESS=true
                        SSL_ENABLED=true
                        echo "✅ Certbot webroot method succeeded"
                        break
                    fi
                    ;;
            esac
        done

        if [ "$CERTBOT_SUCCESS" = false ]; then
            echo "❌ All certbot methods failed"
            notify_webhook "warning" "ssl_certificate" "Failed to obtain SSL certificate, continuing with HTTP"
            # Stop nginx to reconfigure without SSL
            systemctl stop nginx || true
        fi
    else
        echo "Skipping SSL certificate setup due to DNS misconfiguration"
        notify_webhook "warning" "dns_misconfigured" "DNS not configured, skipping SSL"
    fi

    # FINAL NGINX CONFIGURATION
    if [ "$SSL_ENABLED" = true ] && [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        echo "Configuring nginx with SSL..."
        cat > /etc/nginx/sites-available/forgejo <<EOF_SSL
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size ${MAX_UPLOAD_SIZE_MB}M;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_buffering off;
        proxy_request_buffering off;
        add_header Content-Security-Policy "frame-ancestors 'self' $ALLOW_EMBED_WEBSITE" always;
    }
}
EOF_SSL
    else
        echo "Configuring nginx without SSL (HTTP only)..."
        SSL_ENABLED=false
        cat > /etc/nginx/sites-available/forgejo <<EOF_HTTP
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size ${MAX_UPLOAD_SIZE_MB}M;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_buffering off;
        proxy_request_buffering off;
        add_header Content-Security-Policy "frame-ancestors 'self' $ALLOW_EMBED_WEBSITE" always;
    }
}
EOF_HTTP
    fi

    # Test and apply the new config
    if nginx -t; then
        systemctl enable nginx
        systemctl start nginx
        systemctl reload nginx
        echo "✅ Nginx configuration test passed"
        notify_webhook "provisioning" "nginx_ready" "Nginx configured successfully"
    else
        echo "❌ Nginx configuration test failed"
        notify_webhook "failed" "nginx_config" "Nginx config test failed"
        exit 1
    fi

    # Setup cron for SSL renewal if certificate was obtained
    if [ "$SSL_ENABLED" = true ]; then
        echo "[13/15] Setting up Certbot renewal cron..."
        notify_webhook "provisioning" "ssl_cron" "Scheduling daily certificate renewal"
        
        # Setup cron for renewal (runs daily and reloads nginx on change)
        (crontab -l 2>/dev/null | grep -v "certbot renew" || true; \
            echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
    fi

    # ========== FINAL CHECKS ==========
    echo "[14/15] Performing final verification..."
    notify_webhook "provisioning" "verification" "Performing verification checks"

    # Check if services are running
    if systemctl is-active --quiet nginx; then
        echo "✅ Nginx is running"
    else
        echo "❌ Nginx is not running"
        notify_webhook "warning" "verification" "Nginx is not running"
    fi

    if docker ps | grep -q forgejo; then
        echo "✅ Forgejo container is running"
    else
        echo "❌ Forgejo container is not running"
        notify_webhook "warning" "verification" "Forgejo container is not running"
    fi

    # Test accessibility
    echo "[15/15] Testing accessibility..."
    if [ "$SSL_ENABLED" = true ]; then
        PROTOCOL="https"
        URL="https://$DOMAIN"
    else
        PROTOCOL="http" 
        URL="http://$DOMAIN"
    fi

    # Get server IP for fallback testing
    SERVER_IP=$(hostname -I | awk '{print $1}')
    IP_URL="$PROTOCOL://$SERVER_IP"

    echo "Testing access via: $URL"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" || echo "000")
    
    if [ "$RESPONSE" = "200" ]; then
        echo "✅ $PROTOCOL accessibility test passed via domain"
        FINAL_URL="$URL"
    else
        echo "⚠️ Domain access returned $RESPONSE, testing via IP..."
        IP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$IP_URL" || echo "000")
        if [ "$IP_RESPONSE" = "200" ]; then
            echo "✅ $PROTOCOL accessibility test passed via IP"
            FINAL_URL="$IP_URL"
        else
            echo "⚠️ Both domain and IP access failed"
            FINAL_URL="$URL"
        fi
    fi

    # ========== COMPLETION ==========
    echo "Setup complete!"
    notify_webhook "success" "complete" "Forgejo provisioning completed successfully"

    # Display appropriate completion message
    if [ "$SSL_ENABLED" = true ]; then
        SSL_STATUS="✅ SSL Enabled"
        ACCESS_NOTES="Your instance is secured with HTTPS"
    else
        SSL_STATUS="⚠️  SSL Not Enabled (DNS may need configuration)"
        ACCESS_NOTES="SSL certificate setup was skipped due to DNS configuration. You can set up SSL later by running certbot manually after configuring DNS."
    fi

    cat <<EOF_FINAL
=============================================
✅ Forgejo Setup Complete!
---------------------------------------------
🔗 Access URL: $FINAL_URL
🔐 $SSL_STATUS
👤 Admin email: $ADMIN_EMAIL
🔒 Default password: $ADMIN_PASSWORD
---------------------------------------------
$ACCESS_NOTES
---------------------------------------------
⚙️ Useful commands:
- Check status: cd $FORGEJO_DIR && docker compose ps
- View logs: cd $FORGEJO_DIR && docker compose logs -f
- Restart: cd $FORGEJO_DIR && docker compose restart
- Update: cd $FORGEJO_DIR && docker compose pull && docker compose up -d
---------------------------------------------
📝 Post-installation steps:
1. Visit the Access URL to complete setup
2. Change the default admin password immediately
3. Configure your repository settings
4. Set up backup procedures
5. If SSL is not enabled, configure DNS and run: 
   sudo certbot --nginx -d $DOMAIN
---------------------------------------------
Enjoy your new Forgejo instance!
=============================================
EOF_FINAL
    """)

    # ========== WEBHOOK FUNCTION HANDLING ==========
    if tokens["__WEBHOOK_URL__"]:
        webhook_fn = textwrap.dedent(r"""
        notify_webhook() {
            local status="$1"
            local step="$2"
            local message="$3"

            # Build JSON payload
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

            # Send webhook with retry logic
            curl -s -X POST "__WEBHOOK_URL__" \
                -H "Content-Type: application/json" \
                -d "$JSON_PAYLOAD" \
                --connect-timeout 10 \
                --max-time 30 \
                --retry 2 \
                --retry-delay 5 \
                --write-out "Webhook HTTP status: %{http_code}\n" \
                --output /dev/null || true
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
    final_script = script_template.replace("__WEBHOOK_FUNCTION__", webhook_fn)

    # Replace all other tokens
    for token, value in tokens.items():
        final_script = final_script.replace(token, value)

    # Replace webhook-specific tokens in the webhook function
    final_script = final_script.replace("__LOCATION__", tokens["__LOCATION__"])
    final_script = final_script.replace("__RESOURCE_GROUP__", tokens["__RESOURCE_GROUP__"])
    final_script = final_script.replace("__WEBHOOK_URL__", tokens["__WEBHOOK_URL__"])

    # Replace SSL configuration URLs
    final_script = final_script.replace("__LET_OPTIONS_URL__", tokens["__LET_OPTIONS_URL__"])
    final_script = final_script.replace("__SSL_DHPARAMS_URL__", tokens["__SSL_DHPARAMS_URL__"])

    return final_script