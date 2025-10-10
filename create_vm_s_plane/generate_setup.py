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

    # Setup Docker’s official GPG key
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

    # ----------------------------------------------------------
    # Verify OpenSSL availability
    # ----------------------------------------------------------
    echo "🔍 Verifying OpenSSL installation and functionality..."
    OPENSSL_WORKING=false
    if command -v openssl &> /dev/null; then
        echo "✅ OpenSSL found: $(openssl version)"
        if openssl rand -base64 10 &>/dev/null; then
            echo "✅ OpenSSL rand command works"
            OPENSSL_WORKING=true
        else
            echo "⚠️ OpenSSL rand test failed — will use fallback"
            notify_webhook "warning" "openssl_rand_failed" "OpenSSL rand test failed"
        fi
    else
        echo "⚠️ OpenSSL not installed — will use fallback"
        notify_webhook "warning" "openssl_missing" "OpenSSL not found in PATH"
    fi

    # ----------------------------------------------------------
    # Check entropy availability (informational)
    # ----------------------------------------------------------
    if [ -r /proc/sys/kernel/random/entropy_avail ]; then
        ENTROPY=$(cat /proc/sys/kernel/random/entropy_avail)
        echo "🔍 System entropy: $ENTROPY"
        if [ "$ENTROPY" -lt 100 ]; then
            echo "⚠️ Low entropy detected ($ENTROPY) — may slow crypto ops"
            notify_webhook "warning" "low_entropy" "Low entropy: $ENTROPY"
        fi
    fi

    # ----------------------------------------------------------
    # Secure random generation helper
    # ----------------------------------------------------------
    generate_secure_random() {
        local type="$1"   # base64 | hex
        local length="$2" # bytes
        local result=""

        if [ "$OPENSSL_WORKING" = true ]; then
            if [ "$type" = "hex" ]; then
                result=$(openssl rand -hex "$length" 2>/dev/null || true)
            else
                result=$(openssl rand -base64 "$length" 2>/dev/null | tr -d '\n' || true)
            fi
        fi

        # Fallback: /dev/urandom
        if [ -z "$result" ] || [ ${#result} -lt $((length/2)) ]; then
            echo "⚙️ Using /dev/urandom fallback for $type ($length bytes)"
            if [ "$type" = "hex" ]; then
                result=$(head -c "$length" /dev/urandom | xxd -p -c "$length" | tr -d '\n')
            else
                result=$(head -c "$length" /dev/urandom | base64 | tr -d '\n' | head -c $((length*2)))
            fi
        fi

        # Final fallback
        if [ -z "$result" ]; then
            result="$(date +%s%N | sha256sum | head -c $((length*2)))"
        fi

        echo "$result"
    }

    # ----------------------------------------------------------
    # Generate credentials
    # ----------------------------------------------------------
    POSTGRES_USER="plane"
    POSTGRES_DB="plane"
    RABBITMQ_USER="plane"
    RABBITMQ_VHOST="plane"

    POSTGRES_PASSWORD=$(generate_secure_random base64 32)
    RABBITMQ_PASSWORD=$(generate_secure_random base64 32)
    MINIO_PASSWORD=$(generate_secure_random base64 32)
    SECRET_KEY=$(generate_secure_random hex 32)

    # ----------------------------------------------------------
    # Validate credentials
    # ----------------------------------------------------------
    echo "🔍 Validating generated credentials..."
    VALIDATION_FAILED=false

    validate_length() {
        local name="$1"
        local value="$2"
        local minlen="$3"
        if [ -z "$value" ] || [ ${#value} -lt "$minlen" ]; then
            echo "❌ $name too short (${#value} chars)"
            VALIDATION_FAILED=true
        fi
    }

    validate_length "PostgreSQL password" "$POSTGRES_PASSWORD" 20
    validate_length "RabbitMQ password" "$RABBITMQ_PASSWORD" 20
    validate_length "MinIO password" "$MINIO_PASSWORD" 20
    validate_length "Secret key" "$SECRET_KEY" 40

    if [ "$VALIDATION_FAILED" = true ]; then
        echo "❌ ERROR: One or more generated credentials failed validation"
        notify_webhook "failed" "credentials_validation_failed" "Credential validation failed (entropy or OpenSSL issue)"
        exit 1
    fi

    export POSTGRES_USER POSTGRES_DB POSTGRES_PASSWORD \
        RABBITMQ_USER RABBITMQ_PASSWORD RABBITMQ_VHOST \
        MINIO_PASSWORD SECRET_KEY

    echo "✅ Credentials generated successfully using $([ "$OPENSSL_WORKING" = true ] && echo "OpenSSL" || echo "fallback")"
    notify_webhook "provisioning" "credentials_ready" "✅ All credentials generated successfully"
    sleep 5

    # ==========================================================
    # 🧱 Update .env Files from cloned repository with our credentials
    # ==========================================================
    echo "🛠️ Updating .env files with secure credentials and domain..."

    # We're already in the cloned plane directory, update existing .env files
    # Update the main .env file if it exists
    if [ -f ".env" ]; then
        sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" .env
        sed -i "s/^RABBITMQ_PASSWORD=.*/RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD/" .env
        sed -i "s/^AWS_SECRET_ACCESS_KEY=.*/AWS_SECRET_ACCESS_KEY=$MINIO_PASSWORD/" .env
        echo "✅ Updated main .env file with secure credentials"
    else
        # Create main .env if it doesn't exist
        cat > ".env" <<EOF
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB
PGDATA=/var/lib/postgresql/data
REDIS_HOST=plane-redis
REDIS_PORT=6379
AWS_ACCESS_KEY_ID=plane
AWS_SECRET_ACCESS_KEY=$MINIO_PASSWORD
AWS_S3_BUCKET_NAME=uploads
AWS_S3_ENDPOINT_URL=http://plane-minio:9000
AWS_REGION=us-east-1
FILE_SIZE_LIMIT=52428800
DOCKERIZED=1
USE_MINIO=1
NGINX_PORT=8080
RABBITMQ_USER=$RABBITMQ_USER
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD
RABBITMQ_VHOST=$RABBITMQ_VHOST
LISTEN_HTTP_PORT=8080
LISTEN_HTTPS_PORT=8443
EOF
        echo "✅ Created main .env file"
    fi

    # Update apiserver/.env
    if [ -f "apiserver/.env" ]; then
        sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" apiserver/.env
        sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" apiserver/.env
        sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=http://$DOMAIN|" apiserver/.env
        sed -i "s|^WEB_URL=.*|WEB_URL=http://$DOMAIN|" apiserver/.env
        echo "✅ Updated apiserver/.env file"
    else
        mkdir -p apiserver
        cat > "apiserver/.env" <<EOF
DEBUG=0
CORS_ALLOWED_ORIGINS=http://$DOMAIN
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_HOST=plane-db
POSTGRES_DB=$POSTGRES_DB
POSTGRES_PORT=5432
DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@plane-db:\$POSTGRES_PORT/\$POSTGRES_DB
REDIS_HOST=plane-redis
REDIS_PORT=6379
REDIS_URL=redis://plane-redis:6379/
AWS_ACCESS_KEY_ID=plane
AWS_SECRET_ACCESS_KEY=$MINIO_PASSWORD
AWS_S3_ENDPOINT_URL=http://plane-minio:9000
AWS_S3_BUCKET_NAME=uploads
FILE_SIZE_LIMIT=52428800
USE_MINIO=1
NGINX_PORT=8080
WEB_URL=http://$DOMAIN
GUNICORN_WORKERS=3
SECRET_KEY=$SECRET_KEY
EOF
        echo "✅ Created apiserver/.env file"
    fi

    # Update web/.env
    if [ -f "web/.env" ]; then
        sed -i "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://$DOMAIN|" web/.env
        sed -i "s|^NEXT_PUBLIC_ADMIN_BASE_URL=.*|NEXT_PUBLIC_ADMIN_BASE_URL=http://$DOMAIN|" web/.env
        sed -i "s|^NEXT_PUBLIC_SPACE_BASE_URL=.*|NEXT_PUBLIC_SPACE_BASE_URL=http://$DOMAIN|" web/.env
        echo "✅ Updated web/.env file"
    else
        mkdir -p web
        cat > "web/.env" <<EOF
NEXT_PUBLIC_API_BASE_URL=http://$DOMAIN
NEXT_PUBLIC_ADMIN_BASE_URL=http://$DOMAIN
NEXT_PUBLIC_ADMIN_BASE_PATH=/god-mode
NEXT_PUBLIC_SPACE_BASE_URL=http://$DOMAIN
NEXT_PUBLIC_SPACE_BASE_PATH=/spaces
EOF
        echo "✅ Created web/.env file"
    fi

    # Update space/.env
    if [ -f "space/.env" ]; then
        sed -i "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://$DOMAIN|" space/.env
        sed -i "s|^NEXT_PUBLIC_WEB_BASE_URL=.*|NEXT_PUBLIC_WEB_BASE_URL=http://$DOMAIN|" space/.env
        echo "✅ Updated space/.env file"
    else
        mkdir -p space
        cat > "space/.env" <<EOF
NEXT_PUBLIC_API_BASE_URL=http://$DOMAIN
NEXT_PUBLIC_WEB_BASE_URL=http://$DOMAIN
NEXT_PUBLIC_SPACE_BASE_PATH=/spaces
EOF
        echo "✅ Created space/.env file"
    fi

    # Update admin/.env
    if [ -f "admin/.env" ]; then
        sed -i "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://$DOMAIN|" admin/.env
        sed -i "s|^NEXT_PUBLIC_WEB_BASE_URL=.*|NEXT_PUBLIC_WEB_BASE_URL=http://$DOMAIN|" admin/.env
        echo "✅ Updated admin/.env file"
    else
        mkdir -p admin
        cat > "admin/.env" <<EOF
NEXT_PUBLIC_API_BASE_URL=http://$DOMAIN
NEXT_PUBLIC_ADMIN_BASE_PATH=/god-mode
NEXT_PUBLIC_WEB_BASE_URL=http://$DOMAIN
EOF
        echo "✅ Created admin/.env file"
    fi

    echo "✅ All .env files updated/created successfully"
    notify_webhook "provisioning" "env_files_ready" "✅ Environment files ready with secure credentials"
    sleep 5

    # ========== Use existing docker-compose.yml from cloned repo ==========
    echo "📁 Using docker-compose.yml from cloned Plane repository..."
    notify_webhook "provisioning" "compose_setup" "Setting up Docker Compose from cloned repo"

    # Check if docker-compose.yml exists in the cloned repo
    if [ ! -f "docker-compose.yml" ]; then
        echo "❌ docker-compose.yml not found in cloned repository"
        echo "🔍 Looking for docker-compose files:"
        find . -name "*docker-compose*" -type f | head -10
        notify_webhook "failed" "compose_missing" "docker-compose.yml not found in cloned repo"
        exit 1
    fi

    echo "✅ Using existing docker-compose.yml from cloned repository ($(wc -l < docker-compose.yml) lines)"
    echo "🔍 First 10 lines of docker-compose.yml:"
    head -10 docker-compose.yml
    notify_webhook "provisioning" "compose_ready" "✅ Docker Compose file ready from repository"

    sleep 5

    # ========== Fix Docker Compose File ==========
    echo "🔧 Adjusting docker-compose.yml for standalone deployment..."
    notify_webhook "provisioning" "compose_adjustment" "Modifying Docker Compose for standalone setup"

    # Verify we can read and modify the file
    echo "🔍 Verifying docker-compose.yml permissions..."
    if [ ! -r "docker-compose.yml" ] || [ ! -w "docker-compose.yml" ]; then
        echo "❌ ERROR: Cannot read or write docker-compose.yml"
        echo "🔍 File permissions: $(ls -l docker-compose.yml)"
        notify_webhook "failed" "compose_permission_denied" "Cannot modify docker-compose.yml - permission issue"
        exit 1
    fi

    # Create backup before modification
    echo "🔍 Creating backup of docker-compose.yml..."
    cp docker-compose.yml docker-compose.yml.backup
    if [ ! -f "docker-compose.yml.backup" ]; then
        echo "❌ ERROR: Failed to create backup file"
        notify_webhook "failed" "backup_failed" "Failed to create docker-compose.yml backup"
        exit 1
    fi

    # Disable proxy service to avoid port conflicts with host nginx
    echo "🔍 Checking for proxy service in docker-compose.yml..."
    if grep -q "proxy:" docker-compose.yml; then
        echo "🔧 Disabling proxy service to avoid port conflicts..."
        if sed -i.bak 's/^  proxy:/  # proxy:/' docker-compose.yml && \
           sed -i 's/^    container_name: proxy/#     container_name: proxy/' docker-compose.yml; then
            echo "✅ Disabled proxy service to avoid port conflicts"
            echo "🔍 Verification - proxy lines should be commented:"
            grep -E "^(  # proxy:|#     container_name: proxy)" docker-compose.yml || echo "⚠️ Could not find commented proxy lines"
            notify_webhook "provisioning" "proxy_disabled" "✅ Proxy service disabled successfully"
        else
            echo "⚠️ Could not disable proxy service, continuing anyway"
            notify_webhook "warning" "proxy_disable_failed" "Failed to disable proxy, may cause port conflicts"
            # Restore backup
            cp docker-compose.yml.backup docker-compose.yml
        fi
    else
        echo "ℹ️  Proxy service not found in docker-compose.yml, skipping"
        notify_webhook "info" "proxy_not_found" "Proxy service not found in compose file"
    fi

    echo "✅ Docker Compose configuration completed"
    notify_webhook "provisioning" "compose_ready" "✅ Docker Compose configuration completed"
    sleep 5
    
    # ==========================================================
    # 🧹 Ensure database and volume directories exist and are writable
    # ==========================================================
    echo "🔍 Preparing Docker volume directories and ensuring permissions..."
    notify_webhook "provisioning" "volume_prep" "Preparing data volumes for Plane services"

    # Use current directory for persistent storage (we're already in /opt/plane/plane)
    mkdir -p pgdata redisdata miniodata rabbitmqdata

    # Set proper permissions
    chown -R 999:999 pgdata
    chown -R 1001:1001 redisdata
    chown -R 1000:1000 miniodata
    chmod -R 755 pgdata redisdata miniodata rabbitmqdata

    # Confirm directory status
    echo "🔍 Checking data directories:"
    ls -ld ./*data 2>/dev/null || true
    df -h . || true

    echo "✅ Volume directories prepared in current Plane directory"
    notify_webhook "provisioning" "volume_ready" "✅ Data directories ready for containers"
    
    sleep 5

    # ==========================================================
    # 🧩 Ensure docker-compose uses correct environment
    # ==========================================================
    # We're already in the plane directory with all .env files, use simple docker compose
    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi

    echo "✅ Docker Compose configured to use current directory .env files"
    
    sleep 5

    # ========== Start Infrastructure ==========
    echo "[8/15] Starting Plane infrastructure (DB, Redis, MQ, MinIO)..."
    notify_webhook "provisioning" "infra_start" "Starting Plane infrastructure services"

    # ========== Start Infrastructure Services Individually ==========
    services=("plane-db" "plane-redis" "plane-mq" "plane-minio")

    for service in "${services[@]}"; do
        echo "🚀 Starting $service..."
        notify_webhook "provisioning" "service_start" "Starting container: $service"

        # Verify service exists in compose file
        if ! grep -q "$service:" docker-compose.yml; then
            echo "⚠️ Service $service not found in docker-compose.yml, skipping"
            notify_webhook "warning" "service_missing" "Service $service not in compose file"
            continue
        fi

        if ! $DOCKER_COMPOSE_CMD up -d "$service"; then
            echo "❌ Failed to start $service"
            notify_webhook "failed" "service_failed" "Failed to start: $service"
            echo "🔍 Checking $service logs:"
            $DOCKER_COMPOSE_CMD logs "$service" --tail=20
            exit 1
        else
            echo "✅ $service started successfully"
            notify_webhook "provisioning" "service_ready" "✅ Container running: $service"
        fi
        sleep 5
    done

    echo "✅ All infrastructure services started"
    notify_webhook "provisioning" "infra_ready" "✅ All infrastructure containers are running"

    # ========== Wait for PostgreSQL and Redis to be ready ==========
    echo "⏳ Waiting for PostgreSQL to be ready..."
    notify_webhook "provisioning" "db_wait" "Waiting for PostgreSQL to become ready"

    MAX_WAIT=60
    count=0
    until $DOCKER_COMPOSE_CMD exec plane-db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; do
        sleep 5
        count=$((count + 1))
        if [ $count -ge $MAX_WAIT ]; then
            echo "❌ PostgreSQL failed to become ready within $((MAX_WAIT*5)) seconds"
            $DOCKER_COMPOSE_CMD logs plane-db --tail=30
            notify_webhook "failed" "postgres_timeout" "PostgreSQL startup timeout"
            exit 1
        fi
        if [ $((count % 4)) -eq 0 ]; then
            echo "   Still waiting for PostgreSQL... ($((count*5))s)"
            notify_webhook "provisioning" "db_waiting" "PostgreSQL still starting... ($((count*5))s)"
        fi
    done
    echo "✅ PostgreSQL is ready"
    notify_webhook "provisioning" "postgres_ready" "✅ PostgreSQL is ready and accepting connections"

    echo "⏳ Waiting for Redis to be ready..."
    notify_webhook "provisioning" "redis_wait" "Waiting for Redis to become ready"

    count=0
    until $DOCKER_COMPOSE_CMD exec plane-redis redis-cli ping >/dev/null 2>&1; do
        sleep 5
        count=$((count + 1))
        if [ $count -ge $MAX_WAIT ]; then
            echo "❌ Redis failed to become ready within $((MAX_WAIT*2)) seconds"
            $DOCKER_COMPOSE_CMD logs plane-redis --tail=30
            notify_webhook "failed" "redis_timeout" "Redis startup timeout"
            exit 1
        fi
    done
    echo "✅ Redis is ready"
    notify_webhook "provisioning" "redis_ready" "✅ Redis is ready and responsive"

    # ========== Run Migrations ==========
    echo "[9/15] Running Plane database migrations..."
    notify_webhook "provisioning" "migrations_start" "Starting database migrations"

    if ! $DOCKER_COMPOSE_CMD run --rm migrator; then
        echo "⚠️ Migration failed on first attempt, retrying..."
        notify_webhook "warning" "migrations_retry" "First migration attempt failed, retrying..."
        sleep 10
        
        if ! $DOCKER_COMPOSE_CMD run --rm migrator; then
            echo "❌ Database migrations failed after retry"
            $DOCKER_COMPOSE_CMD logs migrator --tail=30
            notify_webhook "failed" "migrations_failed" "Database migrations failed after retry"
            exit 1
        fi
    fi
    echo "✅ Database migrations completed successfully"
    notify_webhook "provisioning" "migrations_success" "✅ Database migrations completed successfully"

    # ========== Start Application Services ==========
    echo "[10/15] Starting Plane application services..."
    notify_webhook "provisioning" "app_start" "Starting Plane application services"

    APPLICATION_SERVICES=("api" "web" "admin" "space" "worker" "beat-worker" "live")
    FAILED_SERVICES=()

    for service in "${APPLICATION_SERVICES[@]}"; do
        echo "🚀 Starting $service..."
        notify_webhook "provisioning" "app_service_start" "Starting application service: $service"

        # Verify service exists in compose file
        if ! grep -q "$service:" docker-compose.yml; then
            echo "⚠️ Service $service not found in docker-compose.yml, skipping"
            notify_webhook "warning" "app_service_missing" "Application service $service not in compose file"
            FAILED_SERVICES+=("$service(missing)")
            continue
        fi

        if ! $DOCKER_COMPOSE_CMD up -d "$service"; then
            echo "❌ Failed to start $service"
            notify_webhook "failed" "app_service_failed" "Failed to start: $service"
            $DOCKER_COMPOSE_CMD logs "$service" --tail=20
            FAILED_SERVICES+=("$service")
            # Continue with other services instead of exiting
        else
            echo "✅ $service started successfully"
            notify_webhook "provisioning" "app_service_ready" "✅ Application service running: $service"
        fi
        sleep 5
    done

    # Report on any failed services
    if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
        echo "⚠️ The following services failed to start: ${FAILED_SERVICES[*]}"
        notify_webhook "warning" "some_services_failed" "Some services failed: ${FAILED_SERVICES[*]}"
    else
        echo "✅ All application services started successfully"
        notify_webhook "provisioning" "all_app_services_ready" "✅ All application services are running"
    fi

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
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8080/tcp
    ufw allow 5432/tcp
    ufw allow 6379/tcp  
    ufw allow 9090/tcp                             
    ufw allow "$PORT"/tcp
    ufw --force enable

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
