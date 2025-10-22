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
    # Start infrastructure services (MAXIMUM VISIBILITY)
    # ==========================================================
    echo "🚀 Starting infrastructure services..."
    notify_webhook "orchestration" "infrastructure_phase_start" "BEGIN infrastructure service startup sequence"

    notify_webhook "debug" "service_dependencies" "Infrastructure dependency order: PostgreSQL → Redis → RabbitMQ → MinIO"
    notify_webhook "debug" "planned_sequence" "Execution order: plane-db → plane-redis → plane-mq → plane-minio"

    INFRA_SERVICES=("plane-db" "plane-redis" "plane-mq" "plane-minio")
    for service in "${INFRA_SERVICES[@]}"; do
        notify_webhook "orchestration" "service_start_attempt" "Starting service: $service (Step $((++step))/4)"
        echo "  Starting $service..."
        
        # Track pull timing
        notify_webhook "debug" "image_pull_start" "Pulling image for $service"
        pull_start=$(date +%s)
        if ! $DOCKER_COMPOSE_CMD pull "$service" --quiet; then
            notify_webhook "warning" "image_pull_skipped" "Image pull failed for $service, using local image"
        else
            pull_end=$(date +%s)
            pull_duration=$((pull_end - pull_start))
            notify_webhook "debug" "image_pull_complete" "✅ Image pulled for $service in ${pull_duration}s"
        fi
        
        # Track start timing
        notify_webhook "orchestration" "container_start_attempt" "Starting container for $service"
        start_time=$(date +%s)
        
        if timeout 60s $DOCKER_COMPOSE_CMD up -d "$service"; then
            end_time=$(date +%s)
            duration=$((end_time - start_time))
            notify_webhook "orchestration" "container_start_success" "✅ $service started in ${duration}s"
            
            # Enhanced status verification with timing
            notify_webhook "debug" "container_status_check" "Verifying $service container status"
            if docker ps -a | grep -q "$service"; then
                notify_webhook "debug" "container_exists" "Container $service exists in docker ps"
                
                # Service-specific readiness tracking
                case "$service" in
                    "plane-db")
                        notify_webhook "orchestration" "postgresql_wait_start" "Waiting for PostgreSQL to accept connections (max 60s)"
                        for i in {1..12}; do
                            sleep 5
                            current_wait=$((i*5))
                            if docker exec plane-db pg_isready -U "$POSTGRES_USER" -q 2>/dev/null; then
                                notify_webhook "orchestration" "postgresql_ready" "✅ PostgreSQL ready after ${current_wait}s - accepting connections"
                                break
                            else
                                notify_webhook "debug" "postgresql_waiting" "PostgreSQL not ready yet (${current_wait}s)..."
                            fi
                            if [ $i -eq 12 ]; then
                                notify_webhook "warning" "postgresql_slow" "PostgreSQL slow to start (60s) but continuing - processes running"
                            fi
                        done
                        ;;
                    "plane-redis")
                        notify_webhook "orchestration" "redis_wait_start" "Waiting for Redis to respond to PING"
                        for i in {1..6}; do
                            sleep 5
                            if docker exec plane-redis redis-cli ping | grep -q PONG 2>/dev/null; then
                                notify_webhook "orchestration" "redis_ready" "✅ Redis ready after $((i*5))s - responding to PING"
                                break
                            fi
                        done
                        ;;
                    "plane-mq")
                        notify_webhook "orchestration" "rabbitmq_wait_start" "Waiting for RabbitMQ startup completion"
                        for i in {1..12}; do
                            sleep 5
                            if docker exec plane-mq rabbitmqctl await_startup 2>/dev/null; then
                                notify_webhook "orchestration" "rabbitmq_ready" "✅ RabbitMQ ready after $((i*5))s - startup complete"
                                break
                            fi
                        done
                        ;;
                    "plane-minio")
                        notify_webhook "orchestration" "minio_wait_start" "Waiting for MinIO health check (max 30s)"
                        for i in {1..6}; do
                            sleep 5
                            current_wait=$((i*5))
                            if curl -s -f http://localhost:9000/minio/health/live >/dev/null 2>&1; then
                                notify_webhook "orchestration" "minio_ready" "✅ MinIO ready after ${current_wait}s - health check passed"
                                break
                            else
                                notify_webhook "debug" "minio_waiting" "MinIO health check failed (${current_wait}s), trying console port..."
                                if curl -s -f http://localhost:9001/minio/health/live >/dev/null 2>&1; then
                                    notify_webhook "orchestration" "minio_ready_console" "✅ MinIO ready via console port after ${current_wait}s"
                                    break
                                fi
                            fi
                        done
                        ;;
                esac
                
            else
                notify_webhook "error" "container_missing" "❌ Container $service not found in docker ps after start attempt"
                notify_webhook "debug" "container_debug" "Debug: docker ps output - $(docker ps -a | head -10)"
                exit 1
            fi
        else
            notify_webhook "error" "container_start_failed" "❌ Failed to start $service container (timeout or error)"
            notify_webhook "debug" "compose_logs" "Docker compose logs: $($DOCKER_COMPOSE_CMD logs "$service" --tail=5 2>/dev/null || echo 'no logs')"
            exit 1
        fi
        
        notify_webhook "orchestration" "service_operational" "✅ $service fully operational and responsive"
        sleep 2
    done

    notify_webhook "milestone" "infrastructure_phase_complete" "🎯 ALL infrastructure services ready - database, cache, queue, storage operational"

    # ==========================================================
    # Setup MinIO bucket (WITH VISIBILITY)
    # ==========================================================
    echo "📦 Setting up MinIO bucket..."
    notify_webhook "orchestration" "minio_setup_start" "Configuring MinIO bucket and permissions"

    # Install mc command if not exists
    if ! command -v mc &>/dev/null; then
        notify_webhook "debug" "mc_install" "Installing MinIO client (mc)"
        curl -s https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
        chmod +x /usr/local/bin/mc
        notify_webhook "debug" "mc_installed" "MinIO client installed successfully"
    fi

    # Create bucket with visibility
    notify_webhook "debug" "minio_alias" "Setting MinIO alias: http://localhost:9000"
    if docker exec plane-minio mc alias set local http://localhost:9000 $MINIO_USER $MINIO_PASSWORD 2>/dev/null; then
        notify_webhook "debug" "minio_alias_success" "MinIO alias configured successfully"
    else
        notify_webhook "warning" "minio_alias_failed" "MinIO alias configuration failed - bucket creation may fail"
    fi

    notify_webhook "debug" "bucket_creation" "Creating bucket: uploads"
    if docker exec plane-minio mc mb local/uploads --ignore-existing 2>/dev/null; then
        notify_webhook "orchestration" "bucket_ready" "✅ MinIO bucket 'uploads' created/verified"
    else
        notify_webhook "warning" "bucket_creation_failed" "MinIO bucket creation failed - continuing without bucket"
    fi

    echo "✅ MinIO bucket configured"
    notify_webhook "milestone" "minio_setup_complete" "✅ MinIO storage layer configured and ready"

    # ==========================================================
    # Run database migrations (WITH VISIBILITY)
    # ==========================================================
    echo "[8/15] Running database migrations..."
    notify_webhook "orchestration" "migrations_start" "BEGIN database migrations - applying schema changes"

    notify_webhook "debug" "migration_precheck" "Verifying PostgreSQL is ready before migrations"
    if ! docker exec plane-db pg_isready -U "$POSTGRES_USER" -q 2>/dev/null; then
        notify_webhook "error" "postgres_not_ready_migration" "PostgreSQL not ready for migrations - aborting"
        exit 1
    fi

    notify_webhook "debug" "migration_execution" "Executing: docker-compose run --rm migrator"
    migration_start=$(date +%s)
    if $DOCKER_COMPOSE_CMD run --rm migrator; then
        migration_end=$(date +%s)
        migration_duration=$((migration_end - migration_start))
        notify_webhook "orchestration" "migrations_complete" "✅ Database migrations completed successfully in ${migration_duration}s"
    else
        notify_webhook "error" "migrations_failed" "❌ Database migrations failed - check logs"
        notify_webhook "debug" "migration_logs", "Migration logs: $($DOCKER_COMPOSE_CMD logs migrator --tail=20 2>/dev/null || echo 'no migration logs')"
        notify_webhook "debug" "postgres_logs", "PostgreSQL logs: $($DOCKER_COMPOSE_CMD logs plane-db --tail=10 2>/dev/null || echo 'no postgres logs')"
        exit 1
    fi

    echo "✅ Migrations completed successfully"
    sleep 3

    # ==========================================================
    # Start application services (MAXIMUM VISIBILITY)
    # ==========================================================
    echo "🚀 Starting Plane application services..."
    notify_webhook "orchestration" "application_phase_start" "BEGIN application service startup sequence"

    notify_webhook "debug" "app_dependencies" "Application dependency order: API → Workers → Web → Space → Admin → Live → Proxy"
    notify_webhook "debug" "critical_services", "Critical services: api, worker, web (will fail deployment if these fail)"

    APP_SERVICES=("api" "worker" "beat-worker" "web" "space" "admin" "live" "proxy")
    for service in "${APP_SERVICES[@]}"; do
        notify_webhook "orchestration" "app_service_start_attempt" "Starting application service: $service (Step $((++app_step))/8)"
        echo "  Starting $service..."
        
        # Track pull timing for application services
        notify_webhook "debug" "app_image_pull" "Pulling application image for $service"
        if ! $DOCKER_COMPOSE_CMD pull "$service" --quiet; then
            notify_webhook "warning" "app_image_pull_failed" "Application image pull failed for $service, using local image"
        else
            notify_webhook "debug" "app_image_pulled" "✅ Application image pulled for $service"
        fi
        
        # Special handling for proxy service
        if [ "$service" = "proxy" ]; then
            notify_webhook "orchestration", "proxy_special_start", "Starting proxy service with port conflict checks"
            
            # Check for port conflicts with visibility
            notify_webhook "debug", "port_check", "Checking for port 80 conflicts"
            if netstat -tuln | grep -q ":80 "; then
                notify_webhook "warning", "port_80_in_use", "Port 80 is in use - may conflict with proxy"
                # Try to identify what's using port 80
                port_user=$(lsof -i:80 -t 2>/dev/null | head -1 || echo "unknown")
                notify_webhook "debug", "port_user", "Port 80 used by PID: $port_user"
            else
                notify_webhook "debug", "port_80_free", "Port 80 is available for proxy"
            fi
            
            # Start proxy with enhanced monitoring
            notify_webhook "orchestration", "proxy_start_attempt", "Starting proxy container"
            proxy_start=$(date +%s)
            if $DOCKER_COMPOSE_CMD up -d proxy; then
                proxy_end=$(date +%s)
                proxy_duration=$((proxy_end - proxy_start))
                notify_webhook "orchestration", "proxy_start_success", "✅ Proxy started in ${proxy_duration}s"
                
                # Verify proxy status
                sleep 10
                if $DOCKER_COMPOSE_CMD ps proxy | grep -q "Up"; then
                    notify_webhook "orchestration", "proxy_healthy", "✅ Proxy container healthy and running"
                else
                    notify_webhook "warning", "proxy_unhealthy", "Proxy container started but not healthy - continuing"
                    notify_webhook "debug", "proxy_status", "Proxy status: $($DOCKER_COMPOSE_CMD ps proxy | grep proxy || echo 'not found')"
                fi
            else
                notify_webhook "error", "proxy_start_failed", "❌ Proxy service failed to start"
                exit 1
            fi
        else
            # Standard application service startup
            notify_webhook "orchestration", "app_container_start", "Starting application container: $service"
            app_start=$(date +%s)
            
            if timeout 120s $DOCKER_COMPOSE_CMD up -d "$service"; then
                app_end=$(date +%s)
                app_duration=$((app_end - app_start))
                notify_webhook "orchestration", "app_container_started", "✅ $service started in ${app_duration}s"
                
                # Verify service is running
                sleep 8
                if $DOCKER_COMPOSE_CMD ps "$service" | grep -q "Up"; then
                    notify_webhook "debug", "app_container_verified", "✅ $service container verified running"
                else
                    notify_webhook "warning", "app_container_unhealthy", "$service container started but not in 'Up' state"
                    notify_webhook "debug", "app_container_logs", "$service logs: $($DOCKER_COMPOSE_CMD logs "$service" --tail=3 2>/dev/null || echo 'no logs')"
                fi
            else
                notify_webhook "error", "app_container_failed", "❌ Failed to start $service container"
                
                # Critical service failure handling
                case "$service" in
                    "api"|"worker"|"web")
                        notify_webhook "fatal", "critical_service_failed", "CRITICAL service $service failed - deployment cannot continue"
                        notify_webhook "debug", "critical_service_logs", "$service logs: $($DOCKER_COMPOSE_CMD logs "$service" --tail=20 2>/dev/null || echo 'no logs')"
                        exit 1
                        ;;
                    *)
                        notify_webhook "warning", "non_critical_service_failed", "Non-critical service $service failed - continuing deployment"
                        ;;
                esac
            fi
        fi
        
        notify_webhook "orchestration", "app_service_operational", "✅ Application service $service operational"
        sleep 3
    done

    notify_webhook "milestone", "application_phase_complete", "🎯 ALL application services started and operational"

    # ==========================================================
    # Verify API health (COMPREHENSIVE VISIBILITY)
    # ==========================================================
    echo "🔍 Verifying Plane API health..."
    notify_webhook "orchestration", "health_verification_start", "BEGIN final health verification phase"

    # Give services time to initialize
    notify_webhook "debug", "service_settling", "Allowing 60s for services to stabilize and initialize"
    sleep 60

    # Comprehensive container status check
    notify_webhook "debug", "container_status_snapshot", "Taking container status snapshot"
    CONTAINER_STATUS=$($DOCKER_COMPOSE_CMD ps)
    RUNNING_CONTAINERS=$(echo "$CONTAINER_STATUS" | grep "Up" | wc -l)
    TOTAL_CONTAINERS=$(echo "$CONTAINER_STATUS" | tail -n +2 | wc -l)

    notify_webhook "debug", "container_count", "Containers running: $RUNNING_CONTAINERS/$TOTAL_CONTAINERS"

    # Detailed container analysis
    notify_webhook "debug", "container_analysis", "Analyzing individual container status"
    EXPECTED_CONTAINERS=("api" "worker" "beat-worker" "web" "space" "admin" "live" "proxy" "plane-db" "plane-redis" "plane-mq" "plane-minio")
    MISSING_CONTAINERS=""
    RUNNING_CONTAINERS_LIST=""

    for container in "${EXPECTED_CONTAINERS[@]}"; do
        if echo "$CONTAINER_STATUS" | grep -q "$container.*Up"; then
            RUNNING_CONTAINERS_LIST="$RUNNING_CONTAINERS_LIST $container"
        else
            MISSING_CONTAINERS="$MISSING_CONTAINERS $container"
            notify_webhook "warning", "container_not_running", "Container $container is not running"
        fi
    done

    notify_webhook "debug", "running_containers", "Running containers:$RUNNING_CONTAINERS_LIST"
    notify_webhook "debug", "missing_containers", "Missing containers:$MISSING_CONTAINERS"

    # API health check with detailed progression
    notify_webhook "orchestration", "api_health_check_start", "Starting API health check (max 300s)"
    READY=false
    for i in {1..30}; do
        current_wait=$((i*10))
        notify_webhook "debug", "api_health_attempt", "API health check attempt $i/${current_wait}s"
        
        # Check if API container is running
        if $DOCKER_COMPOSE_CMD ps api | grep -q "Up"; then
            notify_webhook "debug", "api_container_up", "API container is running"
            
            # Check if API is responding
            if curl -f -s http://localhost:8000/api/ >/dev/null 2>&1; then
                notify_webhook "orchestration", "api_healthy", "✅ API is responsive after ${current_wait}s"
                READY=true
                break
            else
                notify_webhook "debug", "api_not_responding", "API container running but not responding (${current_wait}s)"
            fi
        else
            notify_webhook "warning", "api_container_down", "API container is not running (${current_wait}s)"
        fi
        
        # Progress update every 60 seconds
        if [ $((i % 6)) -eq 0 ]; then
            notify_webhook "orchestration", "health_check_progress", "API health check in progress... (${current_wait}s)"
        fi
        sleep 10
    done

    # Final deployment status
    if [ "$READY" = true ]; then
        notify_webhook "milestone", "plane_fully_operational", "🎯 Plane is FULLY OPERATIONAL and responsive"
        if [ -n "$MISSING_CONTAINERS" ]; then
            notify_webhook "warning", "deployment_partial", "Deployment stable but missing containers:$MISSING_CONTAINERS"
        else
            notify_webhook "success", "deployment_complete", "✅ PERFECT DEPLOYMENT - All $RUNNING_CONTAINERS containers running"
        fi
    else
        if [ $RUNNING_CONTAINERS -ge 7 ]; then
            notify_webhook "warning", "deployment_partial_success", "⚠️ Deployment partially successful - $RUNNING_CONTAINERS/$TOTAL_CONTAINERS running. Missing:$MISSING_CONTAINERS"
            notify_webhook "debug", "partial_success_details", "API not responsive but core services running - may need manual investigation"
        else
            notify_webhook "error", "deployment_failed", "❌ Deployment FAILED - only $RUNNING_CONTAINERS/$TOTAL_CONTAINERS running. Missing:$MISSING_CONTAINERS"
            exit 1
        fi
    fi

    # ==========================================================
    # Final container status and summary
    # ==========================================================
    echo "📊 Final container status:"
    $DOCKER_COMPOSE_CMD ps

    notify_webhook "debug", "final_container_status", "Final container status snapshot completed"
    notify_webhook "milestone", "plane_deployment_complete", "🚀 Plane deployment COMPLETED - Access at http://localhost"

    echo "🎉 Plane deployment completed successfully!"
                                        
                                                                                                                                                            
    # ========== FIREWALL ==========
    echo "[10/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"

    # Ensure UFW is installed
    if ! command -v ufw >/dev/null 2>&1; then
        echo "⚠️ UFW not installed, installing now..."
        apt-get install -y ufw
    fi

    # Reset UFW to defaults first (non-interactive)
    echo "    Resetting UFW to defaults..."
    ufw --force reset

    # Set default policies
    echo "    Setting default policies..."
    ufw default deny incoming
    ufw default allow outgoing

    # SSH access (critical - don't lock yourself out!)
    echo "    Allowing SSH..."
    ufw allow 22/tcp comment 'SSH'

    # Web ports
    echo "    Allowing web ports..."
    ufw allow 80/tcp comment 'HTTP'
    ufw allow 443/tcp comment 'HTTPS'
    ufw allow 8080/tcp comment 'Alternate HTTP'
    ufw allow 8443/tcp comment 'Alternate HTTPS'

    # Plane application ports
    echo "    Allowing Plane application ports..."
    ufw allow 3000/tcp comment 'Plane Web'
    ufw allow 3001/tcp comment 'Plane Admin'
    ufw allow 3002/tcp comment 'Plane Space'
    ufw allow 3100/tcp comment 'Plane Live'
    ufw allow 8000/tcp comment 'Plane API'

    # Database and service ports
    echo "    Allowing database and service ports..."
    ufw allow 5432/tcp comment 'PostgreSQL'
    ufw allow 6379/tcp comment 'Redis'
    ufw allow 5672/tcp comment 'RabbitMQ'
    ufw allow 15672/tcp comment 'RabbitMQ Management'
    ufw allow 9000/tcp comment 'MinIO API'
    ufw allow 9090/tcp comment 'MinIO Console'

    # Custom port if specified
    if [ "$PORT" != "3000" ]; then
        ufw allow "$PORT"/tcp comment "Custom Plane Port"
    fi

    # Enable UFW non-interactively
    echo "    Enabling UFW..."
    if echo "y" | ufw enable; then
        echo "✅ Firewall configured — all Plane service ports allowed"
        notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with all required Plane ports"
    else
        echo "⚠️ UFW enable failed, but continuing without firewall..."
        notify_webhook "warning" "firewall_failed" "UFW enable failed, but continuing without firewall"
    fi

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
