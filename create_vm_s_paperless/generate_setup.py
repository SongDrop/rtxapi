import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT=8000,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DATA_DIR="/opt/paperless",
    TIMEZONE="UTC",
    DOCKER_COMPOSE_VERSION="v2.27.0",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a full bash provisioning script for Paperless-ngx, in Forgejo/Plane style.
    """

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__DATA_DIR__": DATA_DIR,
        "__TIMEZONE__": TIMEZONE,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DOCKER_COMPOSE_VERSION__": DOCKER_COMPOSE_VERSION,
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Paperless-ngx Provisioning Script (Forgejo/Plane style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/paperless_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    PORT="__PORT__"
    DATA_DIR="__DATA_DIR__"
    TIMEZONE="__TIMEZONE__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"

    echo "[1/15] Starting Paperless-ngx provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Paperless-ngx setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/15] Validating inputs..."
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
    sleep 5

    # ========== PAPERLESS DIRECTORY SETUP ==========
    echo "[5/15] Setting up Paperless directory..."
    notify_webhook "provisioning" "directory_setup" "Creating Paperless directory structure"
    sleep 5

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create Paperless data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Paperless directory"
        exit 1
    }
    cd "$DATA_DIR"
    echo "✅ Paperless directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ Paperless directory created successfully"
    
    sleep 5

    # ========== CREATE DATA DIRECTORIES ==========
    echo "[6/15] Creating data directories..."
    notify_webhook "provisioning" "data_directories" "Creating Paperless data directories"

    # Create required directories for Paperless
    mkdir -p consume data media export
    chmod -R 755 consume data media export

    echo "✅ Data directories created"
    notify_webhook "provisioning" "data_directories_ready" "✅ Paperless data directories created"

    # ========== CREATE DOCKER COMPOSE FILE ==========
    echo "[7/15] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "compose_setup" "Creating Docker Compose configuration"

    cat > "docker-compose.yml" <<'EOF'
version: '3.9'

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - paperless-network

  db:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: paperless
      POSTGRES_USER: paperless
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - db_data:/var/lib/postgresql/data
    networks:
      - paperless-network

  webserver:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    restart: unless-stopped
    depends_on:
      - redis
      - db
    ports:
      - "127.0.0.1:${PAPERLESS_PORT:-8000}:8000"
    environment:
      # Database
      PAPERLESS_DBHOST: db
      PAPERLESS_DBPORT: 5432
      PAPERLESS_DBNAME: paperless
      PAPERLESS_DBUSER: paperless
      PAPERLESS_DBPASS: ${POSTGRES_PASSWORD}

      # Redis
      PAPERLESS_REDIS: redis://redis:6379

      # Security
      PAPERLESS_SECRET_KEY: ${SECRET_KEY}

      # Directories
      PAPERLESS_DATA_DIR: /usr/src/paperless/data
      PAPERLESS_MEDIA_ROOT: /usr/src/paperless/media
      PAPERLESS_CONSUMPTION_DIR: /usr/src/paperless/consume

      # Web
      PAPERLESS_URL: https://${DOMAIN_NAME}

      # OCR and Processing
      PAPERLESS_OCR_LANGUAGE: eng
      PAPERLESS_TIME_ZONE: ${TIMEZONE}
      PAPERLESS_OCR_CLEAN: clean
      PAPERLESS_OCR_OUTPUT_TYPE: pdfa

      # Optional: Tika integration for Office documents
      # PAPERLESS_TIKA_ENABLED: 1
      # PAPERLESS_TIKA_GOTENBERG_ENDPOINT: http://gotenberg:3000
      # PAPERLESS_TIKA_ENDPOINT: http://tika:9998

    volumes:
      - ./data:/usr/src/paperless/data
      - ./media:/usr/src/paperless/media
      - ./consume:/usr/src/paperless/consume
      - ./export:/usr/src/paperless/export
    networks:
      - paperless-network

  # Optional: Tika service for Office document support
  # gotenberg:
  #   image: gotenberg/gotenberg:7.10
  #   restart: unless-stopped
  #   networks:
  #     - paperless-network
  #
  # tika:
  #   image: apache/tika:latest
  #   restart: unless-stopped
  #   networks:
  #     - paperless-network

volumes:
  db_data:
    driver: local
  redis_data:
    driver: local

networks:
  paperless-network:
    driver: bridge
EOF

    echo "✅ Docker Compose file created"
    notify_webhook "provisioning" "compose_ready" "✅ Docker Compose configuration ready"

    # ========== CREATE ENVIRONMENT FILE ==========
    echo "[8/15] Creating environment configuration..."
    notify_webhook "provisioning" "environment_setup" "Creating Paperless environment configuration"

    # Generate secure credentials
    SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n')
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')

    cat > ".env" <<EOF
# Paperless Configuration
DOMAIN_NAME=__DOMAIN__
PAPERLESS_PORT=__PORT__
TIMEZONE=__TIMEZONE__

# Security
SECRET_KEY=${SECRET_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# OCR Configuration
PAPERLESS_OCR_LANGUAGE=eng
PAPERLESS_TIME_ZONE=__TIMEZONE__
EOF

    echo "✅ Environment file created"
    notify_webhook "provisioning" "environment_ready" "✅ Paperless environment configuration created"

    # ========== PRE-STARTUP CHECKS ==========
    echo "[9/15] Running system pre-checks..."
    notify_webhook "provisioning" "system_checks" "Running system pre-checks"

    # Check available disk space (Paperless needs more space for documents)
    echo "    Checking disk space..."
    DISK_AVAILABLE=$(df /var/lib/docker /opt/paperless /tmp . | awk 'NR>1 {print $4}' | sort -n | head -1)
    if [ "$DISK_AVAILABLE" -lt 2097152 ]; then  # Less than 2GB
        echo "    ❌ Insufficient disk space: ${DISK_AVAILABLE}KB available"
        df -h
        notify_webhook "failed" "low_disk_space" "Insufficient disk space for Paperless - only ${DISK_AVAILABLE}KB available"
        exit 1
    fi
    notify_webhook "provisioning" "disk_check" "✅ Disk space sufficient: ${DISK_AVAILABLE}KB available"
    
    # Check memory
    echo "    Checking memory..."
    MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
    if [ "$MEM_AVAILABLE" -lt 1024 ]; then  # Less than 1GB available
        echo "    ⚠️ Low memory available: ${MEM_AVAILABLE}MB (Paperless OCR needs memory)"
        notify_webhook "warning" "low_memory" "Low memory available: ${MEM_AVAILABLE}MB - Paperless OCR may be slow"
    else
        notify_webhook "provisioning" "memory_check" "✅ Memory sufficient: ${MEM_AVAILABLE}MB available"
    fi
    
    # Clean up any existing containers that might conflict
    echo "    Cleaning up any existing containers..."
    notify_webhook "provisioning" "cleanup" "Cleaning up existing containers"
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    sleep 2
    
    echo "✅ System pre-checks passed"
    notify_webhook "provisioning" "system_checks_passed" "✅ All system pre-checks passed"

    # ========== START PAPERLESS SERVICES ==========
    echo "[10/15] Starting Paperless services..."
    notify_webhook "provisioning" "services_start" "Starting Paperless multi-container stack"

    # Detect Docker Compose command
    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi

    # Pull images first
    echo "    Pulling Docker images..."
    notify_webhook "provisioning" "pulling_images" "Pulling Paperless and dependency images"
    
    if ! $DOCKER_COMPOSE_CMD pull --quiet; then
        echo "    ⚠️ Failed to pull some images, but continuing..."
        notify_webhook "warning" "image_pull_failed" "Failed to pull some images, but continuing"
    else
        echo "    ✅ Images pulled successfully"
        notify_webhook "provisioning" "images_pulled" "✅ Docker images pulled successfully"
    fi

    # Start services
    echo "    Starting Paperless stack..."
    notify_webhook "provisioning" "stack_start" "Starting Paperless stack"
    
    if timeout 180s $DOCKER_COMPOSE_CMD up -d; then
        echo "    ✅ Paperless stack started successfully"
        notify_webhook "provisioning" "stack_started" "✅ Paperless stack started successfully"
    else
        echo "    ❌ Failed to start Paperless stack"
        echo "    🔍 Docker Compose output:"
        $DOCKER_COMPOSE_CMD up -d
        echo "    🔍 Container status:"
        $DOCKER_COMPOSE_CMD ps
        notify_webhook "failed" "stack_start_failed" "Failed to start Paperless stack - check Docker logs"
        exit 1
    fi

    # ========== HEALTH CHECKS ==========
    echo "[11/15] Performing health checks..."
    notify_webhook "provisioning" "health_checks" "Checking Paperless services health"

    # Wait for services to initialize (Paperless takes time to setup database)
    echo "    Waiting for Paperless services to initialize..."
    sleep 60

    # Check container status
    echo "    Checking container status..."
    RUNNING_CONTAINERS=$($DOCKER_COMPOSE_CMD ps --services --filter "status=running" | wc -l)
    TOTAL_CONTAINERS=$($DOCKER_COMPOSE_CMD ps --services | wc -l)

    if [ "$RUNNING_CONTAINERS" -eq "$TOTAL_CONTAINERS" ]; then
        echo "    ✅ All containers running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
        notify_webhook "provisioning" "containers_running" "✅ All containers running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
    else
        echo "    ⚠️ Some containers not running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
        $DOCKER_COMPOSE_CMD ps
        notify_webhook "warning" "containers_partial" "Some containers not running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
    fi

    # Check Paperless web service health
    echo "    Checking Paperless web service..."
    READY=false
    for i in {1..40}; do  # Paperless takes longer to start (database migrations)
        if curl -f -s http://localhost:$PORT/api/ >/dev/null 2>&1 || \
           curl -f -s http://localhost:$PORT/admin/ >/dev/null 2>&1; then
            READY=true
            break
        fi
        if [ $((i % 6)) -eq 0 ]; then
            echo "    Still waiting for Paperless... (${i}s)"
            notify_webhook "provisioning" "health_check_progress" "Waiting for Paperless to be ready... (${i}s)"
        fi
        sleep 5
    done

    if [ "$READY" = true ]; then
        echo "    ✅ Paperless is responsive"
        notify_webhook "provisioning" "paperless_healthy" "✅ Paperless is healthy and responsive"
    else
        echo "    ⚠️ Paperless not fully responsive, but continuing..."
        notify_webhook "warning" "paperless_slow_start" "Paperless taking longer to start, but continuing"
    fi

    # ========== CREATE SUPERUSER ==========
    echo "[12/15] Creating superuser account..."
    notify_webhook "provisioning" "create_superuser" "Creating Paperless superuser"

    # Create superuser via Docker exec
    if $DOCKER_COMPOSE_CMD exec -T webserver python3 manage.py createsuperuser --email "$ADMIN_EMAIL" --noinput 2>/dev/null; then
        echo "    ✅ Superuser created successfully"
        notify_webhook "provisioning" "superuser_created" "✅ Paperless superuser created"
    else
        echo "    ⚠️ Could not create superuser automatically - you'll need to create it manually"
        echo "    💡 Run: cd $DATA_DIR && docker compose exec webserver python3 manage.py createsuperuser"
        notify_webhook "warning" "superuser_manual" "Superuser creation failed - manual setup required"
    fi

    # ========== NGINX CONFIG + SSL ==========
    echo "[13/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL"

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/paperless

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/paperless <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/paperless /etc/nginx/sites-enabled/paperless
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
        notify_webhook "warning" "ssl" "Paperless Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/paperless <<'EOF_SSL'
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
EOF_SSL

        ln -sf /etc/nginx/sites-available/paperless /etc/nginx/sites-enabled/paperless
        nginx -t && systemctl reload nginx
    fi

    echo "[14/15] Setup Cron for renewal..."
    notify_webhook "provisioning" "cron_setup" "Setting up SSL certificate renewal"
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "__CERTBOT_CRON__" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FIREWALL CONFIGURATION ==========
    echo "[15/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"

    # SSH access
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable

    echo "✅ Firewall configured"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with required ports"

    # ========== FINAL VERIFICATION ==========
    echo "🔍 Final verification..."
    notify_webhook "provisioning" "final_verification" "Performing final verification"

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

    # Display final status
    echo "📊 Final container status:"
    $DOCKER_COMPOSE_CMD ps

    echo "🎉 Paperless-ngx deployment completed successfully!"
    notify_webhook "success" "deployment_complete" "✅ Paperless-ngx deployment completed successfully"

    cat <<EOF_SUMMARY
=============================================
📄 Paperless-ngx Deployment Complete!
🔗 Access URL: https://$DOMAIN
📧 Admin email: $ADMIN_EMAIL
⏰ Timezone: $TIMEZONE
📁 Document directories:
  - Consumption: $DATA_DIR/consume
  - Media: $DATA_DIR/media  
  - Data: $DATA_DIR/data
  - Export: $DATA_DIR/export
⚙️ Useful commands:
- Status: cd $DATA_DIR && docker compose ps
- Logs: cd $DATA_DIR && docker compose logs -f
- Restart: cd $DATA_DIR && docker compose restart
- Update: cd $DATA_DIR && docker compose pull && docker compose up -d
- Stop: cd $DATA_DIR && docker compose down
📋 Services included:
  • Paperless Web (port $PORT)
  • PostgreSQL Database
  • Redis (Task queue)
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

    return final