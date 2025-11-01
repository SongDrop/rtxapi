import textwrap

def generate_apprise_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    PORT=8000,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
    WEBHOOK_URL="",
    ALLOW_EMBED_WEBSITE="",
    location="",
    resource_group="",
    UPLOAD_SIZE_MB=100  # Apprise doesn't need large uploads
):
    """
    Returns a full bash provisioning script for Apprise API using template method.
    Usage: script = generate_apprise_setup("apprise.example.com", "admin@example.com", "8000", ...)
    """
    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__PORT__": str(PORT),
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__ALLOW_EMBED_WEBSITE__": ALLOW_EMBED_WEBSITE,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__APPRISE_DIR__": "/opt/apprise",
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__MAX_UPLOAD_SIZE_MB__": f"{UPLOAD_SIZE_MB}M",
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Apprise API Provisioning Script (generated)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    # Error handling with webhook notifications
    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging Setup ---
    LOG_FILE="/var/log/apprise_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    PORT="__PORT__"
    APPRISE_DIR="__APPRISE_DIR__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    ALLOW_EMBED_WEBSITE="__ALLOW_EMBED_WEBSITE__"
    MAX_UPLOAD_SIZE_MB="__MAX_UPLOAD_SIZE_MB__"

    echo "[1/12] Starting Apprise API provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Apprise API setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/12] Validating inputs..."
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
    echo "[3/12] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"

    export DEBIAN_FRONTEND=noninteractive

    notify_webhook "provisioning" "apt_update" "Running apt-get update"
    apt-get update -q || { notify_webhook "failed" "apt_update" "apt-get update failed"; exit 1; }

    notify_webhook "provisioning" "apt_upgrade" "Running apt-get upgrade"
    apt-get upgrade -y -q || { notify_webhook "failed" "apt_upgrade" "apt-get upgrade failed"; exit 1; }

    notify_webhook "provisioning" "apt_install" "Installing required packages"
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq \
        make net-tools python3-certbot-nginx openssl ufw || { notify_webhook "failed" "apt_install" "apt-get install failed"; exit 1; }

    # ========== DOCKER INSTALLATION ==========
    echo "[4/12] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    # Ensure prerequisites exist
    apt-get install -y -q ca-certificates curl gnupg lsb-release || {
        notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
        exit 1
    }

    # Remove old versions (ignore errors)
    apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

    # Setup Docker's official GPG key
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

    # Update and install Docker with retries
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

    # Enable and start Docker
    systemctl enable docker
    systemctl start docker

    # Verify Docker works
    if ! docker info >/dev/null 2>&1; then
        echo "❌ Docker daemon did not start correctly"
        notify_webhook "failed" "docker_daemon" "Docker daemon failed to start"
        journalctl -u docker --no-pager | tail -n 50 || true
        exit 1
    fi

    echo "✅ Docker installed and running"
    notify_webhook "provisioning" "docker_ready" "Docker installed successfully"
    sleep 5

    # ========== APPRISE DIRECTORY SETUP ==========
    echo "[5/12] Setting up Apprise directories..."
    notify_webhook "provisioning" "directory_setup" "Creating Apprise directory structure"
    sleep 5

    mkdir -p "$APPRISE_DIR"/{config,ssl} || {
        echo "ERROR: Failed to create Apprise directories"
        notify_webhook "failed" "directory_creation" "Failed to create Apprise directories"
        exit 1
    }

    # Set proper permissions for config directory
    chown -R 33:33 "$APPRISE_DIR"/config || {
        echo "WARNING: Could not change ownership of config directory"
    }
    sleep 5

    # ========== DOCKER COMPOSE CONFIGURATION ==========
    echo "[6/12] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose" "Configuring Docker Compose"
    sleep 5

    cat > "$APPRISE_DIR/docker-compose.yml" <<EOF
version: "3.8"
services:
  apprise:
    image: caronc/apprise:latest
    container_name: apprise-api
    restart: always
    ports:
      - "8000:8000"
    volumes:
      - ./config:/config
    environment:
      - APPRISE_DENY_SERVICES=windows,dbus,gnome,macos,syslog
      - ALLOWED_HOSTS=*
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/details"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
EOF

    sleep 5
    notify_webhook "provisioning" "docker_compose_ready" "Docker Compose configuration created"

    sleep 5
    echo "[7/12] Starting Apprise API..."
    notify_webhook "provisioning" "apprise_start" "Starting Apprise API container"

    cd "$APPRISE_DIR"
    docker compose up -d || {
        echo "ERROR: Failed to start Apprise container"
        notify_webhook "failed" "container_start" "Failed to start Apprise container"
        exit 1
    }

    sleep 10

    # Wait for Apprise to become ready
    echo "[8/12] Waiting for Apprise API to become ready..."
    notify_webhook "provisioning" "apprise_readiness" "Waiting for Apprise API to become ready..."

    READY_TIMEOUT=300   # 5 minutes
    SLEEP_INTERVAL=5
    elapsed=0
    READY=false

    # Ensure container exists
    echo "⏳ Waiting for container 'apprise-api' to appear..."
    while ! docker ps -a --format '{{.Names}}' | grep -wq apprise-api; do
        sleep $SLEEP_INTERVAL
        elapsed=$((elapsed + SLEEP_INTERVAL))
        [ $elapsed -ge $READY_TIMEOUT ] && {
            echo "❌ Timeout waiting for container 'apprise-api' to appear"
            notify_webhook "failed" "service_start" "Timeout waiting for apprise container"
            docker ps -a
            docker compose logs --tail=200
            exit 1
        }
    done

    # Reset timer
    elapsed=0

    echo "🔎 Checking Apprise API container health..."
    while [ $elapsed -lt $READY_TIMEOUT ]; do
        # Check container state first
        state=$(docker inspect -f '{{.State.Status}}' apprise-api 2>/dev/null || echo "unknown")
        echo "   -> state=$state (elapsed ${elapsed}s)"

        # Health check via API endpoint
        if curl -fsS "http://127.0.0.1:8000/details" >/dev/null 2>&1; then
            READY=true
            break
        fi

        # If container exited, bail early
        if [ "$state" = "exited" ] || [ "$state" = "dead" ]; then
            echo "❌ Container 'apprise-api' is $state. Dumping logs:"
            docker logs --tail=200 apprise-api || true
            notify_webhook "failed" "service_start" "Apprise container is $state"
            exit 1
        fi

        sleep $SLEEP_INTERVAL
        elapsed=$((elapsed + $SLEEP_INTERVAL))
    done

    if [ "$READY" = false ]; then
        echo "❌ Apprise API failed to become ready in $READY_TIMEOUT seconds"
        docker ps -a
        docker compose logs --tail=500
        notify_webhook "failed" "service_start" "Apprise API readiness timeout"
        exit 1
    fi

    echo "✅ Apprise API is running and healthy"
    notify_webhook "provisioning" "service_start" "✅ Apprise API is running and healthy"
    sleep 5

    # ========== FIREWALL CONFIGURATION ==========
    echo "[9/12] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW firewall"

    if ! ufw status | grep -q inactive; then
        echo "UFW already active; adding rules"
    fi

    ufw allow 22/tcp 
    ufw allow 80/tcp 
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable

    # ========== NGINX CONFIG + SSL ==========
    echo "[10/12] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/apprise

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/apprise <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/apprise /etc/nginx/sites-enabled/apprise
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
        notify_webhook "warning" "ssl" "Apprise Certbot failed, SSL not installed for __DOMAIN__"
        
        # HTTP-only configuration
        cat > /etc/nginx/sites-available/apprise <<'EOF_HTTP'
server {
    listen 80;
    server_name __DOMAIN__;

    client_max_body_size __MAX_UPLOAD_SIZE_MB__;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
EOF_HTTP
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/apprise <<'EOF_SSL'
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

    client_max_body_size __MAX_UPLOAD_SIZE_MB__;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
EOF_SSL
    fi

    ln -sf /etc/nginx/sites-available/apprise /etc/nginx/sites-enabled/apprise
    nginx -t && systemctl reload nginx

    # ========== SSL RENEWAL SETUP ==========
    echo "[11/12] Setting up SSL certificate renewal..."
    notify_webhook "provisioning" "ssl_renewal" "Setting up Certbot renewal cron"

    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "__CERTBOT_CRON__" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FINAL CHECKS ==========
    echo "[12/12] Final verification..."
    notify_webhook "provisioning" "verification" "Performing verification checks"

    if ! nginx -t; then
        echo "ERROR: nginx config test failed"
        notify_webhook "failed" "verification" "Nginx config test failed"
        exit 1
    fi

    # Test API connectivity
    echo "Testing Apprise API connectivity..."
    if curl -fsS "http://127.0.0.1:8000/details" >/dev/null 2>&1; then
        echo "✅ Apprise API is responding internally"
        notify_webhook "provisioning" "verification" "Apprise API internal check passed"
    else
        echo "❌ Apprise API internal check failed"
        notify_webhook "warning" "verification" "Apprise API internal check failed"
    fi

    # Test external access if SSL is configured
    if [ -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://__DOMAIN__/details || echo "000")
        echo "HTTPS API check returned: $HTTPS_RESPONSE"
        if [ "$HTTPS_RESPONSE" = "200" ]; then
            notify_webhook "provisioning" "verification" "HTTPS API access working"
        else
            notify_webhook "warning" "verification" "HTTPS API check returned $HTTPS_RESPONSE"
        fi
    else
        HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://__DOMAIN__/details || echo "000")
        echo "HTTP API check returned: $HTTP_RESPONSE"
        if [ "$HTTP_RESPONSE" = "200" ]; then
            notify_webhook "provisioning" "verification" "HTTP API access working"
        else
            notify_webhook "warning" "verification" "HTTP API check returned $HTTP_RESPONSE"
        fi
    fi

    # Final nginx reload
    if nginx -t; then
        systemctl reload nginx
        echo "✅ Nginx configuration test passed"
        notify_webhook "provisioning" "verification" "✅ Nginx configuration test passed"
    else
        echo "❌ Nginx configuration test failed"
        notify_webhook "failed" "verification" "Nginx config test failed"
        exit 1
    fi
                                      
    notify_webhook "provisioning" "verification" "✅ Apprise API installed"


    sleep 10

    cat <<EOF_FINAL
=============================================
✅ Apprise API Setup Complete!
---------------------------------------------
🔗 Access URL: https://__DOMAIN__
📊 API Status: https://__DOMAIN__/details
🔧 Web Interface: https://__DOMAIN__/
---------------------------------------------
⚙️ Useful commands:
- Check status: cd $APPRISE_DIR && docker compose ps
- View logs: cd $APPRISE_DIR && docker compose logs -f
- Restart: cd $APPRISE_DIR && docker compose restart
- Update: cd $APPRISE_DIR && docker compose pull && docker compose up -d
---------------------------------------------
📝 API Usage Examples:

# Stateless notification
curl -X POST https://__DOMAIN__/notify \\
  -d "urls=mailto://user:pass@gmail.com&body=Test Message"

# Add configuration
curl -X POST https://__DOMAIN__/add/myconfig \\
  -d "urls=mailto://user:pass@gmail.com,discord://webhook_id/webhook_token"

# Send to saved config
curl -X POST https://__DOMAIN__/notify/myconfig \\
  -d "body=Notification via saved config&title=Alert"

---------------------------------------------
Enjoy your new Apprise API instance!
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

    # Replace remaining tokens for admin email, domain, port
    final = final.replace("__ADMIN_EMAIL__", tokens["__ADMIN_EMAIL__"])
    final = final.replace("__DOMAIN__", tokens["__DOMAIN__"])
    final = final.replace("__PORT__", tokens["__PORT__"])

    return final