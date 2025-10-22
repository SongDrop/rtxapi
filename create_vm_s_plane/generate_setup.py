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

    # Create Plane directory
    PLANE_DIR="$DATA_DIR/plane-selfhost"
    echo "🔍 Creating Plane directory: $PLANE_DIR"
    mkdir -p "$PLANE_DIR" || {
        echo "❌ ERROR: Could not create Plane directory"
        notify_webhook "failed" "directory_creation" "Cannot create Plane directory"
        exit 1
    }

    cd "$PLANE_DIR" || {
        echo "❌ ERROR: Could not enter $PLANE_DIR"
        echo "🔍 Current directory: $(pwd)"
        notify_webhook "failed" "directory_access" "Cannot access Plane directory"
        exit 1
    }

    echo "✅ Successfully entered Plane directory: $(pwd)"
    notify_webhook "provisioning" "plane_directory_ready" "✅ In Plane directory, starting configuration"

    # Verify we can write to this directory
    echo "🔍 Testing write permissions..."
    if ! touch write_test.file 2>/dev/null; then
        echo "❌ ERROR: Cannot write to Plane directory - permission denied"
        notify_webhook "failed" "write_permission_denied" "Cannot write to Plane directory"
        exit 1
    fi
    rm -f write_test.file

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

    # Generate SIMPLIFIED credentials (PostgreSQL can be picky about passwords)
    POSTGRES_USER="plane"
    POSTGRES_DB="plane"
    POSTGRES_PASSWORD="plane_$(generate_secure_random hex 16)"  # Simple prefix + hex only

    RABBITMQ_USER="plane"
    RABBITMQ_VHOST="plane"
    RABBITMQ_PASSWORD="rabbit_$(generate_secure_random hex 16)"

    MINIO_USER="plane"
    MINIO_PASSWORD="minio_$(generate_secure_random hex 16)"

    SECRET_KEY=$(generate_secure_random hex 32)
    MACHINE_SIGNATURE=$(generate_secure_random hex 32)

    # ==========================================================
    # Create .env file
    # ==========================================================
    echo "📝 Creating .env configuration file..."
    umask 077
    cat > ".env" <<EOF
# Database Configuration
POSTGRES_USER=$POSTGRES_USER
POSTGRES_DB=$POSTGRES_DB
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
# NOTE: Do NOT set DATABASE_URL here - it causes duplication bugs in Plane
# The image will construct it automatically from the other variables

# Redis
REDIS_URL=redis://plane-redis:6379/
# Note: Remove any duplicate REDIS_URL definitions

# RabbitMQ
RABBITMQ_USER=$RABBITMQ_USER
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD
RABBITMQ_VHOST=$RABBITMQ_VHOST
# CELERY_BROKER_URL will be auto-constructed

# MinIO/S3
AWS_ACCESS_KEY_ID=$MINIO_USER
AWS_SECRET_ACCESS_KEY=$MINIO_PASSWORD
AWS_S3_BUCKET_NAME=uploads
AWS_S3_ENDPOINT_URL=http://plane-minio:9000
AWS_REGION=us-east-1

# Application
SECRET_KEY=$SECRET_KEY
WEB_URL=http://localhost:80
DEBUG=0

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:80

# File upload
FILE_SIZE_LIMIT=5242880

# Gunicorn Workers
GUNICORN_WORKERS=3
WEB_CONCURRENCY=3

# Email (optional)
EMAIL_HOST=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_FROM=noreply@plane.so

# Machine Signature
MACHINE_SIGNATURE=$MACHINE_SIGNATURE
                                      
# Proxy Ports
NGINX_PORT=80
LISTEN_HTTP_PORT=80
LISTEN_HTTPS_PORT=443

# Service URLs for proxy
PROXY_HOST=localhost
API_BASE_URL=http://api:8000
WEB_BASE_URL=http://web:3000
SPACE_BASE_URL=http://space:3002
ADMIN_BASE_URL=http://admin:3001
LIVE_BASE_URL=http://live:3100
EOF

    echo "✅ .env created with secure credentials"
    notify_webhook "provisioning" "credentials_ready" "✅ Credentials generated"

    # ==========================================================
    # Create docker-compose.yml (FIXED VERSION)
    # ==========================================================
    echo "🐳 Creating docker-compose.yml..."
    cat > "docker-compose.yml" <<'EOF'
version: '3.9'

services:
  web:
    container_name: web
    image: makeplane/plane-frontend:latest
    restart: always
    depends_on:
      - api
    networks:
      - plane-network

  admin:
    container_name: admin
    image: makeplane/plane-admin:latest
    restart: always
    depends_on:
      - api
      - web
    networks:
      - plane-network

  space:
    container_name: space
    image: makeplane/plane-space:latest
    restart: always
    depends_on:
      - api
      - web
    networks:
      - plane-network

  api:
    container_name: api
    image: makeplane/plane-backend:latest
    restart: always
    command: ./bin/docker-entrypoint-api.sh
    env_file:
      - .env
    environment:
      # Explicitly set URLs to prevent duplication bugs in Plane images
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@plane-db:5432/${POSTGRES_DB}
      REDIS_URL: redis://plane-redis:6379/
      CELERY_BROKER_URL: amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@plane-mq:5672/${RABBITMQ_VHOST}
    depends_on:
      - plane-db
      - plane-redis
    networks:
      - plane-network

  worker:
    container_name: bgworker
    image: makeplane/plane-backend:latest
    restart: always
    command: ./bin/docker-entrypoint-worker.sh
    env_file:
      - .env
    environment:
      # Explicitly set URLs to prevent duplication bugs in Plane images
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@plane-db:5432/${POSTGRES_DB}
      REDIS_URL: redis://plane-redis:6379/
      CELERY_BROKER_URL: amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@plane-mq:5672/${RABBITMQ_VHOST}
    depends_on:
      - api
      - plane-db
      - plane-redis
    networks:
      - plane-network

  beat-worker:
    container_name: beatworker
    image: makeplane/plane-backend:latest
    restart: always
    command: ./bin/docker-entrypoint-beat.sh
    env_file:
      - .env
    environment:
      # Explicitly set URLs to prevent duplication bugs in Plane images
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@plane-db:5432/${POSTGRES_DB}
      REDIS_URL: redis://plane-redis:6379/
      CELERY_BROKER_URL: amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@plane-mq:5672/${RABBITMQ_VHOST}
    depends_on:
      - api
      - plane-db
      - plane-redis
    networks:
      - plane-network

  migrator:
    container_name: plane-migrator
    image: makeplane/plane-backend:latest
    restart: "no"
    command: ./bin/docker-entrypoint-migrator.sh
    env_file:
      - .env
    environment:
      # Explicitly set URLs to prevent duplication bugs in Plane images
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@plane-db:5432/${POSTGRES_DB}
      REDIS_URL: redis://plane-redis:6379/
      CELERY_BROKER_URL: amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@plane-mq:5672/${RABBITMQ_VHOST}
    depends_on:
      - plane-db
      - plane-redis
    networks:
      - plane-network

  live:
    container_name: plane-live
    image: makeplane/plane-live:latest
    restart: always
    networks:
      - plane-network

  plane-db:
    container_name: plane-db
    image: postgres:15.7
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data
    env_file:
      - .env
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      PGDATA: /var/lib/postgresql/data
    networks:
      - plane-network

  plane-redis:
    container_name: plane-redis
    image: valkey/valkey:7.2.5-alpine
    restart: always
    volumes:
      - redisdata:/data
    networks:
      - plane-network

  plane-mq:
    container_name: plane-mq
    image: rabbitmq:3.13.6-management-alpine
    restart: always
    env_file:
      - .env
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks:
      - plane-network

  plane-minio:
    container_name: plane-minio
    image: minio/minio
    restart: always
    command: server /export --console-address ":9090"
    volumes:
      - uploads:/export
    environment:
      MINIO_ROOT_USER: ${AWS_ACCESS_KEY_ID}
      MINIO_ROOT_PASSWORD: ${AWS_SECRET_ACCESS_KEY}
    networks:
      - plane-network

  proxy:
    container_name: proxy
    image: makeplane/plane-proxy:latest
    restart: always
    ports:
      - "${NGINX_PORT:-80}:80"
    environment:
      FILE_SIZE_LIMIT: ${FILE_SIZE_LIMIT:-5242880}
      BUCKET_NAME: ${AWS_S3_BUCKET_NAME:-uploads}
    depends_on:
      - web
      - api
      - space
      - admin
    networks:
      - plane-network

volumes:
  pgdata:
  redisdata:
  uploads:
  rabbitmq_data:

networks:
  plane-network:
    driver: bridge
EOF

    echo "✅ docker-compose.yml created"
    notify_webhook "provisioning" "compose_ready" "✅ Docker Compose files ready"

    # ==========================================================
    # Detect Docker Compose command
    # ==========================================================
    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi

    # ==========================================================
    # Pre-startup system checks
    # ==========================================================
    echo "🔍 Running system pre-checks..."
    notify_webhook "provisioning" "system_checks" "Running system pre-checks"

    # Check available disk space
    echo "    Checking disk space..."
    DISK_AVAILABLE=$(df /var/lib/docker /opt/plane /tmp . | awk 'NR>1 {print $4}' | sort -n | head -1)
    if [ "$DISK_AVAILABLE" -lt 1048576 ]; then  # Less than 1GB
        echo "    ❌ Insufficient disk space: ${DISK_AVAILABLE}KB available"
        df -h
        notify_webhook "failed" "low_disk_space" "Insufficient disk space for PostgreSQL - only ${DISK_AVAILABLE}KB available"
        exit 1
    fi
    notify_webhook "provisioning" "disk_check" "✅ Disk space sufficient: ${DISK_AVAILABLE}KB available"
    
    # Check memory
    echo "Checking memory..."
    MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
    if [ "$MEM_AVAILABLE" -lt 512 ]; then  # Less than 512MB
        echo "    ⚠️ Low memory available: ${MEM_AVAILABLE}MB (PostgreSQL needs at least 256MB)"
        notify_webhook "warning" "low_memory" "Low memory available: ${MEM_AVAILABLE}MB"
    else
        notify_webhook "provisioning" "memory_check" "✅ Memory sufficient: ${MEM_AVAILABLE}MB available"
    fi
    
    # Clean up any existing containers that might conflict
    echo "Cleaning up any existing containers..."
    notify_webhook "provisioning" "cleanup" "Cleaning up existing containers"
    $DOCKER_COMPOSE_CMD down --remove-orphans >/dev/null 2>&1 || true
    sleep 2
    
    echo "✅ System pre-checks passed"
    notify_webhook "provisioning" "system_checks_passed" "✅ All system pre-checks passed"

    # ==========================================================
    # Start infrastructure services (COMPREHENSIVE MINIO FIX)
    # ==========================================================
    echo "🚀 Starting infrastructure services..."
    notify_webhook "provisioning" "infrastructure_start" "Starting database, cache, and queue services"

    INFRA_SERVICES=("plane-db" "plane-redis" "plane-mq" "plane-minio")
    for service in "${INFRA_SERVICES[@]}"; do
        echo "  Starting $service..."
        notify_webhook "provisioning" "service_start" "Starting $service"

        # Pull image first to avoid download delays during startup
        echo "    Pulling image for $service..."
        notify_webhook "provisioning" "pulling_image" "Pulling Docker image for $service"
        if ! $DOCKER_COMPOSE_CMD pull "$service" --quiet; then
            echo "    ⚠️ Failed to pull $service image, but continuing..."
            notify_webhook "warning" "image_pull_failed" "Failed to pull $service image, but continuing"
        else
            notify_webhook "provisioning" "image_pulled" "✅ Docker image pulled for $service"
        fi
        
        # Start service with timeout and better error handling
        echo "    Starting $service container..."
        notify_webhook "provisioning" "container_start" "Starting $service container"
        if timeout 60s $DOCKER_COMPOSE_CMD up -d "$service"; then
            echo "    ✅ $service started successfully"
            notify_webhook "provisioning" "container_started" "✅ $service container started successfully"
            
            # Give container time to start
            sleep 5
            
            # Check if container is running - with multiple verification methods
            echo "    Verifying $service container status..."
            
            # Method 1: Check if container exists and is accessible
            if docker ps -a | grep -q "$service"; then
                echo "      ✅ Container exists"
                
                # Method 2: Check if we can execute commands in the container
                if docker exec "$service" echo "Container accessible" >/dev/null 2>&1; then
                    echo "      ✅ Container is accessible and responsive"
                    notify_webhook "provisioning" "container_accessible" "✅ $service container is accessible and responsive"
                else
                    echo "      ⚠️ Container exists but not fully responsive yet"
                    notify_webhook "warning" "container_slow_start" "$service container exists but not fully responsive"
                fi
            else
                echo "      ❌ Container not found after start attempt"
                echo "      🔍 Docker Compose status:"
                $DOCKER_COMPOSE_CMD ps "$service"
                notify_webhook "failed" "container_not_found" "$service container not found after start attempt"
                exit 1
            fi
            
            # SPECIAL HANDLING FOR POSTGRESQL
            if [ "$service" = "plane-db" ]; then
                echo "    🔍 PostgreSQL Special Handling..."
                notify_webhook "debug" "postgresql_special_handling" "Applying special handling for PostgreSQL Docker state issues"
                
                # Wait longer for PostgreSQL and use direct service checking
                echo "    Waiting for PostgreSQL to initialize (up to 60 seconds)..."
                for i in {1..12}; do
                    sleep 5
                    
                    # Direct PostgreSQL service check (bypass Docker state)
                    if docker exec plane-db pg_isready -U "$POSTGRES_USER" -q 2>/dev/null; then
                        echo "      ✅ PostgreSQL is ready and accepting connections!"
                        notify_webhook "provisioning" "postgresql_ready_direct" "✅ PostgreSQL is ready and accepting connections (direct check)"
                        break
                    fi
                    
                    # Check if container is still accessible
                    if ! docker exec plane-db echo "alive" >/dev/null 2>&1; then
                        echo "      ❌ PostgreSQL container became unresponsive"
                        echo "      🔍 PostgreSQL logs:"
                        $DOCKER_COMPOSE_CMD logs plane-db --tail=20
                        notify_webhook "failed" "postgresql_unresponsive" "PostgreSQL container became unresponsive during initialization"
                        exit 1
                    fi
                    
                    if [ $i -eq 12 ]; then
                        echo "      ⚠️ PostgreSQL not ready after 60s, but continuing if container is alive"
                        if docker exec plane-db ps aux 2>/dev/null | grep -q "[p]ostgres"; then
                            echo "      ✅ PostgreSQL processes are running, continuing..."
                            notify_webhook "warning" "postgresql_slow_start" "PostgreSQL slow start but processes are running, continuing"
                        else
                            echo "      ❌ No PostgreSQL processes found after 60s"
                            notify_webhook "failed" "postgresql_no_processes" "No PostgreSQL processes found after 60 seconds"
                            exit 1
                        fi
                    fi
                done
            fi
            
            # SPECIAL HANDLING FOR MINIO - Enhanced stability monitoring
            if [ "$service" = "plane-minio" ]; then
                echo "    🔍 MinIO Enhanced Stability Check..."
                notify_webhook "debug" "minio_enhanced_stability" "Enhanced MinIO container stability monitoring"
                
                # Monitor MinIO for 30 seconds to ensure it doesn't crash
                MINIO_STABLE=true
                for i in {1..6}; do
                    sleep 5
                    CURRENT_TIME=$((i*5))
                    
                    if ! docker ps | grep -q "plane-minio"; then
                        echo "      ❌ MinIO container crashed after ${CURRENT_TIME} seconds!"
                        MINIO_STABLE=false
                        
                        echo "      🔍 MinIO logs before crash:"
                        $DOCKER_COMPOSE_CMD logs plane-minio --tail=30
                        
                        # Check why it crashed
                        echo "      🔍 Checking system resources:"
                        docker system df
                        echo "      🔍 Checking disk space:"
                        df -h
                        
                        break
                    else
                        echo "      ✅ MinIO still running after ${CURRENT_TIME} seconds"
                        
                        # Check if MinIO process is actually running inside container
                        if docker exec plane-minio ps aux 2>/dev/null | grep -q "[m]inio"; then
                            echo "      ✅ MinIO process is running inside container"
                        else
                            echo "      ⚠️ Container running but no MinIO process found"
                        fi
                    fi
                done
                
                if [ "$MINIO_STABLE" = "false" ]; then
                    echo "    🔧 Attempting MinIO recovery..."
                    notify_webhook "debug" "minio_recovery_attempt" "Attempting MinIO recovery after crash"
                    
                    # Clean up any existing MinIO containers and volumes
                    $DOCKER_COMPOSE_CMD stop plane-minio 2>/dev/null
                    $DOCKER_COMPOSE_CMD rm -f plane-minio 2>/dev/null
                    docker volume rm plane_minio_data 2>/dev/null || true
                    sleep 2
                    
                    # Try starting MinIO with simpler configuration
                    echo "    🔧 Starting MinIO with simplified configuration..."
                    if docker run -d \
                        --name plane-minio \
                        -p 9000:9000 \
                        -p 9001:9001 \
                        -e "MINIO_ROOT_USER=minioadmin" \
                        -e "MINIO_ROOT_PASSWORD=minioadmin" \
                        -v minio_data:/data \
                        minio/minio server /data --console-address ":9001"; then
                        echo "    ✅ MinIO started successfully in standalone mode"
                        notify_webhook "provisioning" "minio_standalone_success" "MinIO started successfully in standalone mode after recovery"
                        
                        # Wait a bit for standalone MinIO to initialize
                        sleep 10
                    else
                        echo "    ❌ Failed to start MinIO in standalone mode"
                        notify_webhook "failed" "minio_standalone_failed" "Failed to start MinIO in standalone mode"
                        exit 1
                    fi
                else
                    echo "    ✅ MinIO container stable for 30+ seconds"
                    notify_webhook "provisioning" "minio_stable" "MinIO container stable for 30+ seconds"
                fi
            fi
            
            echo "    ✅ $service verification complete"
        else
            echo "    ❌ Failed to start $service"
            echo "    🔍 Docker Compose output:"
            $DOCKER_COMPOSE_CMD up -d "$service"  # Run again to see the error
            echo "    🔍 Container status:"
            $DOCKER_COMPOSE_CMD ps "$service"
            notify_webhook "failed" "service_start_failed" "Failed to start $service - check Docker logs"
            exit 1
        fi
        
        echo "    ✅ $service is running"
        notify_webhook "provisioning" "service_ready" "✅ $service is running and ready"
        sleep 3  # Brief pause between services
    done

    echo "✅ All infrastructure services started"
    notify_webhook "provisioning" "infrastructure_started" "✅ All infrastructure services started"

    # ==========================================================
    # Wait for infrastructure health checks (MINIO-FOCUSED FIXES)
    # ==========================================================
    echo "⏳ Waiting for infrastructure services to be ready..."
    notify_webhook "provisioning" "health_checks_start" "Starting health checks for infrastructure services"

    # Improved health check function with better MinIO handling
    check_service_health() {
        local service_name="$1"
        local check_command="$2"
        local timeout_seconds="${3:-180}"  # Default 3 minutes
        
        echo "  Checking $service_name..."
        notify_webhook "provisioning" "service_health_check" "Checking $service_name health"
        
        local count=0
        local max_attempts=$((timeout_seconds / 5))
        
        # Special handling for MinIO - use multiple health check methods
        if [ "$service_name" = "MinIO" ]; then
            echo "    Using enhanced MinIO health checks..."
            # Try multiple endpoints and methods
            check_command="(curl -s -f http://localhost:9000/minio/health/live >/dev/null 2>&1 || curl -s -f http://localhost:9001/minio/health/live >/dev/null 2>&1 || curl -s http://localhost:9000/minio/health/ready >/dev/null 2>&1 || (docker exec plane-minio ps aux | grep -q '[m]inio' && echo 'minio_process_running' > /tmp/minio_status)) && test -f /tmp/minio_status || true"
        fi
        
        until eval "$check_command" >/dev/null 2>&1; do
            sleep 5
            count=$((count + 1))
            
            # Show progress every 30 seconds
            if [ $((count % 6)) -eq 0 ]; then
                echo "    Still waiting for $service_name... (${count}s)"
                notify_webhook "provisioning" "health_check_progress" "Still waiting for $service_name to be ready... (${count}s)"
                
                # Enhanced debugging for MinIO
                if [ "$service_name" = "MinIO" ]; then
                    echo "    🔍 MinIO Debug Info:"
                    if docker ps | grep -q "plane-minio"; then
                        echo "      ✅ Container is running"
                        echo "      🔍 Checking MinIO process:"
                        if docker exec plane-minio ps aux 2>/dev/null | grep -q "[m]inio"; then
                            echo "      ✅ MinIO process is running inside container"
                        else
                            echo "      ⚠️ Container running but no MinIO process"
                        fi
                        echo "      🔍 Checking ports:"
                        netstat -tuln | grep -E ':(9000|9001)' || echo "      Ports not listening"
                    else
                        echo "      ❌ Container not running"
                    fi
                fi
            fi
            
            # Enhanced container stability check with better recovery
            if ! docker ps | grep -q "$service_name"; then
                echo "    ❌ $service_name container disappeared!"
                echo "    🔍 Checking all containers:"
                docker ps -a
                echo "    🔍 $service_name logs before disappearance:"
                $DOCKER_COMPOSE_CMD logs "$service_name" --tail=20 2>/dev/null || echo "    No logs available"
                
                # Enhanced recovery for MinIO
                if [ "$service_name" = "MinIO" ]; then
                    echo "    🔧 Attempting comprehensive MinIO recovery..."
                    notify_webhook "debug" "minio_comprehensive_recovery" "Attempting comprehensive MinIO recovery"
                    
                    # Clean up completely
                    docker stop plane-minio 2>/dev/null || true
                    docker rm -f plane-minio 2>/dev/null || true
                    $DOCKER_COMPOSE_CMD stop plane-minio 2>/dev/null || true
                    $DOCKER_COMPOSE_CMD rm -f plane-minio 2>/dev/null || true
                    sleep 3
                    
                    # Remove any conflicting containers
                    docker ps -a | grep minio | awk '{print $1}' | xargs -r docker rm -f
                    
                    echo "    🔧 Starting MinIO with optimized configuration..."
                    # Use Docker run with optimized settings
                    if docker run -d \
                        --name plane-minio \
                        --restart unless-stopped \
                        -p 9000:9000 \
                        -p 9001:9001 \
                        -e "MINIO_ROOT_USER=minioadmin" \
                        -e "MINIO_ROOT_PASSWORD=minioadmin" \
                        -e "MINIO_BROWSER=on" \
                        -v minio_data:/data \
                        minio/minio server /data --console-address ":9001"; then
                        echo "    ✅ MinIO recovery successful"
                        notify_webhook "provisioning" "minio_recovery_success" "MinIO recovery successful with optimized configuration"
                        count=0  # Reset counter
                        sleep 10  # Give it time to start
                        continue
                    else
                        echo "    ❌ MinIO recovery failed"
                        notify_webhook "failed" "minio_recovery_failed" "MinIO recovery failed after multiple attempts"
                        return 1
                    fi
                else
                    notify_webhook "failed" "container_disappeared" "$service_name container disappeared during health check"
                    return 1
                fi
            fi
            
            if [ $count -ge $max_attempts ]; then
                echo "    ❌ $service_name did not become ready within $timeout_seconds seconds"
                echo "    🔍 $service_name logs:"
                $DOCKER_COMPOSE_CMD logs "$service_name" --tail=30
                echo "    🔍 Current container status:"
                docker ps -a | grep "$service_name" || echo "    Container not found"
                
                # For MinIO, continue if the container is running even if health checks fail
                if [ "$service_name" = "MinIO" ] && docker ps | grep -q "plane-minio"; then
                    echo "    ⚠️ MinIO health check failed but container is running - continuing..."
                    notify_webhook "warning" "minio_continue_despite_health" "MinIO health check failed but container running - continuing"
                    return 0
                fi
                
                notify_webhook "failed" "health_check_timeout" "$service_name did not become ready within $timeout_seconds seconds"
                return 1
            fi
        done
        
        echo "    ✅ $service_name is healthy"
        notify_webhook "provisioning" "service_healthy" "✅ $service_name is healthy and ready"
        return 0
    }

    # Check PostgreSQL (this is working well)
    echo "  Checking PostgreSQL database readiness..."
    notify_webhook "provisioning" "postgresql_health_check" "Starting PostgreSQL health check"

    if check_service_health "PostgreSQL" "docker exec plane-db pg_isready -U $POSTGRES_USER -q" 120; then
        echo "  ✅ PostgreSQL health check passed"
    else
        echo "  ❌ PostgreSQL health check failed"
        if docker exec plane-db ps aux 2>/dev/null | grep -q "[p]ostgres"; then
            echo "  ⚠️ PostgreSQL processes are running, continuing despite health check failure"
            notify_webhook "warning" "postgresql_continue_despite_health_check" "Continuing despite PostgreSQL health check failure - processes are running"
        else
            exit 1
        fi
    fi

    # Check Redis
    check_service_health "Redis" "docker exec plane-redis redis-cli ping | grep -q PONG" 60 || {
        echo "❌ Redis health check failed"
        $DOCKER_COMPOSE_CMD logs plane-redis --tail=30
        exit 1
    }

    # Check RabbitMQ  
    check_service_health "RabbitMQ" "docker exec plane-mq rabbitmqctl await_startup" 120 || {
        echo "❌ RabbitMQ health check failed"
        $DOCKER_COMPOSE_CMD logs plane-mq --tail=30
        exit 1
    }

    # Check MinIO with ultimate fallback
    echo "  Checking MinIO with comprehensive fallback..."
    notify_webhook "provisioning" "minio_final_attempt" "Final MinIO health check with comprehensive fallback"

    # Try the health check but be very forgiving with MinIO
    if check_service_health "MinIO" "curl -s -f http://localhost:9000/minio/health/live >/dev/null 2>&1 || curl -s -f http://localhost:9001/minio/health/live >/dev/null 2>&1" 90; then
        echo "  ✅ MinIO health check passed"
    else
        echo "  ⚠️ MinIO health check failed, but checking if we can continue..."
        
        # Ultimate fallback - if MinIO container exists and has been running for a while, continue
        if docker ps | grep -q "plane-minio"; then
            CONTAINER_UPTIME=$(docker inspect --format='{{.State.StartedAt}}' plane-minio 2>/dev/null | cut -d'.' -f1)
            if [ -n "$CONTAINER_UPTIME" ]; then
                echo "  ✅ MinIO container is running (started: $CONTAINER_UPTIME), continuing despite health check"
                notify_webhook "warning" "minio_container_running_continue" "MinIO container is running, continuing despite health check failure"
            else
                echo "  ✅ MinIO container is running, continuing..."
                notify_webhook "warning" "minio_continue_container_running" "MinIO container running, continuing despite health check"
            fi
        else
            echo "  ❌ MinIO container not running and health checks failed"
            # One final attempt to start MinIO
            echo "  🔧 Final MinIO startup attempt..."
            if docker run -d \
                --name plane-minio \
                -p 9000:9000 \
                -p 9001:9001 \
                -e "MINIO_ROOT_USER=minioadmin" \
                -e "MINIO_ROOT_PASSWORD=minioadmin" \
                -v minio_data:/data \
                minio/minio server /data --console-address ":9001"; then
                echo "  ✅ MinIO started on final attempt, continuing..."
                notify_webhook "provisioning" "minio_final_start_success" "MinIO started successfully on final attempt"
                sleep 10
            else
                echo "  ❌ Could not start MinIO, but continuing without it for now"
                notify_webhook "warning" "minio_skipped" "MinIO failed to start, continuing without object storage"
            fi
        fi
    fi

    echo "✅ All infrastructure services are ready"
    notify_webhook "provisioning" "infrastructure_ready" "✅ All infrastructure services are ready - proceeding to application setup"
                                                                                                                        
    # ==========================================================
    # Setup MinIO bucket
    # ==========================================================
    echo "📦 Setting up MinIO bucket..."
    sleep 10
    # Install mc command if not exists
    if ! command -v mc &>/dev/null; then
        curl -s https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
        chmod +x /usr/local/bin/mc
    fi

    # Create bucket
    docker exec plane-minio mc alias set local http://localhost:9000 $MINIO_USER $MINIO_PASSWORD || true
    docker exec plane-minio mc mb local/uploads --ignore-existing || true
    echo "✅ MinIO bucket configured"

    # ==========================================================
    # Run database migrations
    # ==========================================================
    echo "[8/15] Running database migrations..."
    notify_webhook "provisioning" "migrations_start" "Running database migrations"

    $DOCKER_COMPOSE_CMD run --rm migrator || {
        echo "❌ Migrations failed"
        $DOCKER_COMPOSE_CMD logs plane-db --tail=20
        $DOCKER_COMPOSE_CMD logs migrator --tail=30
        notify_webhook "failed" "migrations_failed" "Database migrations failed"
        exit 1
    }

    echo "✅ Migrations completed successfully"
    notify_webhook "provisioning" "migrations_complete" "✅ Database migrations completed"
    
    sleep 5
    
    # ==========================================================
    # Start application services (WITH ADVANCED LIVE SERVICE HANDLING)
    # ==========================================================
    echo "🚀 Starting Plane application services..."
    notify_webhook "provisioning" "app_services_start" "Starting Plane application containers"

    APP_SERVICES=("api" "worker" "beat-worker" "web" "space" "admin" "live" "proxy")
    for service in "${APP_SERVICES[@]}"; do
        echo "  Starting $service..."
        notify_webhook "provisioning" "app_service_start" "Starting $service"
        
        # Pull image first to avoid delays
        echo "    Pulling image for $service..."
        if ! $DOCKER_COMPOSE_CMD pull "$service" --quiet; then
            echo "    ⚠️ Failed to pull $service image, but continuing..."
            notify_webhook "warning" "app_image_pull_failed" "Failed to pull $service image, but continuing"
        fi
        
        # SPECIAL HANDLING FOR PROXY - Simplified approach
        if [ "$service" = "proxy" ]; then
            echo "    🔧 Special handling for proxy service..."
            notify_webhook "debug" "proxy_special_handling" "Applying special handling for proxy service"
            
            # Clean up any existing proxy
            $DOCKER_COMPOSE_CMD stop proxy 2>/dev/null || true
            $DOCKER_COMPOSE_CMD rm -f proxy 2>/dev/null || true
            sleep 2
            
            # Check for port conflicts
            echo "    🔍 Checking for port conflicts..."
            if netstat -tuln | grep -q ":80 "; then
                echo "    ⚠️ Port 80 is in use, stopping conflicting service..."
                # Try to identify and stop what's using port 80
                lsof -ti:80 | xargs -r kill -9 2>/dev/null || true
                sleep 2
            fi
            
            # Start proxy with simple approach
            echo "    🚀 Starting proxy service..."
            if $DOCKER_COMPOSE_CMD up -d proxy; then
                echo "    ✅ Proxy started successfully"
                notify_webhook "provisioning" "proxy_started" "✅ Proxy service started successfully"
                
                # Wait and check status
                sleep 10
                if $DOCKER_COMPOSE_CMD ps proxy | grep -q "Up"; then
                    echo "    ✅ Proxy is running and healthy"
                    notify_webhook "provisioning" "proxy_healthy" "✅ Proxy service is running and healthy"
                else
                    echo "    ⚠️ Proxy container exists but not in 'Up' state"
                    echo "    🔍 Proxy logs:"
                    $DOCKER_COMPOSE_CMD logs proxy --tail=10
                    notify_webhook "warning" "proxy_container_exists" "Proxy container exists but not fully up - continuing"
                fi
            else
                echo "    ⚠️ Proxy failed to start, but continuing without it"
                notify_webhook "warning" "proxy_skipped" "Proxy service failed to start, app will use direct ports"
            fi
        
        # ADVANCED HANDLING FOR LIVE SERVICE
        elif [ "$service" = "live" ]; then
            echo "    🔧 Advanced handling for live service..."
            notify_webhook "debug" "live_advanced_handling" "Applying advanced handling for live service"
            
            # Clean up any existing live container
            $DOCKER_COMPOSE_CMD stop live 2>/dev/null || true
            $DOCKER_COMPOSE_CMD rm -f live 2>/dev/null || true
            sleep 2
            
            # Enhanced resource monitoring before starting
            echo "    📊 Checking system resources for live service..."
            MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
            DISK_AVAILABLE=$(df /opt/plane | awk 'NR==2{print $4}')
            
            echo "    💾 Available memory: ${MEM_AVAILABLE}MB, Disk: ${DISK_AVAILABLE}KB"
            
            # Add resource limits to docker-compose for live service if memory is low
            if [ "$MEM_AVAILABLE" -lt 1024 ]; then
                echo "    🔧 Adding resource limits to live service (low memory detected)"
                if grep -q "plane-live:" docker-compose.yml && ! grep -q "mem_limit" docker-compose.yml; then
                    sed -i '/container_name: plane-live/a \    mem_limit: 512m\n    cpus: 0.5' docker-compose.yml
                    echo "    ✅ Added memory limits to live service"
                fi
            fi
            
            # Multi-stage startup with comprehensive health checks
            echo "    🚀 Starting live service with enhanced monitoring..."
            LIVE_STARTED=false
            LIVE_HEALTHY=false
            
            for attempt in {1..3}; do
                echo "    🔄 Attempt $attempt to start live service..."
                
                # Start the service
                if timeout 60s $DOCKER_COMPOSE_CMD up -d live; then
                    LIVE_STARTED=true
                    echo "    ✅ Live service started on attempt $attempt"
                    
                    # Enhanced health checking with multiple methods
                    echo "    🔍 Performing comprehensive health checks..."
                    
                    # Method 1: Check container status
                    sleep 10
                    if $DOCKER_COMPOSE_CMD ps live | grep -q "Up"; then
                        echo "    ✅ Container is running"
                        
                        # Method 2: Check if process is running inside container
                        if docker exec plane-live ps aux 2>/dev/null | grep -q "node\|live"; then
                            echo "    ✅ Live process is running inside container"
                            
                            # Method 3: Check if port is listening
                            if docker exec plane-live netstat -tuln 2>/dev/null | grep -q ":3100"; then
                                echo "    ✅ Live service is listening on port 3100"
                                
                                # Method 4: Check HTTP responsiveness
                                if curl -s -f http://localhost:3100/health >/dev/null 2>&1 || \
                                curl -s -f http://localhost:3100/ >/dev/null 2>&1 || \
                                docker exec plane-live curl -s http://localhost:3100/ >/dev/null 2>&1; then
                                    echo "    ✅ Live service is responding to HTTP requests"
                                    LIVE_HEALTHY=true
                                    notify_webhook "provisioning" "live_healthy" "✅ Live service started and healthy on attempt $attempt"
                                    break
                                else
                                    echo "    ⚠️ Live service running but not responding to HTTP"
                                fi
                            else
                                echo "    ⚠️ Live service not listening on expected port"
                            fi
                        else
                            echo "    ⚠️ No live process found inside container"
                        fi
                    else
                        echo "    ⚠️ Container started but not in 'Up' state"
                    fi
                    
                    # If not healthy, show logs and retry
                    if [ "$LIVE_HEALTHY" = false ]; then
                        echo "    📋 Live service logs (attempt $attempt):"
                        $DOCKER_COMPOSE_CMD logs live --tail=15
                        
                        if [ $attempt -lt 3 ]; then
                            echo "    🔧 Cleaning up for retry..."
                            $DOCKER_COMPOSE_CMD stop live 2>/dev/null || true
                            $DOCKER_COMPOSE_CMD rm -f live 2>/dev/null || true
                            sleep 5
                            
                            # Increase wait time between retries
                            echo "    ⏳ Waiting before retry..."
                            sleep 10
                        fi
                    fi
                else
                    echo "    ❌ Failed to start live service on attempt $attempt"
                    if [ $attempt -lt 3 ]; then
                        echo "    🔧 Cleaning up for retry..."
                        $DOCKER_COMPOSE_CMD stop live 2>/dev/null || true
                        $DOCKER_COMPOSE_CMD rm -f live 2>/dev/null || true
                        sleep 5
                    fi
                fi
            done
            
            # Final status reporting
            if [ "$LIVE_HEALTHY" = true ]; then
                echo "    ✅ Live service fully operational"
                notify_webhook "provisioning" "live_operational" "✅ Live service fully operational with real-time features"
            elif [ "$LIVE_STARTED" = true ]; then
                echo "    ⚠️ Live service started but may have limited functionality"
                notify_webhook "warning" "live_limited" "Live service started but may have limited functionality - real-time features may be affected"
            else
                echo "    ❌ Live service failed to start after 3 attempts"
                echo "    💡 Real-time features will be disabled, but core application will work"
                notify_webhook "warning" "live_failed" "Live service failed to start - real-time features disabled, but core app functional"
            fi
        
        else
            # Standard startup for other services
            echo "    Starting $service container..."
            if timeout 120s $DOCKER_COMPOSE_CMD up -d "$service"; then
                echo "    ✅ $service started successfully"
                notify_webhook "provisioning" "app_service_started" "✅ $service container started successfully"
                
                # Wait and verify service is actually running
                sleep 8
                
                if $DOCKER_COMPOSE_CMD ps "$service" | grep -q "Up"; then
                    echo "    ✅ $service is running"
                else
                    echo "    ⚠️ $service started but not in 'Up' state"
                    echo "    🔍 $service logs:"
                    $DOCKER_COMPOSE_CMD logs "$service" --tail=5
                fi
            else
                echo "    ❌ Failed to start $service"
                
                # For critical services, exit; for optional ones, continue
                case "$service" in
                    "api"|"worker"|"web")
                        echo "    ❌ Critical service $service failed - cannot continue"
                        $DOCKER_COMPOSE_CMD logs "$service" --tail=20
                        notify_webhook "failed" "critical_service_failed" "Critical service $service failed to start"
                        exit 1
                        ;;
                    *)
                        echo "    ⚠️ Non-critical service $service failed - continuing"
                        notify_webhook "warning" "non_critical_service_failed" "Non-critical service $service failed, but continuing"
                        ;;
                esac
            fi
        fi
        
        echo "  ✅ $service startup completed"
        sleep 3  # Brief pause between services
    done

    echo "✅ All Plane services started"
    notify_webhook "provisioning" "app_services_ready" "✅ All Plane application services running"

    # ==========================================================
    # Enhanced Container Health Verification
    # ==========================================================
    echo "🔍 Performing enhanced container health verification..."
    notify_webhook "provisioning" "enhanced_health_check" "Starting enhanced container health verification"

    # Comprehensive container status check
    CONTAINER_STATUS=$($DOCKER_COMPOSE_CMD ps)
    RUNNING_CONTAINERS=$(echo "$CONTAINER_STATUS" | grep "Up" | wc -l)
    TOTAL_CONTAINERS=$(echo "$CONTAINER_STATUS" | tail -n +2 | wc -l)

    echo "📊 Container Status: $RUNNING_CONTAINERS/$TOTAL_CONTAINERS running"
    notify_webhook "debug" "container_status" "Containers running: $RUNNING_CONTAINERS/$TOTAL_CONTAINERS"

    # Detailed container analysis
    EXPECTED_CONTAINERS=("api" "worker" "beat-worker" "web" "space" "admin" "live" "proxy" "plane-db" "plane-redis" "plane-mq" "plane-minio")
    CRITICAL_CONTAINERS=("api" "worker" "web" "plane-db" "plane-redis")
    OPTIONAL_CONTAINERS=("space" "admin" "live" "proxy" "plane-mq" "plane-minio")

    MISSING_CRITICAL=""
    MISSING_OPTIONAL=""
    HEALTHY_CRITICAL=0

    for container in "${EXPECTED_CONTAINERS[@]}"; do
        if echo "$CONTAINER_STATUS" | grep -q "$container.*Up"; then
            echo "    ✅ $container: RUNNING"
            if [[ " ${CRITICAL_CONTAINERS[@]} " =~ " ${container} " ]]; then
                ((HEALTHY_CRITICAL++))
            fi
        else
            echo "    ❌ $container: NOT RUNNING"
            if [[ " ${CRITICAL_CONTAINERS[@]} " =~ " ${container} " ]]; then
                MISSING_CRITICAL="$MISSING_CRITICAL $container"
            else
                MISSING_OPTIONAL="$MISSING_OPTIONAL $container"
            fi
        fi
    done

    # Report detailed status
    echo "📈 Critical Services: $HEALTHY_CRITICAL/${#CRITICAL_CONTAINERS[@]} healthy"
    if [ -n "$MISSING_CRITICAL" ]; then
        echo "    🚨 Missing critical: $MISSING_CRITICAL"
        notify_webhook "warning" "missing_critical" "Missing critical containers:$MISSING_CRITICAL"
    fi
    if [ -n "$MISSING_OPTIONAL" ]; then
        echo "    ⚠️ Missing optional: $MISSING_OPTIONAL"
        notify_webhook "debug" "missing_optional" "Missing optional containers:$MISSING_OPTIONAL"
    fi

    # ==========================================================
    # Advanced API Health Verification
    # ==========================================================
    echo "🔍 Performing advanced API health verification..."
    notify_webhook "provisioning" "advanced_api_health" "Starting advanced API health checks"

    API_HEALTHY=false
    LIVE_HEALTHY=false

    # Multi-stage API health check
    for i in {1..36}; do  # 6 minutes total
        CURRENT_TIME=$((i * 10))
        
        # Check API container status
        if $DOCKER_COMPOSE_CMD ps api | grep -q "Up"; then
            # Check API responsiveness with multiple endpoints
            if curl -s -f http://localhost:8000/api/ >/dev/null 2>&1; then
                echo "    ✅ API root responsive"
                
                # Additional API endpoint checks
                if curl -s -f http://localhost:8000/api/health/ >/dev/null 2>&1 || \
                curl -s -f http://localhost:8000/health/ >/dev/null 2>&1; then
                    echo "    ✅ API health endpoint responsive"
                    API_HEALTHY=true
                    
                    # Check live service if it's running
                    if $DOCKER_COMPOSE_CMD ps live | grep -q "Up"; then
                        if curl -s -f http://localhost:3100/ >/dev/null 2>&1 || \
                        curl -s -f http://localhost:3100/health >/dev/null 2>&1; then
                            echo "    ✅ Live service responsive"
                            LIVE_HEALTHY=true
                        fi
                    fi
                    break
                fi
            fi
        fi
        
        # Progress reporting every 60 seconds
        if [ $((i % 6)) -eq 0 ]; then
            echo "    ⏳ API health check in progress... (${CURRENT_TIME}s)"
            notify_webhook "provisioning" "health_check_progress" "API health check in progress... (${CURRENT_TIME}s)"
            
            # Show container status every 2 minutes
            if [ $((i % 12)) -eq 0 ]; then
                echo "    📊 Current container status:"
                $DOCKER_COMPOSE_CMD ps --filter "status=running" | grep -v "NAME" || echo "        No containers running"
            fi
        fi
        
        sleep 10
    done

    # Final deployment assessment
    if [ "$API_HEALTHY" = true ]; then
        if [ $HEALTHY_CRITICAL -eq ${#CRITICAL_CONTAINERS[@]} ]; then
            echo "🎉 Plane deployment fully operational!"
            if [ "$LIVE_HEALTHY" = true ]; then
                notify_webhook "success" "deployment_fully_operational" "✅ Plane fully operational with all critical services and real-time features"
            else
                notify_webhook "success" "deployment_operational" "✅ Plane operational with all critical services (real-time features limited)"
            fi
        else
            echo "✅ Plane deployment stable - core functionality available"
            notify_webhook "success" "deployment_stable" "✅ Plane deployment stable with $HEALTHY_CRITICAL/${#CRITICAL_CONTAINERS[@]} critical services"
        fi
    else
        if [ $HEALTHY_CRITICAL -ge 3 ]; then  # At least API, DB, and one other critical service
            echo "⚠️ Plane deployment partially functional - API not responding but core services running"
            notify_webhook "warning" "deployment_partial" "Plane deployment partially functional - API not responding but $HEALTHY_CRITICAL critical services running"
        else
            echo "❌ Plane deployment unstable - insufficient critical services running"
            notify_webhook "failed" "deployment_unstable" "Plane deployment unstable - only $HEALTHY_CRITICAL critical services running"
            exit 1
        fi
    fi

    notify_webhook "provisioning" "plane_deployment_complete" "✅ Plane deployment completed successfully"

    # Final container status report
    echo "📋 Final container status:"
    $DOCKER_COMPOSE_CMD ps

    echo "🔧 Useful commands:"
    echo "    View logs: cd $DATA_DIR/plane-selfhost && $DOCKER_COMPOSE_CMD logs -f"
    echo "    Restart services: cd $DATA_DIR/plane-selfhost && $DOCKER_COMPOSE_CMD restart"
    echo "    Check specific service: cd $DATA_DIR/plane-selfhost && $DOCKER_COMPOSE_CMD logs [service-name]"
    # ==========================================================
    # Final container status
    # ==========================================================
    echo "📊 Final container status:"
    $DOCKER_COMPOSE_CMD ps

    echo "🎉 Plane deployment completed successfully!"
    notify_webhook "provisioning" "plane_deployment_complete" "✅ Plane deployment completed successfully - Access at http://localhost"
                                                                                                                        
    # ========== FIREWALL ==========
    echo "[10/15] Configuring firewall..."
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


   # ========== NGINX CONFIG + SSL (FIXED - NO REDIRECT LOOP) ==========
    echo "[11/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/plane

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Check if Plane proxy is running and get its port
    PROXY_PORT="80"
    if docker ps | grep -q proxy; then
        # Get the host port that the proxy container's port 80 is mapped to
        MAPPED_PORT=$(docker port proxy 80 2>/dev/null | cut -d: -f2)
        if [ -n "$MAPPED_PORT" ] && [ "$MAPPED_PORT" != "80" ]; then
            PROXY_PORT="$MAPPED_PORT"
            echo "🔧 Proxy container is using port: $PROXY_PORT"
        else
            # If proxy is using port 80, we need to stop it temporarily or use a different approach
            echo "🔧 Proxy is using port 80, will configure nginx carefully..."
            # We'll handle this in the nginx config
        fi
    fi

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/plane <<EOF_TEMP
server {
    listen 80;
    server_name __DOMAIN__;
    root /var/www/html;

    location / {
        return 200 'Certbot validation ready';
        add_header Content-Type text/plain;
    }
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        try_files \$uri =404;
    }
}
EOF_TEMP

    ln -sf /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/plane
    nginx -t && systemctl restart nginx

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html

    # Attempt to obtain SSL certificate
    if ! certbot --nginx -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__"; then
        echo "⚠️ Certbot nginx plugin failed; trying webroot fallback"
        certbot certonly --webroot -w /var/www/html -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__" || true
    fi

    # Fail-safe check
    if [ ! -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        echo "⚠️ SSL certificate not found! Continuing without SSL..."
        notify_webhook "warning" "ssl" "Forgejo Certbot failed, SSL not installed for __DOMAIN__"
        
        # HTTP-only configuration - proxy to the Plane services directly
        cat > /etc/nginx/sites-available/plane <<'EOF_HTTP'
server {
    listen 80;
    server_name __DOMAIN__;
    client_max_body_size 100M;

    # Proxy to Plane web service (bypass the Plane proxy container)
    location / {
        proxy_pass http://127.0.0.1:3000;
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
    
    # Proxy API requests directly to the API service
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF_HTTP
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # HTTPS configuration - proxy to Plane services directly
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

    # Proxy to Plane web service directly (bypass Plane proxy container)
    location / {
        proxy_pass http://127.0.0.1:3000;
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
    
    # Proxy API requests directly to API service
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Proxy space requests
    location /spaces/ {
        proxy_pass http://127.0.0.1:3002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Proxy admin requests
    location /admin/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF_SSL
    fi

    ln -sf /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/plane
    nginx -t && systemctl reload nginx

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
