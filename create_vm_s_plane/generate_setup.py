import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT=3000,
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
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__DATA_DIR__": DATA_DIR,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DOCKER_COMPOSE_VERSION__": DOCKER_COMPOSE_VERSION,
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__PLANE_DOCKER_COMPOSE__": "https://raw.githubusercontent.com/makeplane/plane/refs/heads/preview/docker-compose.yml",
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

    # Ensure prerequisites exist
    apt-get install -y -q ca-certificates curl gnupg lsb-release || {
        notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
        exit 1
    }

    # Remove old versions (ignore errors)
    apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

   # Setup Docker’s official GPG key with retry loop
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

    # ========== PLANE DIRECTORY SETUP ==========
    echo "[6/15] Setting up Plane directory..."
    notify_webhook "provisioning" "directory_setup" "Creating Plane directory structure"
    sleep 5

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create Plane data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Plane directory"
        exit 1
    }
    chown -R 1000:1000 "$DATA_DIR"
    cd "$DATA_DIR"
    echo "✅ Plane directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ Plane directory created successfully"
    
    sleep 5

    # ========== PLANE INSTALL ==========
    echo "[7/15] Installing Plane with Docker Compose..."
    notify_webhook "provisioning" "plane_install" "Setting up Plane with Docker Compose"

    # Navigate to Plane directory with absolute path
    echo "🔍 Navigating to Plane directory: $DATA_DIR"
    cd "$DATA_DIR" || { 
        echo "❌ ERROR: Could not enter $DATA_DIR"
        echo "🔍 Current directory: $(pwd)"
        echo "🔍 Directory contents:"
        ls -la "$DATA_DIR" 2>/dev/null || echo "Cannot list directory"
        notify_webhook "failed" "directory_access" "Cannot access Plane data directory"
        exit 1
    }

    # Clone or update Plane repository with better error handling
    if [ ! -d "plane" ]; then
        echo "📦 Cloning the official Plane repository..."
        notify_webhook "provisioning" "plane_clone_start" "📦 Cloning Plane repository from GitHub"
        
        # Check if we have git and network access
        if ! command -v git &> /dev/null; then
            echo "❌ ERROR: git command not found"
            notify_webhook "failed" "git_missing" "git is not installed"
            exit 1
        fi
        
        if ! timeout 10 git ls-remote https://github.com/makeplane/plane.git &>/dev/null; then
            echo "❌ ERROR: Cannot reach GitHub repository"
            notify_webhook "failed" "network_error" "Cannot access GitHub - check network connectivity"
            exit 1
        fi
        
        if ! git clone https://github.com/makeplane/plane.git; then
            echo "❌ Failed to clone Plane repository"
            echo "🔍 Checking disk space:"
            df -h .
            notify_webhook "failed" "plane_clone_failed" "Git clone failed - check disk space and network"
            exit 1
        fi
        echo "✅ Plane repository cloned successfully"
        notify_webhook "provisioning" "plane_cloned" "✅ Plane repository cloned successfully"
        
        sleep 5
    else
        echo "✅ Plane repository already exists, checking for updates..."
        notify_webhook "provisioning" "plane_update" "Checking for repository updates"
        
        if [ -d "plane" ]; then
            cd plane
            if git pull origin main; then
                echo "✅ Repository updated successfully"
                notify_webhook "provisioning" "plane_updated" "✅ Repository updated successfully"
            else
                echo "⚠️ Could not update repository, continuing with existing version"
                notify_webhook "warning" "plane_update_failed" "Git pull failed, using existing code"
            fi
            cd ..
        else
            echo "❌ ERROR: plane directory disappeared"
            notify_webhook "failed" "directory_disappeared" "plane directory missing after check"
            exit 1
        fi
    fi

    # Enter plane directory with comprehensive error handling
    echo "🔍 Verifying Plane directory structure..."
    if [ ! -d "plane" ]; then
        echo "❌ ERROR: Plane directory not found after clone/update"
        echo "🔍 Current directory: $(pwd)"
        echo "🔍 Directory contents:"
        ls -la
        notify_webhook "failed" "directory_missing" "Plane directory does not exist"
        exit 1
    fi

    # Check directory permissions
    echo "🔍 Checking plane directory permissions..."
    if [ ! -r "plane" ] || [ ! -x "plane" ]; then
        echo "❌ ERROR: Insufficient permissions to access plane directory"
        echo "🔍 Permissions: $(ls -ld plane)"
        notify_webhook "failed" "permission_denied" "Cannot access plane directory - permission issue"
        exit 1
    fi

    cd plane || {
        echo "❌ ERROR: Cannot enter plane directory"
        echo "🔍 Current directory: $(pwd)"
        echo "🔍 plane directory info: $(ls -ld plane)"
        notify_webhook "failed" "directory_access" "Cannot cd into plane directory - permission issue?"
        exit 1
    }

    echo "✅ Successfully entered Plane directory: $(pwd)"
    echo "🔍 Contents of Plane directory:"
    ls -la
    notify_webhook "provisioning" "plane_directory_ready" "✅ In Plane directory, starting configuration"

    # Verify we can write to this directory
    echo "🔍 Testing write permissions..."
    if ! touch write_test.file 2>/dev/null; then
        echo "❌ ERROR: Cannot write to Plane directory - permission denied"
        notify_webhook "failed" "write_permission_denied" "Cannot write to Plane directory"
        exit 1
    fi
    rm -f write_test.file

    sleep 5


    # ==========================================================
    # 🔐 Generate Secure Credentials
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
                result=$(openssl rand -base64 "$length" 2>/dev/null | tr -d '\n' || true)
            fi
        fi

        # Fallback to /dev/urandom if openssl fails
        if [ -z "$result" ]; then
            if [ "$type" = "hex" ]; then
                result=$(head -c "$length" /dev/urandom | xxd -p -c "$length" 2>/dev/null || true)
            else
                result=$(head -c "$length" /dev/urandom | base64 | tr -d '\n' | head -c $((length*2)) 2>/dev/null || true)
            fi
        fi

        # Final check
        if [ -z "$result" ]; then
            echo "❌ ERROR: Unable to generate random $type string"
            exit 1
        fi

        echo "$result"
    }

    # ==========================================================
    # Credentials
    # ==========================================================
    POSTGRES_USER="plane"
    POSTGRES_DB="plane"
    POSTGRES_PASSWORD=$(generate_secure_random base64 32)

    RABBITMQ_USER="plane"
    RABBITMQ_VHOST="plane"
    RABBITMQ_PASSWORD=$(generate_secure_random base64 32)

    MINIO_USER="plane"
    MINIO_PASSWORD=$(generate_secure_random base64 32)

    SECRET_KEY=$(generate_secure_random hex 32)

    # ==========================================================
    # Write stack.env securely
    # ==========================================================
    STACK_ENV="./stack.env"
    umask 077  # ensure file is only readable/writable by owner
    cat > "$STACK_ENV" <<EOF
# PostgreSQL
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB

# Redis
REDIS_HOST=plane-redis
REDIS_PORT=6379

# RabbitMQ
RABBITMQ_USER=$RABBITMQ_USER
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD
RABBITMQ_VHOST=$RABBITMQ_VHOST

# MinIO
AWS_ACCESS_KEY_ID=$MINIO_USER
AWS_SECRET_ACCESS_KEY=$MINIO_PASSWORD
AWS_S3_BUCKET_NAME=uploads
AWS_S3_ENDPOINT_URL=http://plane-minio:9000

# Misc
SECRET_KEY=$SECRET_KEY
FILE_SIZE_LIMIT=52428800
DOCKERIZED=1
USE_MINIO=1
EOF

    echo "✅ stack.env created with secure credentials"
    notify_webhook "provisioning" "credentials_ready" "✅ Credentials generated"
    sleep 5

    # ==========================================================
    # Prepare persistent volume directories
    # ==========================================================
    echo "🔍 Preparing persistent volume directories..."
    VOLUME_DIRS=(/volume1/docker/plane/db \
                /volume1/docker/plane/redis \
                /volume1/docker/plane/rabbitmq \
                /volume1/docker/plane/uploads)

    for dir in "${VOLUME_DIRS[@]}"; do
        mkdir -p "$dir"
        chown 1026:100 "$dir"
        chmod 755 "$dir"
    done

    echo "✅ Volume directories ready"
    notify_webhook "provisioning" "volume_ready" "✅ Volumes ready"


    # ==========================================================
    # Docker Compose command
    # ==========================================================
    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi

    # ==========================================================
    # Start infrastructure services first
    # ==========================================================
    INFRA_SERVICES=("db" "redis" "plane-mq" "minio")
    for service in "${INFRA_SERVICES[@]}"; do
        echo "🚀 Starting $service..."
        notify_webhook "provisioning" "service_start" "Starting $service"
        $DOCKER_COMPOSE_CMD up -d "$service"
    done

    # ==========================================================
    # Wait for healthchecks
    # ==========================================================
    MAX_WAIT=60

    wait_for_postgres() {
        local count=0
        until $DOCKER_COMPOSE_CMD exec -T db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; do
            sleep 5
            count=$((count+1))
            if [ $count -ge $MAX_WAIT ]; then
                echo "❌ PostgreSQL did not become ready"
                $DOCKER_COMPOSE_CMD logs db --tail=30
                exit 1
            fi
        done
        echo "✅ PostgreSQL ready"
    }

    wait_for_redis() {
        local count=0
        until $DOCKER_COMPOSE_CMD exec -T redis redis-cli ping >/dev/null 2>&1; do
            sleep 5
            count=$((count+1))
            if [ $count -ge $MAX_WAIT ]; then
                echo "❌ Redis did not become ready"
                $DOCKER_COMPOSE_CMD logs redis --tail=30
                exit 1
            fi
        done
        echo "✅ Redis ready"
    }

    wait_for_rabbitmq() {
        local count=0
        until $DOCKER_COMPOSE_CMD exec -T plane-mq rabbitmqctl await_startup >/dev/null 2>&1; do
            sleep 5
            count=$((count+1))
            if [ $count -ge $MAX_WAIT ]; then
                echo "❌ RabbitMQ did not become ready"
                $DOCKER_COMPOSE_CMD logs plane-mq --tail=30
                exit 1
            fi
        done
        echo "✅ RabbitMQ ready"
    }

    wait_for_minio() {
        local count=0
        until $DOCKER_COMPOSE_CMD exec -T minio mc alias set local http://localhost:9000 $MINIO_USER $MINIO_PASSWORD >/dev/null 2>&1; do
            sleep 5
            count=$((count+1))
            if [ $count -ge $MAX_WAIT ]; then
                echo "❌ MinIO did not become ready"
                $DOCKER_COMPOSE_CMD logs minio --tail=30
                exit 1
            fi
        done
        echo "✅ MinIO ready"
    }

    wait_for_postgres
    wait_for_redis
    wait_for_rabbitmq
    wait_for_minio

    # ==========================================================
    # Run database migrations
    # ==========================================================
    echo "[9/15] Running migrations..."
    notify_webhook "provisioning" "migrations_start" "Running migrations"
    $DOCKER_COMPOSE_CMD run --rm migrator || {
        sleep 10
        $DOCKER_COMPOSE_CMD run --rm migrator || {
            echo "❌ Migrations failed"
            $DOCKER_COMPOSE_CMD logs migrator --tail=30
            notify_webhook "failed" "migrations_failed" "Migrations failed"
            exit 1
        }
    }
    echo "✅ Migrations completed"

    # ==========================================================
    # Start application services
    # ==========================================================
    APP_SERVICES=("back" "worker" "beat" "front" "space" "admin" "live" "proxy")
    for service in "${APP_SERVICES[@]}"; do
        echo "🚀 Starting $service..."
        notify_webhook "provisioning" "app_service_start" "Starting $service"
        $DOCKER_COMPOSE_CMD up -d "$service"
    done

    echo "✅ Plane deployment complete"
    notify_webhook "provisioning" "all_services_ready" "✅ All services running"


    # ========== Verify API Health ==========
    echo "[11/15] Verifying Plane API health..."
    notify_webhook "provisioning" "health_check" "Checking Plane API health status"

    READY_TIMEOUT=300
    SLEEP_INTERVAL=10
    elapsed=0
    READY=false

    while [ $elapsed -lt $READY_TIMEOUT ]; do
        if docker compose ps api | grep -q "Up" && \
           curl -f -s http://localhost:8000/api/ >/dev/null 2>&1; then
            READY=true
            break
        fi
        echo "   Waiting for API to be ready... (${elapsed}s elapsed)"
        
        # Send progress update every 30 seconds
        if [ $((elapsed % 30)) -eq 0 ]; then
            notify_webhook "provisioning" "health_check_progress" "API health check in progress... (${elapsed}s)"
        fi
        
        sleep $SLEEP_INTERVAL
        elapsed=$((elapsed + SLEEP_INTERVAL))
    done

    if [ "$READY" = false ]; then
        echo "❌ Plane API did not become ready within $READY_TIMEOUT seconds"
        docker compose logs api --tail=30
        docker compose ps
        notify_webhook "failed" "api_health_timeout" "Plane API health check timeout after $READY_TIMEOUT seconds"
        exit 1
    fi

    echo "✅ Plane is fully running and responsive!"
    notify_webhook "provisioning" "plane_healthy" "✅ Plane is fully operational and responsive"

    # Show final container status
    echo "📊 Final container status:"
    docker compose ps

    # Send final success notification
    notify_webhook "provisioning" "plane_deployment_complete" "✅ Plane deployment completed successfully"
                                      
    # ========== FIREWALL ==========
    echo "[8/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"

    # SSH access
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8080/tcp   # Alternate HTTP (if proxy disabled)
    ufw allow 8443/tcp   # Alternate HTTPS (if proxy disabled)
    ufw allow 3000/tcp   # web (frontend)
    ufw allow 3001/tcp   # admin
    ufw allow 3002/tcp   # space
    ufw allow 3100/tcp   # live
    ufw allow 8000/tcp   # api
    ufw allow 5432/tcp   # PostgreSQL
    ufw allow 6379/tcp   # Redis
    ufw allow 5672/tcp   # RabbitMQ
    ufw allow 15672/tcp  # RabbitMQ Management UI
    ufw allow 9000/tcp   # MinIO API
    ufw allow 9090/tcp   # MinIO Console
    ufw allow "$PORT"/tcp
    ufw --force enable
                                      
    echo "✅ Firewall configured — all Plane service ports allowed"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with all required Plane ports"


    # ========== NGINX CONFIG + SSL (Forgejo / fail-safe) ==========
    echo "[18/20] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/plane

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
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
    nginx -t && systemctl restart nginx

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html

    #use --staging if u reach daily limit
    #certbot --nginx -d "__DOMAIN__" --staging --non-interactive --agree-tos -m "__ADMIN_EMAIL__"
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
        cat > /etc/nginx/sites-available/plane <<'EOF_SSL'
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
        proxy_pass http://127.0.0.1:80;
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

        ln -sf /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/plane
        nginx -t && systemctl reload nginx
    fi

    echo "[14/15] Setup Cron for renewal..."
    notify_webhook "provisioning" "provisioning" "Setup Cron for renewal..."
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "__CERTBOT_CRON__" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FINAL CHECKS ==========
    echo "[15/15] Final verification..."
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

    echo "✅ Plane setup complete!"
    notify_webhook "provisioning" "provisioning" "✅ Plane deployment succeeded"

    #wait 60 seconds until everything is fully ready 
    sleep 60
                                      
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
    final = final.replace("__PLANE_DOCKER_COMPOSE__", tokens["__PLANE_DOCKER_COMPOSE__"])

    # Replace CERTBOT_CRON token
    certbot_cron = "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
    final = final.replace("__CERTBOT_CRON__", certbot_cron)

    # Replace remaining tokens for password, admin email, domain, port
    final = final.replace("__ADMIN_PASSWORD__", tokens["__ADMIN_PASSWORD__"])
    final = final.replace("__ADMIN_EMAIL__", tokens["__ADMIN_EMAIL__"])
    final = final.replace("__DOMAIN__", tokens["__DOMAIN__"])
    final = final.replace("__PORT__", tokens["__PORT__"])

    return final
