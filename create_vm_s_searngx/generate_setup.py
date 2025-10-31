import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT=8888,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    INSTANCE_NAME="SearXNG",
    DATA_DIR="/opt/searxng",
    DEPLOYMENT_TYPE="container",  # "container" or "manual"
    DOCKER_COMPOSE_VERSION="v2.27.0",
    SEARXNG_VERSION="latest"
):
    """
    Returns a full bash provisioning script for SearXNG, in Forgejo style.
    Fully automated installation with comprehensive error handling.
    """

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__INSTANCE_NAME__": INSTANCE_NAME,
        "__PORT__": str(PORT),
        "__DATA_DIR__": DATA_DIR,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DOCKER_COMPOSE_VERSION__": DOCKER_COMPOSE_VERSION,
        "__SEARXNG_VERSION__": SEARXNG_VERSION,
        "__DEPLOYMENT_TYPE__": DEPLOYMENT_TYPE,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # SearXNG Automated Provisioning Script (Forgejo style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/searxng_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    INSTANCE_NAME="__INSTANCE_NAME__"
    PORT="__PORT__"
    DATA_DIR="__DATA_DIR__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DEPLOYMENT_TYPE="__DEPLOYMENT_TYPE__"
    SEARXNG_VERSION="__SEARXNG_VERSION__"

    echo "[1/10] Starting automated SearXNG provisioning..."
    notify_webhook "provisioning" "starting" "Beginning automated SearXNG setup - Deployment type: $DEPLOYMENT_TYPE"

    # ========== INPUT VALIDATION ==========
    echo "[2/10] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and configuration"

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
    echo "[3/10] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"
    
    export DEBIAN_FRONTEND=noninteractive
    
    # Update system with retry logic
    for i in {1..3}; do
        if apt-get update -q; then
            echo "✅ System updated successfully on attempt $i"
            break
        fi
        echo "⚠️ System update attempt $i failed; retrying..."
        sleep 5
        [ $i -eq 3 ] && {
            echo "❌ System update failed after 3 attempts"
            notify_webhook "failed" "system_update_failed" "System update failed after 3 attempts"
            exit 1
        }
    done

    # Install base packages with comprehensive error handling
    apt-get upgrade -y -q
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx openssl ufw || {
        echo "❌ Failed to install base packages"
        notify_webhook "failed" "package_installation_failed" "Failed to install base system packages"
        exit 1
    }

    echo "✅ System dependencies installed"
    notify_webhook "provisioning" "dependencies_ready" "✅ System dependencies installed successfully"

    # ========== DEPLOYMENT TYPE EXECUTION ==========
    if [ "$DEPLOYMENT_TYPE" = "container" ]; then
        # ========== DOCKER INSTALLATION ==========
        echo "[4/10] Installing Docker..."
        notify_webhook "provisioning" "docker_install" "Installing Docker engine"

        # Ensure prerequisites exist
        apt-get install -y -q ca-certificates curl gnupg lsb-release || {
            notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
            exit 1
        }

        # Remove old versions (ignore errors)
        apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

        # Setup Docker's official GPG key with retry loop
        mkdir -p /etc/apt/keyrings
        MAX_RETRIES=3

        for i in $(seq 1 $MAX_RETRIES); do
            if curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; then
                echo "✅ Docker GPG key downloaded successfully on attempt $i"
                break
            fi
            echo "⚠️ Docker GPG key download attempt $i failed; retrying..."
            sleep 5
            if [ $i -eq $MAX_RETRIES ]; then
                echo "❌ Failed to download Docker GPG key after $MAX_RETRIES attempts"
                notify_webhook "failed" "docker_gpg" "Failed to download Docker GPG key after $MAX_RETRIES attempts"
                exit 1
            fi
        done

        chmod a+r /etc/apt/keyrings/docker.gpg

        ARCH=$(dpkg --print-architecture)
        CODENAME=$(lsb_release -cs)
        echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list

        # Update and install Docker with retries
        for i in {1..3}; do
            if apt-get update -q && apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
                echo "✅ Docker installed successfully on attempt $i"
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
        notify_webhook "provisioning" "docker_ready" "✅ Docker installed successfully"

        # ========== SEARXNG CONTAINER SETUP ==========
        echo "[5/10] Setting up SearXNG container deployment..."
        notify_webhook "provisioning" "container_setup" "Configuring SearXNG container deployment"

        # Create data directory
        mkdir -p "$DATA_DIR"/{config,data}
        cd "$DATA_DIR"

        # Generate secure secret key
        echo "🔐 Generating secure credentials..."
        notify_webhook "provisioning" "credentials_generation" "Creating secure secret key"

        generate_secure_random() {
            local length="$1"
            local result=""
            
            # Try multiple methods for maximum compatibility
            if command -v openssl &>/dev/null; then
                result=$(openssl rand -hex "$length" 2>/dev/null || true)
            fi
            
            if [ -z "$result" ] && [ -f /dev/urandom ]; then
                result=$(head -c "$length" /dev/urandom | xxd -p -c "$length" 2>/dev/null | head -c $((length*2)) || true)
            fi
            
            if [ -z "$result" ]; then
                echo "❌ ERROR: Unable to generate random string"
                exit 1
            fi
            
            echo "$result"
        }

        SECRET_KEY=$(generate_secure_random 32)

        # Create settings.yml automatically
        echo "📝 Creating SearXNG configuration..."
        mkdir -p "$DATA_DIR/config"
        cat > "$DATA_DIR/config/settings.yml" <<EOF
# SearXNG settings - Auto-generated by provisioning script
use_default_settings: true

general:
  debug: false
  instance_name: "$INSTANCE_NAME"

search:
  safe_search: 2
  autocomplete: 'duckduckgo'
  formats:
    - html

server:
  secret_key: "$SECRET_KEY"
  limiter: true
  image_proxy: true
  base_url: https://$DOMAIN

ui:
  default_locale: 'en'
  default_theme: 'simple'

valkey:
  url: valkey://searxng-valkey:6379/0
EOF

        echo "✅ Configuration created automatically"
        notify_webhook "provisioning" "config_ready" "✅ SearXNG configuration created"

        # Create docker-compose.yml automatically
        echo "🐳 Creating docker-compose.yml..."
        cat > "docker-compose.yml" <<EOF
version: '3.9'

services:
  searxng:
    container_name: searxng
    image: docker.io/searxng/searxng:$SEARXNG_VERSION
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - "./config:/etc/searxng:ro"
      - "./data:/var/cache/searxng"
    environment:
      - SEARXNG_SECRET_KEY=$SECRET_KEY
      - SEARXNG_BASE_URL=https://$DOMAIN
    depends_on:
      - searxng-valkey
    networks:
      - searxng-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  searxng-valkey:
    container_name: searxng-valkey
    image: valkey/valkey:7.2.5-alpine
    restart: unless-stopped
    volumes:
      - "valkey-data:/data"
    networks:
      - searxng-network
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  valkey-data:

networks:
  searxng-network:
    driver: bridge
EOF

        echo "✅ docker-compose.yml created automatically"
        notify_webhook "provisioning" "compose_ready" "✅ Docker Compose configuration ready"

        # ========== START SEARXNG CONTAINER ==========
        echo "[6/10] Starting SearXNG container services..."
        notify_webhook "provisioning" "container_start" "Starting SearXNG services"

        # Pull images with retry logic
        echo "📥 Pulling Docker images..."
        for i in {1..3}; do
            if docker compose pull --quiet; then
                echo "✅ Images pulled successfully on attempt $i"
                break
            fi
            echo "⚠️ Image pull attempt $i failed; retrying..."
            sleep 10
            [ $i -eq 3 ] && {
                echo "❌ Failed to pull images after 3 attempts"
                notify_webhook "failed" "image_pull_failed" "Failed to pull Docker images after 3 attempts"
                exit 1
            }
        done

        # Start services
        if docker compose up -d; then
            echo "✅ SearXNG container started successfully"
            notify_webhook "provisioning" "container_started" "✅ SearXNG container started successfully"
        else
            echo "❌ Failed to start SearXNG container"
            notify_webhook "failed" "container_start_failed" "Failed to start SearXNG container"
            exit 1
        fi

        # Wait for services to be ready with comprehensive health checks
        echo "⏳ Waiting for SearXNG services to be ready..."
        notify_webhook "provisioning" "health_check" "Checking SearXNG health"

        # Check Valkey health
        for i in {1..30}; do
            if docker compose exec -T searxng-valkey valkey-cli ping | grep -q PONG; then
                echo "✅ Valkey is ready"
                break
            fi
            if [ $i -eq 30 ]; then
                echo "⚠️ Valkey slow to start, but continuing..."
                notify_webhook "warning" "valkey_slow_start" "Valkey taking longer than expected to start"
            fi
            sleep 2
        done

        # Check SearXNG health
        for i in {1..30}; do
            if curl -s -f http://localhost:8080 >/dev/null 2>&1; then
                echo "✅ SearXNG is responding"
                notify_webhook "provisioning" "searxng_ready" "✅ SearXNG is ready and responding"
                break
            fi
            if [ $i -eq 30 ]; then
                echo "⚠️ SearXNG slow to start, but continuing..."
                notify_webhook "warning" "searxng_slow_start" "SearXNG taking longer than expected to start"
            fi
            sleep 2
        done

    else
        # ========== AUTOMATED MANUAL INSTALLATION ==========
        echo "[4/10] Starting automated manual SearXNG installation..."
        notify_webhook "provisioning" "manual_install" "Beginning automated manual SearXNG installation"

        # Install additional dependencies for manual installation
        echo "[5/10] Installing SearXNG dependencies..."
        notify_webhook "provisioning" "manual_dependencies" "Installing SearXNG specific packages"

        apt-get install -y -q \
            python3-dev python3-babel python3-venv python-is-python3 \
            uwsgi uwsgi-plugin-python3 \
            git build-essential libxslt-dev zlib1g-dev libffi-dev libssl-dev || {
            echo "❌ Failed to install SearXNG dependencies"
            notify_webhook "failed" "searxng_deps_failed" "Failed to install SearXNG specific packages"
            exit 1
        }

        # ========== CREATE SEARXNG USER ==========
        echo "[6/10] Creating SearXNG user..."
        notify_webhook "provisioning" "user_creation" "Creating dedicated SearXNG user"

        if ! id "searxng" &>/dev/null; then
            useradd --shell /bin/bash --system \
                --home-dir "/usr/local/searxng" \
                --comment 'Privacy-respecting metasearch engine' \
                searxng || {
                echo "❌ Failed to create searxng user"
                notify_webhook "failed" "user_creation_failed" "Failed to create searxng user"
                exit 1
            }
            echo "✅ SearXNG user created"
        else
            echo "✅ SearXNG user already exists"
        fi

        mkdir -p "/usr/local/searxng"
        chown -R "searxng:searxng" "/usr/local/searxng"

        # ========== AUTOMATED SEARXNG INSTALLATION ==========
        echo "[7/10] Automating SearXNG installation..."
        notify_webhook "provisioning" "source_install" "Installing SearXNG from source code automatically"

        # Execute installation as searxng user
        su - searxng -c '
        set -e
        cd /usr/local/searxng
        
        echo "Cloning SearXNG repository..."
        if [ ! -d "searxng-src" ]; then
            git clone "https://github.com/searxng/searxng" "searxng-src" || exit 1
        fi

        echo "Creating Python virtual environment..."
        python3 -m venv "searx-pyenv" || exit 1
        
        echo "Activating virtual environment and installing dependencies..."
        source searx-pyenv/bin/activate
        
        # Update pip and install dependencies
        pip install -U pip setuptools wheel || exit 1
        pip install -U pyyaml msgspec || exit 1

        echo "Installing SearXNG..."
        cd "searxng-src"
        pip install --use-pep517 --no-build-isolation -e . || exit 1
        
        echo "SearXNG installation completed successfully"
        ' || {
            echo "❌ Automated SearXNG installation failed"
            notify_webhook "failed" "installation_failed" "Automated SearXNG installation failed"
            exit 1
        }

        echo "✅ SearXNG installed successfully"
        notify_webhook "provisioning" "searxng_installed" "✅ SearXNG installed from source automatically"

        # ========== AUTOMATED CONFIGURATION ==========
        echo "[8/10] Automating SearXNG configuration..."
        notify_webhook "provisioning" "configuration" "Setting up SearXNG configuration automatically"

        mkdir -p "/etc/searxng"

        # Generate secure secret key
        SECRET_KEY=$(openssl rand -hex 64 2>/dev/null || head -c 64 /dev/urandom | xxd -p -c 64)

        # Create settings.yml automatically
        cat > "/etc/searxng/settings.yml" <<EOF
# SearXNG settings - Auto-generated by provisioning script
use_default_settings: true

general:
  debug: false
  instance_name: "$INSTANCE_NAME"

search:
  safe_search: 2
  autocomplete: 'duckduckgo'
  formats:
    - html

server:
  secret_key: "$SECRET_KEY"
  limiter: true
  image_proxy: true
  base_url: https://$DOMAIN

ui:
  default_locale: 'en'
  default_theme: 'auto'
EOF

        chown searxng:searxng "/etc/searxng/settings.yml"
        chmod 600 "/etc/searxng/settings.yml"

        echo "✅ Configuration created automatically"
        notify_webhook "provisioning" "config_ready" "✅ SearXNG configuration complete"

        # ========== AUTOMATED SERVICE SETUP ==========
        echo "[9/10] Setting up automated service..."
        notify_webhook "provisioning" "service_setup" "Configuring SearXNG service automatically"

        cat > "/etc/systemd/system/searxng.service" <<EOF
[Unit]
Description=SearXNG metasearch engine
After=network.target
Wants=network.target

[Service]
Type=exec
User=searxng
Group=searxng
WorkingDirectory=/usr/local/searxng/searxng-src
Environment=SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml
Environment=PYTHONPATH=/usr/local/searxng/searxng-src
ExecStart=/usr/local/searxng/searx-pyenv/bin/python searx/webapp.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

        systemctl daemon-reload
        systemctl enable searxng

        # Start service with retry logic
        for i in {1..3}; do
            if systemctl start searxng; then
                echo "✅ SearXNG service started successfully on attempt $i"
                break
            fi
            echo "⚠️ Service start attempt $i failed; retrying..."
            sleep 5
            [ $i -eq 3 ] && {
                echo "❌ Failed to start SearXNG service after 3 attempts"
                notify_webhook "failed" "service_start_failed" "Failed to start SearXNG service after 3 attempts"
                exit 1
            }
        done

        # Wait for service to be ready
        sleep 5
        if systemctl is-active --quiet searxng; then
            echo "✅ SearXNG service is running"
            notify_webhook "provisioning" "service_running" "✅ SearXNG service is running"
        else
            echo "❌ SearXNG service failed to start"
            journalctl -u searxng --no-pager | tail -n 20
            notify_webhook "failed" "service_failed" "SearXNG service failed to start"
            exit 1
        fi
    fi

    # ========== FIREWALL CONFIGURATION ==========
    echo "[7/10] Configuring firewall automatically..."
    notify_webhook "provisioning" "firewall" "Setting up UFW firewall automatically"

    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable

    echo "✅ Firewall configured automatically"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with required ports"

    # ========== AUTOMATED NGINX + SSL SETUP ==========
    echo "[8/10] Automating nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL automatically"

    # Clean up existing configs
    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/searxng
    rm -f /etc/nginx/sites-enabled/searxng

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf || true
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem || true

    # Determine backend port
    if [ "$DEPLOYMENT_TYPE" = "container" ]; then
        BACKEND_PORT="8080"
        BACKEND_HOST="127.0.0.1"
    else
        BACKEND_PORT="$PORT"
        BACKEND_HOST="127.0.0.1"
    fi

    # Create temporary HTTP config for certbot
    cat > /etc/nginx/sites-available/searxng <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    root /var/www/html;
    
    # For certbot validation
    location ~ /\.well-known/acme-challenge {
        allow all;
        root /var/www/html;
    }
    
    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/searxng /etc/nginx/sites-enabled/searxng
    
    # Test and start nginx
    if nginx -t; then
        systemctl restart nginx
        echo "✅ Nginx temporary config applied"
    else
        echo "❌ Nginx config test failed"
        notify_webhook "failed" "nginx_config_failed" "Nginx configuration test failed"
        exit 1
    fi

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html

    # Automated SSL certificate acquisition
    echo "🔐 Acquiring SSL certificate automatically..."
    notify_webhook "provisioning" "ssl_acquisition" "Automating SSL certificate acquisition"

    MAX_CERTBOT_ATTEMPTS=3
    SSL_OBTAINED=false

    for i in $(seq 1 $MAX_CERTBOT_ATTEMPTS); do
        echo "Attempt $i of $MAX_CERTBOT_ATTEMPTS to obtain SSL certificate..."
        
        if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL" --redirect; then
            SSL_OBTAINED=true
            echo "✅ SSL certificate obtained successfully on attempt $i"
            break
        else
            echo "⚠️ Certbot attempt $i failed"
            
            if [ $i -eq $MAX_CERTBOT_ATTEMPTS ]; then
                echo "⚠️ All Certbot attempts failed, trying webroot method..."
                if certbot certonly --webroot -w /var/www/html -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL"; then
                    SSL_OBTAINED=true
                    echo "✅ SSL certificate obtained via webroot method"
                fi
            fi
        fi
        sleep 10
    done

    if [ "$SSL_OBTAINED" = true ]; then
        echo "✅ SSL certificate setup completed"
        notify_webhook "provisioning" "ssl_ready" "✅ SSL certificate obtained successfully"
    else
        echo "⚠️ SSL certificate acquisition failed, continuing with HTTP only"
        notify_webhook "warning" "ssl_failed" "SSL certificate setup failed, continuing without HTTPS"
    fi

    # ========== FINAL NGINX CONFIG ==========
    echo "[9/10] Applying final nginx configuration..."
    notify_webhook "provisioning" "final_config" "Applying final nginx configuration"

    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        # SSL configuration
        cat > /etc/nginx/sites-available/searxng <<EOF
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

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 10M;

    location / {
        proxy_pass http://$BACKEND_HOST:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_buffering off;
    }

    # Static files cache
    location /static {
        proxy_pass http://$BACKEND_HOST:$BACKEND_PORT/static;
        proxy_set_header Host \$host;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /healthz {
        proxy_pass http://$BACKEND_HOST:$BACKEND_PORT;
        proxy_set_header Host \$host;
        access_log off;
    }
}
EOF
    else
        # HTTP only configuration
        cat > /etc/nginx/sites-available/searxng <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 10M;

    location / {
        proxy_pass http://$BACKEND_HOST:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_buffering off;
    }

    # Static files cache
    location /static {
        proxy_pass http://$BACKEND_HOST:$BACKEND_PORT/static;
        proxy_set_header Host \$host;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /healthz {
        proxy_pass http://$BACKEND_HOST:$BACKEND_PORT;
        proxy_set_header Host \$host;
        access_log off;
    }
}
EOF
    fi

    # Test and apply final nginx config
    if nginx -t; then
        systemctl reload nginx
        echo "✅ Final nginx configuration applied successfully"
        notify_webhook "provisioning" "nginx_ready" "✅ Nginx configuration completed"
    else
        echo "❌ Final nginx configuration test failed"
        notify_webhook "failed" "nginx_final_failed" "Final nginx configuration test failed"
        exit 1
    fi

    # ========== FINAL SETUP AND VERIFICATION ==========
    echo "[10/10] Performing final verification..."
    notify_webhook "provisioning" "final_verification" "Performing final setup verification"

    # Setup SSL renewal cron
    (crontab -l 2>/dev/null | grep -v "certbot renew" || true; 
     echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # Wait for services to stabilize
    sleep 10

    # Final health check
    echo "🔍 Performing final health check..."
    MAX_HEALTH_CHECKS=10
    HEALTHY=false

    for i in $(seq 1 $MAX_HEALTH_CHECKS); do
        if [ "$SSL_OBTAINED" = true ]; then
            if curl -s -f "https://$DOMAIN" >/dev/null 2>&1; then
                HEALTHY=true
                break
            fi
        else
            if curl -s -f "http://$DOMAIN" >/dev/null 2>&1; then
                HEALTHY=true
                break
            fi
        fi
        
        if [ $i -eq $MAX_HEALTH_CHECKS ]; then
            echo "⚠️ Final health check failed after $MAX_HEALTH_CHECKS attempts"
            notify_webhook "warning" "final_health_check_failed" "Final health check failed but deployment completed"
        else
            sleep 5
        fi
    done

    if [ "$HEALTHY" = true ]; then
        echo "✅ SearXNG is fully operational and accessible"
        notify_webhook "success" "deployment_complete" "✅ SearXNG deployment completed successfully and is accessible"
    fi

    # Display final summary
    echo "🎉 Automated SearXNG setup complete!"
    notify_webhook "provisioning" "complete" "🎉 Automated SearXNG setup completed successfully"

    cat <<EOF_SUMMARY

=============================================
✅ AUTOMATED SEARXNG DEPLOYMENT COMPLETE
=============================================
🔗 Access URL: https://$DOMAIN
🔍 Instance: $INSTANCE_NAME
📧 Admin: $ADMIN_EMAIL
🏗️ Deployment: $DEPLOYMENT_TYPE
🔐 SSL: $([ "$SSL_OBTAINED" = true ] && echo "Enabled" || echo "Not available")

⚙️ MANAGEMENT COMMANDS:
EOF_SUMMARY

    if [ "$DEPLOYMENT_TYPE" = "container" ]; then
        cat <<EOF_SUMMARY
- Status: cd $DATA_DIR && docker compose ps
- Logs: cd $DATA_DIR && docker compose logs -f
- Restart: cd $DATA_DIR && docker compose restart
- Update: cd $DATA_DIR && docker compose pull && docker compose up -d
EOF_SUMMARY
    else
        cat <<EOF_SUMMARY
- Status: systemctl status searxng
- Logs: journalctl -u searxng -f
- Restart: systemctl restart searxng
- Update: 
  sudo -u searxng bash -c 'cd /usr/local/searxng/searxng-src && git pull && /usr/local/searxng/searx-pyenv/bin/pip install -U -e .'
  systemctl restart searxng
EOF_SUMMARY
    fi

    cat <<EOF_SUMMARY

📊 DEPLOYMENT DETAILS:
- Data Directory: $DATA_DIR
- Configuration: $([ "$DEPLOYMENT_TYPE" = "container" ] && echo "$DATA_DIR/config/settings.yml" || echo "/etc/searxng/settings.yml")
- Log File: /var/log/searxng_setup.log
- Webhook Notifications: $([ -n "$WEBHOOK_URL" ] && echo "Enabled" || echo "Disabled")

🔧 TROUBLESHOOTING:
- Check service status above
- Review log file: /var/log/searxng_setup.log
- Verify nginx: nginx -t
- Check firewall: ufw status

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
  "deployment_type": "__DEPLOYMENT_TYPE__",
  "instance_name": "__INSTANCE_NAME__",
  "domain": "__DOMAIN__",
  "details": {
    "step": "$step",
    "message": "$message"
  }
}
JSON_EOF
)
            curl -s -X POST "__WEBHOOK_URL__" -H "Content-Type: application/json" -d "$JSON_PAYLOAD" \
                 --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 5 --output /dev/null || true
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
    final = final.replace("__DEPLOYMENT_TYPE__", tokens["__DEPLOYMENT_TYPE__"])
    final = final.replace("__INSTANCE_NAME__", tokens["__INSTANCE_NAME__"])
    final = final.replace("__DOMAIN__", tokens["__DOMAIN__"])

    # Replace SSL configuration URLs
    final = final.replace("__LET_OPTIONS_URL__", tokens["__LET_OPTIONS_URL__"])
    final = final.replace("__SSL_DHPARAMS_URL__", tokens["__SSL_DHPARAMS_URL__"])

    return final