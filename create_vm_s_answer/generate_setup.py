import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT=9080,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    ADMIN_NAME="admin",
    SITE_NAME="Apache Answer",
    DB_FILE="/data/answer.db",
    DATA_DIR="/opt/answer",
    DOCKER_COMPOSE_VERSION="v2.27.0",
    DB_TYPE="sqlite3",
    DB_HOST="",
    DB_USERNAME="",
    DB_PASSWORD="",
    DB_NAME="",
):
    """
    Returns a full bash provisioning script for Apache Answer, in Forgejo style.
    """

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__ADMIN_NAME__": ADMIN_NAME,
        "__SITE_NAME__": SITE_NAME,
        "__PORT__": str(PORT),
        "__DATA_DIR__": DATA_DIR,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DOCKER_COMPOSE_VERSION__": DOCKER_COMPOSE_VERSION,
        "__DB_TYPE__": DB_TYPE,
        "__DB_HOST__": DB_HOST,
        "__DB_USERNAME__": DB_USERNAME,
        "__DB_PASSWORD__": DB_PASSWORD,
        "__DB_NAME__": DB_NAME,
        "__DB_FILE__": DB_FILE,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Apache Answer Provisioning Script (Forgejo style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/answer_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    ADMIN_NAME="__ADMIN_NAME__"
    SITE_NAME="__SITE_NAME__"
    PORT="__PORT__"
    DATA_DIR="__DATA_DIR__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DB_TYPE="__DB_TYPE__"
    DB_HOST="__DB_HOST__"
    DB_USERNAME="__DB_USERNAME__"
    DB_PASSWORD="__DB_PASSWORD__"
    DB_NAME="__DB_NAME__"
    DB_FILE="__DB_FILE__"

    echo "[1/12] Starting Apache Answer provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Apache Answer setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/12] Validating inputs..."
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

    # Validate database configuration
    if [[ "$DB_TYPE" == "mysql" || "$DB_TYPE" == "postgres" ]]; then
        if [[ -z "$DB_HOST" || -z "$DB_USERNAME" || -z "$DB_PASSWORD" || -z "$DB_NAME" ]]; then
            echo "ERROR: Database configuration incomplete for $DB_TYPE"
            notify_webhook "failed" "validation" "Database configuration incomplete for $DB_TYPE"
            exit 1
        fi
    fi

    # ========== SYSTEM DEPENDENCIES ==========
    echo "[3/12] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get upgrade -y -q
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx openssl ufw

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

    # ========== ANSWER DIRECTORY SETUP ==========
    echo "[5/12] Setting up Answer directory..."
    notify_webhook "provisioning" "directory_setup" "Creating Answer directory structure"
    sleep 5

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create Answer data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Answer directory"
        exit 1
    }
    cd "$DATA_DIR"
    echo "✅ Answer directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ Answer directory created successfully"
    
    sleep 5

    # ==========================================================
    # 🔐 Generate SIMPLIFIED Secure Credentials
    # ==========================================================
    echo "🔐 Generating secure credentials..."
    notify_webhook "provisioning" "credentials_generation" "Creating secure passwords and keys"

    generate_secure_random() {
        local type="$1"
        local length="$2"
        local result=""

        # Try openssl first
        if command -v openssl &>/dev/null; then
            if [ "$type" = "hex" ]; then
                result=$(openssl rand -hex "$length" 2>/dev/null || true)
            else
                # Use simpler base64 without special characters for PostgreSQL
                result=$(openssl rand -base64 "$length" 2>/dev/null | tr -d '\n+/=' | head -c "$length" || true)
            fi
        fi

        # Fallback to /dev/urandom
        if [ -z "$result" ]; then
            if [ "$type" = "hex" ]; then
                result=$(head -c "$length" /dev/urandom | xxd -p -c "$length" 2>/dev/null || true)
            else
                # Simple alphanumeric for PostgreSQL compatibility
                result=$(head -c "$length" /dev/urandom | base64 | tr -d '\n+/=' | head -c "$length" 2>/dev/null || true)
            fi
        fi

        # Final check
        if [ -z "$result" ]; then
            echo "❌ ERROR: Unable to generate random $type string"
            exit 1
        fi

        echo "$result"
    }

    # Generate SIMPLIFIED credentials (sqlite can be picky about passwords)
    # Set database configuration based on type
    if [[ "$DB_TYPE" == "mysql" ]]; then
        DB_USER="answer"
        DB_PASSWORD="answer_$(generate_secure_random hex 16)"
        DB_NAME="answer"
        DB_FILE=""
    elif [[ "$DB_TYPE" == "postgres" ]]; then
        DB_USER="answer"
        DB_PASSWORD="answer_$(generate_secure_random hex 16)"
        DB_NAME="answer"
        DB_FILE=""
    else
        # SQLite3 (default) - no credentials needed
        DB_USER=""
        DB_PASSWORD=""
        DB_HOST=""
        DB_NAME=""
        DB_FILE="/data/answer.db"
    fi          
                                                                           
    # ========== BUILD CUSTOM ANSWER WITH PLUGINS ==========
    echo "[6/12] Building custom Answer image with plugins..."
    notify_webhook "provisioning" "plugin_build" "Building custom Answer image with plugins"

    # Create Dockerfile for Answer with essential plugins
    cat > "Dockerfile" <<'DOCKERFILE'
FROM apache/answer as answer-builder

FROM golang:1.22-alpine AS golang-builder

COPY --from=answer-builder /usr/bin/answer /usr/bin/answer

RUN apk --no-cache add \
    build-base git bash nodejs npm go && \
    npm install -g pnpm@10.7.0

# Build Answer with essential plugins
RUN answer build \
    --with github.com/apache/answer-plugins/connector-basic \
    --with github.com/apache/answer-plugins/connector-github \
    --with github.com/apache/answer-plugins/connector-google \
    --with github.com/apache/answer-plugins/captcha-basic \
    --with github.com/apache/answer-plugins/storage-s3 \
    --output /usr/bin/new_answer

FROM alpine
LABEL maintainer="answer-setup-script"

ARG TIMEZONE
ENV TIMEZONE=${TIMEZONE:-"UTC"}

RUN apk update \
    && apk --no-cache add \
        bash \
        ca-certificates \
        curl \
        dumb-init \
        sqlite \
        tzdata \
    && ln -sf /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
    && echo "${TIMEZONE}" > /etc/timezone

COPY --from=golang-builder /usr/bin/new_answer /usr/bin/answer
COPY --from=answer-builder /data /data
COPY --from=answer-builder /entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

VOLUME /data
EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
DOCKERFILE

    # Build the custom image with timeout and retry logic
    echo "    Building custom Answer image with plugins..."
    notify_webhook "provisioning" "building_image" "Building custom Answer image with plugins"
    
    MAX_BUILD_RETRIES=2
    BUILD_SUCCESS=false
    
    for attempt in $(seq 1 $MAX_BUILD_RETRIES); do
        echo "    Build attempt $attempt of $MAX_BUILD_RETRIES..."
        
        # Build with timeout to prevent hanging
        if timeout 600 docker build -t answer-with-plugins .; then
            echo "    ✅ Custom Answer image with plugins built successfully (attempt $attempt)"
            notify_webhook "provisioning" "custom_image_built" "✅ Custom Answer image with plugins built successfully"
            CUSTOM_IMAGE="answer-with-plugins"
            BUILD_SUCCESS=true
            break
        else
            echo "    ⚠️ Build attempt $attempt failed or timed out"
            
            # Clean up any failed build artifacts
            docker system prune -f >/dev/null 2>&1 || true
            
            if [ $attempt -eq $MAX_BUILD_RETRIES ]; then
                echo "    ❌ All build attempts failed, using standard image without plugins"
                notify_webhook "warning" "custom_build_failed" "All build attempts failed, using standard Answer image"
                CUSTOM_IMAGE="apache/answer:latest"
            else
                echo "    🔄 Retrying build in 10 seconds..."
                sleep 10
            fi
        fi
    done

    # Clean up Dockerfile regardless of build outcome
    rm -f Dockerfile

    # Verify the custom image actually exists if we think we built it
    if [ "$BUILD_SUCCESS" = true ]; then
        if ! docker image inspect answer-with-plugins >/dev/null 2>&1; then
            echo "    ⚠️ Custom image verification failed, using standard image"
            notify_webhook "warning" "image_verification_failed" "Custom image verification failed, using standard image"
            CUSTOM_IMAGE="apache/answer:latest"
            BUILD_SUCCESS=false
        fi
    fi

    # ========== DOCKER COMPOSE SETUP ==========
    echo "[7/12] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose_setup" "Setting up Docker Compose for Answer"

    # Create docker-compose.yml with custom image
    cat > "docker-compose.yml" <<DOCKERCOMPOSE
version: '3.8'

services:
  answer:
    image: ${CUSTOM_IMAGE}
    container_name: answer
    restart: unless-stopped
    ports:
      - "9080:80"
    volumes:
      - answer_data:/data
    environment:
      - ANSWER_DATA_PATH=/data

volumes:
  answer_data:
    driver: local
DOCKERCOMPOSE

    echo "✅ Docker Compose configuration created"
    if [ "$BUILD_SUCCESS" = true ]; then
        echo "    🎯 Using custom Answer image with plugins"
        notify_webhook "provisioning" "compose_ready" "✅ Docker Compose configuration ready (with plugins)"
    else
        echo "    ℹ️  Using standard Answer image (plugins not available)"
        notify_webhook "provisioning" "compose_ready" "✅ Docker Compose configuration ready (standard image)"
    fi
                                      
    # ========== PRE-STARTUP CHECKS ==========
    echo "[8/12] Running system pre-checks..."
    notify_webhook "provisioning" "system_checks" "Running system pre-checks"

    # Check available disk space
    echo "    Checking disk space..."
    DISK_AVAILABLE=$(df /var/lib/docker /opt/answer /tmp . | awk 'NR>1 {print $4}' | sort -n | head -1)
    if [ "$DISK_AVAILABLE" -lt 1048576 ]; then  # Less than 1GB
        echo "    ❌ Insufficient disk space: ${DISK_AVAILABLE}KB available"
        df -h
        notify_webhook "failed" "low_disk_space" "Insufficient disk space - only ${DISK_AVAILABLE}KB available"
        exit 1
    fi
    notify_webhook "provisioning" "disk_check" "✅ Disk space sufficient: ${DISK_AVAILABLE}KB available"
    
    # Check memory
    echo "    Checking memory..."
    MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
    if [ "$MEM_AVAILABLE" -lt 512 ]; then  # Less than 512MB
        echo "    ⚠️ Low memory available: ${MEM_AVAILABLE}MB"
        notify_webhook "warning" "low_memory" "Low memory available: ${MEM_AVAILABLE}MB"
    else
        notify_webhook "provisioning" "memory_check" "✅ Memory sufficient: ${MEM_AVAILABLE}MB available"
    fi
    
    # Clean up any existing containers
    echo "    Cleaning up any existing containers..."
    notify_webhook "provisioning" "cleanup" "Cleaning up existing containers"
    docker-compose down --remove-orphans >/dev/null 2>&1 || true
    sleep 2
    
    echo "✅ System pre-checks passed"
    notify_webhook "provisioning" "system_checks_passed" "✅ All system pre-checks passed"

    # ========== START ANSWER CONTAINER ==========
    echo "[9/12] Starting Apache Answer container..."
    notify_webhook "provisioning" "answer_start" "Starting Apache Answer container"

    # Skip pull if using custom image
    if [ "$CUSTOM_IMAGE" = "apache/answer:latest" ]; then
        echo "    Pulling Apache Answer image..."
        if docker pull apache/answer:latest; then
            echo "    ✅ Image pulled successfully"
            notify_webhook "provisioning" "image_pulled" "✅ Apache Answer image pulled successfully"
        else
            echo "    ⚠️ Failed to pull image, but continuing..."
            notify_webhook "warning" "image_pull_failed" "Failed to pull Apache Answer image, but continuing"
        fi
    else
        echo "    Using custom built image with plugins"
        notify_webhook "provisioning" "using_custom_image" "Using custom built image with plugins"
    fi

    # Start the container
    echo "    Starting Answer container..."
    if docker-compose up -d; then
        echo "    ✅ Answer container started successfully"
        notify_webhook "provisioning" "container_started" "✅ Apache Answer container started successfully"
        
        # Verify plugins if custom image was built
        if [ "$CUSTOM_IMAGE" = "answer-with-plugins" ]; then
            echo "    🔧 Verifying plugins..."
            sleep 10
            if docker exec answer answer plugin 2>/dev/null; then
                echo "    ✅ Plugins verified successfully"
                notify_webhook "provisioning" "plugins_verified" "✅ Plugins verified successfully"
            else
                echo "    ⚠️ Could not verify plugins, but container is running"
                notify_webhook "warning" "plugins_verification_failed" "Could not verify plugins, but container is running"
            fi
        fi
    else
        echo "    ❌ Failed to start Answer container"
        notify_webhook "failed" "container_start_failed" "Failed to start Apache Answer container"
        exit 1
    fi
                                      
    # ========== WAIT FOR ANSWER INITIALIZATION ==========
    echo "[9/12] Waiting for Answer to initialize..."
    notify_webhook "provisioning" "initialization" "Waiting for Apache Answer to initialize"

    # Wait for Answer to be ready
    READY=false
    for i in {1..30}; do
        if docker ps | grep -q "answer.*Up" && curl -f -s http://localhost:$PORT/healthz >/dev/null 2>&1; then
            READY=true
            break
        fi
        if [ $((i % 6)) -eq 0 ]; then
            echo "    Still waiting for Answer to be ready... ($((i*10))s)"
            notify_webhook "provisioning" "initialization_progress" "Still waiting for Answer to be ready... ($((i*10))s)"
        fi
        sleep 10
    done

    if [ "$READY" = false ]; then
        echo "    ⚠️ Answer taking longer than expected to start, but continuing..."
        notify_webhook "warning" "slow_startup" "Answer taking longer than expected to start, but continuing"
        
        # Check container status
        echo "    🔍 Container status:"
        docker-compose ps
        echo "    🔍 Answer logs:"
        docker-compose logs answer --tail=20
    else
        echo "    ✅ Answer is ready and responsive"
        notify_webhook "provisioning" "answer_ready" "✅ Apache Answer is ready and responsive"
    fi

    # ========== FIREWALL CONFIGURATION ==========
    echo "[10/12] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"

    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable

    echo "✅ Firewall configured"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with required ports"

    # ========== NGINX REVERSE PROXY + SSL ==========
    echo "[11/12] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL"

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/answer

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/answer <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/answer /etc/nginx/sites-enabled/answer
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
        notify_webhook "warning" "ssl_failed" "Certbot failed, SSL not installed for __DOMAIN__"
        
        # Create HTTP-only nginx config
        cat > /etc/nginx/sites-available/answer <<'EOF_HTTP'
server {
    listen 80;
    server_name __DOMAIN__;

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
EOF_HTTP
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "provisioning" "ssl_ready" "✅ SSL certificate obtained"

        # Create HTTPS nginx config
        cat > /etc/nginx/sites-available/answer <<'EOF_SSL'
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
    fi

    ln -sf /etc/nginx/sites-available/answer /etc/nginx/sites-enabled/answer
    nginx -t && systemctl reload nginx

    # Setup cron for SSL renewal
    echo "[12/12] Setting up SSL renewal cron..."
    notify_webhook "provisioning" "cron_setup" "Setting up SSL renewal cron"
    (crontab -l 2>/dev/null | grep -v -F "certbot renew" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FINAL VERIFICATION ==========
    echo "🔍 Performing final verification..."
    notify_webhook "provisioning" "final_verification" "Performing final verification checks"

    # Test nginx configuration
    if ! nginx -t; then
        echo "❌ Nginx configuration test failed"
        notify_webhook "failed" "nginx_test_failed" "Nginx configuration test failed"
        exit 1
    fi

    # Test Answer accessibility
    sleep 10  # Give nginx time to reload
    HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/ || echo "000")
    echo "Answer direct access check returned: $HTTP_RESPONSE"

    if [ "$HTTP_RESPONSE" = "200" ]; then
        echo "✅ Answer is accessible directly on port $PORT"
        notify_webhook "provisioning" "direct_access_ok" "✅ Answer is accessible directly on port $PORT"
    else
        echo "⚠️ Answer direct access returned $HTTP_RESPONSE"
        notify_webhook "warning" "direct_access_issue" "Answer direct access returned $HTTP_RESPONSE"
    fi

    # Check if we can access via domain (if SSL worked)
    if [ -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://__DOMAIN__/ || echo "000")
        echo "HTTPS domain check returned: $HTTPS_RESPONSE"
        if [ "$HTTPS_RESPONSE" = "200" ]; then
            echo "✅ Answer is accessible via HTTPS at __DOMAIN__"
            notify_webhook "provisioning" "https_access_ok" "✅ Answer is accessible via HTTPS at __DOMAIN__"
        else
            echo "⚠️ HTTPS domain access returned $HTTPS_RESPONSE"
            notify_webhook "warning" "https_access_issue" "HTTPS domain access returned $HTTPS_RESPONSE"
        fi
    else
        HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://__DOMAIN__/ || echo "000")
        echo "HTTP domain check returned: $HTTP_RESPONSE"
        if [ "$HTTP_RESPONSE" = "200" ]; then
            echo "✅ Answer is accessible via HTTP at __DOMAIN__"
            notify_webhook "provisioning" "http_access_ok" "✅ Answer is accessible via HTTP at __DOMAIN__"
        else
            echo "⚠️ HTTP domain access returned $HTTP_RESPONSE"
            notify_webhook "warning" "http_access_issue" "HTTP domain access returned $HTTP_RESPONSE"
        fi
    fi

    echo "✅ Apache Answer setup complete!"
    notify_webhook "provisioning" "setup_complete" "✅ Apache Answer deployment completed successfully"

    cat <<EOF_SUMMARY
=============================================
🎉 Apache Answer Setup Complete!
🔗 Access URL: https://__DOMAIN__ (or http://__DOMAIN__)
📊 Direct Access: http://localhost:__PORT__
👤 Admin: __ADMIN_NAME__ (__ADMIN_EMAIL__)
🏠 Site Name: __SITE_NAME__
💾 Data Directory: __DATA_DIR__
🗄️  Database: __DB_TYPE__

⚙️ Useful commands:
- Status: cd $DATA_DIR && docker-compose ps
- Logs: cd $DATA_DIR && docker-compose logs -f answer
- Restart: cd $DATA_DIR && docker-compose restart
- Update: cd $DATA_DIR && docker-compose pull && docker-compose up -d
- Backup: docker exec answer answer dump -p /backup/

📝 Next steps:
1. Visit https://__DOMAIN__ to access your Answer instance
2. Login with admin credentials
3. Configure your community settings
4. Invite users to your Q&A community
=============================================
EOF_SUMMARY

    # Final container status
    echo "📊 Final container status:"
    cd "$DATA_DIR" && docker-compose ps

    notify_webhook "provisioning" "deployment_complete" "🎉 Apache Answer deployment fully completed - Ready for use!"
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

    return final