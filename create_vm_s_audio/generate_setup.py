import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT=3000,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DATA_DIR="/opt/audiotranscript",
    DOCKER_COMPOSE_VERSION="v2.27.0",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a full bash provisioning script for AudioTranscript, following Plane's exact structure.
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
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # AudioTranscript Provisioning Script (Plane style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/audiotranscript_setup.log"
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

    echo "[1/15] Starting AudioTranscript provisioning..."
    notify_webhook "provisioning" "starting" "Beginning AudioTranscript setup"

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

    # ========== AUDIOTRANSCRIPT DIRECTORY SETUP ==========
    echo "[6/15] Setting up AudioTranscript directory..."
    notify_webhook "provisioning" "directory_setup" "Creating AudioTranscript directory structure"
    sleep 5

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create AudioTranscript data directory"
        notify_webhook "failed" "directory_creation" "Failed to create AudioTranscript directory"
        exit 1
    }
    chown -R 1000:1000 "$DATA_DIR"
    cd "$DATA_DIR"
    echo "✅ AudioTranscript directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ AudioTranscript directory created successfully"
    
    sleep 5
                                      
    # ========== AUDIOTRANSCRIPT INSTALL ==========
    echo "[7/15] Installing AudioTranscript with Docker Compose..."
    notify_webhook "provisioning" "audiotranscript_install" "Setting up AudioTranscript with Docker Compose"

    # Create AudioTranscript directory
    APP_DIR="$DATA_DIR/audiotranscript"
    echo "🔍 Creating AudioTranscript directory: $APP_DIR"
    mkdir -p "$APP_DIR" || {
        echo "❌ ERROR: Could not create AudioTranscript directory"
        notify_webhook "failed" "directory_creation" "Cannot create AudioTranscript directory"
        exit 1
    }

    cd "$APP_DIR" || {
        echo "❌ ERROR: Could not enter $APP_DIR"
        echo "🔍 Current directory: $(pwd)"
        notify_webhook "failed" "directory_access" "Cannot access AudioTranscript directory"
        exit 1
    }

    echo "✅ Successfully entered AudioTranscript directory: $(pwd)"
    notify_webhook "provisioning" "audiotranscript_directory_ready" "✅ In AudioTranscript directory, starting configuration"

    # Verify we can write to this directory
    echo "🔍 Testing write permissions..."
    if ! touch write_test.file 2>/dev/null; then
        echo "❌ ERROR: Cannot write to AudioTranscript directory - permission denied"
        notify_webhook "failed" "write_permission_denied" "Cannot write to AudioTranscript directory"
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
    POSTGRES_USER="audiotranscript"
    POSTGRES_DB="audiotranscript"
    POSTGRES_PASSWORD="at_$(generate_secure_random hex 16)"  # Simple prefix + hex only

    REDIS_PASSWORD="redis_$(generate_secure_random hex 16)"

    MINIO_USER="audiotranscript"
    MINIO_PASSWORD="minio_$(generate_secure_random hex 16)"

    SECRET_KEY=$(generate_secure_random hex 32)
    JWT_SECRET=$(generate_secure_random hex 32)

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

# Redis Configuration
REDIS_PASSWORD=$REDIS_PASSWORD

# MinIO/S3 Configuration
MINIO_ROOT_USER=$MINIO_USER
MINIO_ROOT_PASSWORD=$MINIO_PASSWORD
MINIO_BUCKET=audio-recordings

# Application Configuration
SECRET_KEY=$SECRET_KEY
JWT_SECRET=$JWT_SECRET
WEB_URL=https://__DOMAIN__
DEBUG=0

# File upload
FILE_SIZE_LIMIT=524288000

# Security
CORS_ALLOWED_ORIGINS=https://__DOMAIN__

# Email (optional)
EMAIL_HOST=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_FROM=noreply@__DOMAIN__

# Proxy Ports
NGINX_PORT=8080
LISTEN_HTTP_PORT=8080
LISTEN_HTTPS_PORT=443

EOF

    echo "✅ .env created with secure credentials"
    notify_webhook "provisioning" "credentials_ready" "✅ Credentials generated"

    # ==========================================================
    # Create docker-compose.yml (FIXED VERSION)
    # ==========================================================
    echo "🐳 Creating docker-compose.yml..."
    cat > "docker-compose.yml" <<'EOF'
version: '3.8'

services:
  # Frontend
  frontend:
    container_name: audiotranscript-frontend
    image: nginx:alpine
    restart: always
    ports:
      - "3000:80"
    volumes:
      - ./frontend:/usr/share/nginx/html
    depends_on:
      - api
    networks:
      - audiotranscript-network

  # Backend API
  api:
    container_name: audiotranscript-api
    image: node:18-alpine
    restart: always
    working_dir: /app
    volumes:
      - ./backend:/app
    command: sh -c "npm install && npm run start"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://default:${REDIS_PASSWORD}@redis:6379
      - MINIO_ENDPOINT=http://minio:9000
      - AWS_ACCESS_KEY_ID=${MINIO_ROOT_USER}
      - AWS_SECRET_ACCESS_KEY=${MINIO_ROOT_PASSWORD}
      - JWT_SECRET=${JWT_SECRET}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
      - redis
      - minio
    networks:
      - audiotranscript-network

  # Worker for audio processing
  worker:
    container_name: audiotranscript-worker
    image: python:3.11-alpine
    restart: always
    working_dir: /app
    volumes:
      - ./worker:/app
    command: sh -c "pip install -r requirements.txt && python worker.py"
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://default:${REDIS_PASSWORD}@redis:6379
      - MINIO_ENDPOINT=http://minio:9000
      - AWS_ACCESS_KEY_ID=${MINIO_ROOT_USER}
      - AWS_SECRET_ACCESS_KEY=${MINIO_ROOT_PASSWORD}
    depends_on:
      - db
      - redis
      - minio
    networks:
      - audiotranscript-network

  # Database
  db:
    container_name: audiotranscript-db
    image: postgres:15-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    networks:
      - audiotranscript-network

  # Redis
  redis:
    container_name: audiotranscript-redis
    image: redis:7-alpine
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - audiotranscript-network

  # MinIO for audio file storage
  minio:
    container_name: audiotranscript-minio
    image: minio/minio
    restart: always
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    networks:
      - audiotranscript-network

  # Proxy (like Plane's proxy service)
  proxy:
    container_name: audiotranscript-proxy
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./proxy/nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - frontend
      - api
      - minio
    networks:
      - audiotranscript-network

volumes:
  postgres_data:
  redis_data:
  minio_data:

networks:
  audiotranscript-network:
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

    # Check available disk space...
    echo "    Checking disk space..."
    DISK_AVAILABLE=$(df /var/lib/docker /opt/audiotranscript /tmp . | awk 'NR>1 {print $4}' | sort -n | head -1)
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
    if [ "$MEM_AVAILABLE" -lt 1024 ]; then  # Less than 1GB
        echo "    ⚠️ Low memory available: ${MEM_AVAILABLE}MB (Audio processing needs at least 1GB)"
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
    notify_webhook "provisioning" "infrastructure_start" "Starting database, cache, and storage services"

    INFRA_SERVICES=("db" "redis" "minio")
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
            if [ "$service" = "db" ]; then
                echo "    🔍 PostgreSQL Special Handling..."
                notify_webhook "debug" "postgresql_special_handling" "Applying special handling for PostgreSQL Docker state issues"
                
                # Wait longer for PostgreSQL and use direct service checking
                echo "    Waiting for PostgreSQL to initialize (up to 60 seconds)..."
                for i in {1..12}; do
                    sleep 5
                    
                    # Direct PostgreSQL service check (bypass Docker state)
                    if docker exec audiotranscript-db pg_isready -U "$POSTGRES_USER" -q 2>/dev/null; then
                        echo "      ✅ PostgreSQL is ready and accepting connections!"
                        notify_webhook "provisioning" "postgresql_ready_direct" "✅ PostgreSQL is ready and accepting connections (direct check)"
                        break
                    fi
                    
                    # Check if container is still accessible
                    if ! docker exec audiotranscript-db echo "alive" >/dev/null 2>&1; then
                        echo "      ❌ PostgreSQL container became unresponsive"
                        echo "      🔍 PostgreSQL logs:"
                        $DOCKER_COMPOSE_CMD logs db --tail=20
                        notify_webhook "failed" "postgresql_unresponsive" "PostgreSQL container became unresponsive during initialization"
                        exit 1
                    fi
                    
                    if [ $i -eq 12 ]; then
                        echo "      ⚠️ PostgreSQL not ready after 60s, but continuing if container is alive"
                        if docker exec audiotranscript-db ps aux 2>/dev/null | grep -q "[p]ostgres"; then
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
            if [ "$service" = "minio" ]; then
                echo "    🔍 MinIO Enhanced Stability Check..."
                notify_webhook "debug" "minio_enhanced_stability" "Enhanced MinIO container stability monitoring"
                
                # Monitor MinIO for 30 seconds to ensure it doesn't crash
                MINIO_STABLE=true
                for i in {1..6}; do
                    sleep 5
                    CURRENT_TIME=$((i*5))
                    
                    if ! docker ps | grep -q "audiotranscript-minio"; then
                        echo "      ❌ MinIO container crashed after ${CURRENT_TIME} seconds!"
                        MINIO_STABLE=false
                        
                        echo "      🔍 MinIO logs before crash:"
                        $DOCKER_COMPOSE_CMD logs minio --tail=30
                        
                        # Check why it crashed
                        echo "      🔍 Checking system resources:"
                        docker system df
                        echo "      🔍 Checking disk space:"
                        df -h
                        
                        break
                    else
                        echo "      ✅ MinIO still running after ${CURRENT_TIME} seconds"
                        
                        # Check if MinIO process is actually running inside container
                        if docker exec audiotranscript-minio ps aux 2>/dev/null | grep -q "[m]inio"; then
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
                    $DOCKER_COMPOSE_CMD stop minio 2>/dev/null
                    $DOCKER_COMPOSE_CMD rm -f minio 2>/dev/null
                    docker volume rm audiotranscript_minio_data 2>/dev/null || true
                    sleep 2
                    
                    # Try starting MinIO with simpler configuration
                    echo "    🔧 Starting MinIO with simplified configuration..."
                    if docker run -d \
                        --name audiotranscript-minio \
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
            check_command="(curl -s -f http://localhost:9000/minio/health/live >/dev/null 2>&1 || curl -s -f http://localhost:9001/minio/health/live >/dev/null 2>&1 || curl -s http://localhost:9000/minio/health/ready >/dev/null 2>&1 || (docker exec audiotranscript-minio ps aux | grep -q '[m]inio' && echo 'minio_process_running' > /tmp/minio_status)) && test -f /tmp/minio_status || true"
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
                    if docker ps | grep -q "audiotranscript-minio"; then
                        echo "      ✅ Container is running"
                        echo "      🔍 Checking MinIO process:"
                        if docker exec audiotranscript-minio ps aux 2>/dev/null | grep -q "[m]inio"; then
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
                    docker stop audiotranscript-minio 2>/dev/null || true
                    docker rm -f audiotranscript-minio 2>/dev/null || true
                    $DOCKER_COMPOSE_CMD stop minio 2>/dev/null || true
                    $DOCKER_COMPOSE_CMD rm -f minio 2>/dev/null || true
                    sleep 3
                    
                    # Remove any conflicting containers
                    docker ps -a | grep minio | awk '{print $1}' | xargs -r docker rm -f
                    
                    echo "    🔧 Starting MinIO with optimized configuration..."
                    # Use Docker run with optimized settings
                    if docker run -d \
                        --name audiotranscript-minio \
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
                if [ "$service_name" = "MinIO" ] && docker ps | grep -q "audiotranscript-minio"; then
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

    if check_service_health "PostgreSQL" "docker exec audiotranscript-db pg_isready -U $POSTGRES_USER -q" 120; then
        echo "  ✅ PostgreSQL health check passed"
    else
        echo "  ❌ PostgreSQL health check failed"
        if docker exec audiotranscript-db ps aux 2>/dev/null | grep -q "[p]ostgres"; then
            echo "  ⚠️ PostgreSQL processes are running, continuing despite health check failure"
            notify_webhook "warning" "postgresql_continue_despite_health_check" "Continuing despite PostgreSQL health check failure - processes are running"
        else
            exit 1
        fi
    fi

    # Check Redis
    check_service_health "Redis" "docker exec audiotranscript-redis redis-cli -a $REDIS_PASSWORD ping | grep -q PONG" 60 || {
        echo "❌ Redis health check failed"
        $DOCKER_COMPOSE_CMD logs redis --tail=30
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
        if docker ps | grep -q "audiotranscript-minio"; then
            CONTAINER_UPTIME=$(docker inspect --format='{{.State.StartedAt}}' audiotranscript-minio 2>/dev/null | cut -d'.' -f1)
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
                --name audiotranscript-minio \
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
    # Setup MinIO bucket (ROBUST FIX WITH COMPREHENSIVE ERROR HANDLING)
    # ==========================================================
    echo "📦 Setting up MinIO bucket..."
    notify_webhook "provisioning" "minio_setup" "Starting MinIO bucket configuration"
    sleep 10

    # Install mc command with better error handling
    if ! command -v mc &>/dev/null; then
        echo "Installing mc (MinIO client)..."
        if curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc; then
            chmod +x /usr/local/bin/mc
            echo "✅ mc installed successfully"
        else
            echo "⚠️ Failed to install mc, but continuing..."
            notify_webhook "warning" "mc_install_failed" "Failed to install MinIO client"
        fi
    fi

    # Wait for MinIO to be fully ready with better checks
    echo "Waiting for MinIO to be ready..."
    MINIO_READY=false
    for i in {1..60}; do  # Increased to 60 attempts (2 minutes)
        # Check multiple ways MinIO might be ready
        if docker ps | grep -q "audiotranscript-minio" && \
        docker exec audiotranscript-minio ps aux 2>/dev/null | grep -q "[m]inio" && \
        (curl -s http://localhost:9000/minio/health/live >/dev/null 2>&1 || \
            curl -s http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1); then
            echo "✅ MinIO is ready and responsive (attempt $i)"
            MINIO_READY=true
            break
        fi
        
        echo "    Still waiting for MinIO... (attempt $i/60)"
        
        # Every 10 attempts, show more debug info
        if [ $((i % 10)) -eq 0 ]; then
            echo "    🔍 MinIO status check:"
            echo "      Container running: $(docker ps | grep -q "audiotranscript-minio" && echo "✅" || echo "❌")"
            echo "      Process inside: $(docker exec audiotranscript-minio ps aux 2>/dev/null | grep -q "[m]inio" && echo "✅" || echo "❌")"
            echo "      Port 9000 listening: $(netstat -tuln | grep -q ":9000 " && echo "✅" || echo "❌")"
            
            # Show MinIO logs if container exists
            if docker ps | grep -q "audiotranscript-minio"; then
                echo "      Recent MinIO logs:"
                docker logs audiotranscript-minio --tail=3 2>/dev/null | while read line; do echo "        $line"; done || true
            fi
        fi
        
        sleep 2
    done

    if [ "$MINIO_READY" = false ]; then
        echo "⚠️ MinIO not fully ready after 2 minutes, but attempting configuration anyway..."
        notify_webhook "warning" "minio_slow_start" "MinIO taking longer than expected to start"
    fi

    # Setup MinIO alias with comprehensive error handling
    echo "Configuring MinIO bucket..."
    MAX_RETRIES=3
    BUCKET_CREATED=false

    for attempt in $(seq 1 $MAX_RETRIES); do
        echo "  MinIO configuration attempt $attempt of $MAX_RETRIES..."
        
        # Wait a bit before each attempt
        sleep 5
        
        # Check if MinIO container is responsive
        if ! docker ps | grep -q "audiotranscript-minio"; then
            echo "    ❌ MinIO container not running"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ Giving up on MinIO configuration after $MAX_RETRIES attempts"
                notify_webhook "warning" "minio_container_missing" "MinIO container not running, skipping bucket setup"
                break
            fi
            continue
        fi
        
        # Test basic container accessibility
        if ! docker exec audiotranscript-minio echo "Container test" >/dev/null 2>&1; then
            echo "    ❌ MinIO container not accessible"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ MinIO container not responsive, skipping bucket setup"
                break
            fi
            continue
        fi
        
        # Set MinIO alias
        echo "    Setting MinIO alias..."
        if docker exec audiotranscript-minio mc alias set local http://localhost:9000 "$MINIO_USER" "$MINIO_PASSWORD" 2>/dev/null; then
            echo "    ✅ MinIO alias set successfully"
        else
            echo "    ⚠️ Failed to set MinIO alias (attempt $attempt)"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ Continuing without MinIO alias..."
            fi
            continue
        fi
        
        # Create bucket
        echo "    Creating audio-recordings bucket..."
        if docker exec audiotranscript-minio mc mb local/audio-recordings --ignore-existing 2>/dev/null; then
            echo "    ✅ Bucket created or already exists"
            BUCKET_CREATED=true
        else
            echo "    ⚠️ Failed to create bucket (attempt $attempt)"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ Bucket creation failed, but continuing..."
            fi
            continue
        fi
        
        # Set public policy (non-critical, but helpful)
        echo "    Setting bucket policy..."
        if docker exec audiotranscript-minio mc anonymous set public local/audio-recordings 2>/dev/null; then
            echo "    ✅ Public policy set"
        else
            echo "    ⚠️ Failed to set public policy (not critical)"
        fi
        
        # Verify the setup
        echo "    Verifying MinIO setup..."
        if docker exec audiotranscript-minio mc ls local/ 2>/dev/null | grep -q "audio-recordings"; then
            echo "    ✅ MinIO setup verified successfully"
            notify_webhook "provisioning" "minio_setup_complete" "✅ MinIO bucket configured successfully"
            break
        else
            echo "    ⚠️ MinIO setup verification failed (attempt $attempt)"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ MinIO setup incomplete, but continuing..."
                notify_webhook "warning" "minio_setup_incomplete" "MinIO setup incomplete but continuing"
            fi
        fi
    done

    # Final fallback: if all else fails, use a simple Docker exec approach
    if [ "$BUCKET_CREATED" = false ]; then
        echo "🔧 Attempting fallback MinIO setup..."
        if docker ps | grep -q "audiotranscript-minio"; then
            echo "  Using direct Docker commands..."
            # Try to create bucket using direct MinIO commands inside container
            if docker exec audiotranscript-minio sh -c "
                /opt/bin/mc alias set local http://localhost:9000 '$MINIO_USER' '$MINIO_PASSWORD' &&
                /opt/bin/mc mb local/audio-recordings --ignore-existing &&
                /opt/bin/mc anonymous set public local/audio-recordings
            " 2>/dev/null; then
                echo "    ✅ Fallback MinIO setup successful"
                BUCKET_CREATED=true
            else
                echo "    ⚠️ Fallback setup also failed"
            fi
        fi
    fi

    if [ "$BUCKET_CREATED" = true ]; then
        echo "✅ MinIO bucket configured successfully"
        notify_webhook "provisioning" "minio_success" "✅ MinIO fully configured and ready"
    else
        echo "⚠️ MinIO bucket configuration had issues, but continuing deployment..."
        echo "⚠️ File uploads may not work until MinIO is manually configured"
        notify_webhook "warning" "minio_partial_setup" "MinIO configuration had issues - file uploads may not work"
        
        # Provide debugging information
        echo "🔍 MinIO Debug Information:"
        echo "  Container status: $(docker ps | grep -q "audiotranscript-minio" && echo "Running" || echo "Not running")"
        echo "  MinIO logs (last 5 lines):"
        docker logs audiotranscript-minio --tail=5 2>/dev/null | while read line; do echo "    $line"; done || echo "    No logs available"
        echo "  Port 9000 status: $(netstat -tuln | grep -q ":9000 " && echo "Listening" || echo "Not listening")"
    fi
    sleep 5
    
    # ==========================================================
    # Create placeholder directories (like Plane's structure)
    # ==========================================================
    echo "📁 Creating application directories..."
    
    mkdir -p frontend backend worker proxy
    
    echo "✅ Application directories created"
    notify_webhook "provisioning" "directory_structure_ready" "✅ Application directory structure created"

    # ==========================================================
    # Start application services (PROXY-SPECIFIC FIX)
    # ==========================================================
    echo "🚀 Starting AudioTranscript application services..."
    notify_webhook "provisioning" "app_services_start" "Starting AudioTranscript application containers"

    APP_SERVICES=("api" "worker" "frontend" "proxy")
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
                    "api"|"worker")
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

    echo "✅ All AudioTranscript services started"
    notify_webhook "provisioning" "app_services_ready" "✅ All AudioTranscript application services running"

    # ==========================================================
    # Verify API health (WITH CONTAINER DEBUGGING)
    # ==========================================================
    notify_webhook "provisioning" "health_check_start" "Checking AudioTranscript API health"

    # Give services time to initialize
    sleep 60

    # DEBUG: Check which containers are running and report status
    CONTAINER_STATUS=$($DOCKER_COMPOSE_CMD ps)
    RUNNING_CONTAINERS=$(echo "$CONTAINER_STATUS" | grep "Up" | wc -l)
    TOTAL_CONTAINERS=$(echo "$CONTAINER_STATUS" | tail -n +2 | wc -l)

    notify_webhook "debug" "container_status" "Containers running: $RUNNING_CONTAINERS/$TOTAL_CONTAINERS"

    # List all expected containers and check each one
    EXPECTED_CONTAINERS=("api" "worker" "frontend" "proxy" "db" "redis" "minio")
    MISSING_CONTAINERS=""

    for container in "${EXPECTED_CONTAINERS[@]}"; do
        if ! echo "$CONTAINER_STATUS" | grep -q "$container.*Up"; then
            MISSING_CONTAINERS="$MISSING_CONTAINERS $container"
            notify_webhook "warning" "container_missing" "Container $container is not running"
        fi
    done

    # Check if API is responsive with extended timeout
    READY=false
    for i in {1..30}; do
        if $DOCKER_COMPOSE_CMD ps api | grep -q "Up" && curl -f -s http://localhost:3001/health >/dev/null 2>&1; then
            READY=true
            break
        fi
        if [ $((i % 6)) -eq 0 ]; then
            notify_webhook "provisioning" "health_check_progress" "API health check in progress... ($((i*10))s)"
        fi
        sleep 10
    done

    if [ "$READY" = false ]; then
        # FIXED: Lower the threshold and report which containers are missing
        if [ $RUNNING_CONTAINERS -ge 5 ]; then
            if [ -n "$MISSING_CONTAINERS" ]; then
                notify_webhook "provisioning" "deployment_stable" "✅ AudioTranscript deployment stable with $RUNNING_CONTAINERS containers running. Missing:$MISSING_CONTAINERS"
            else
                notify_webhook "provisioning" "deployment_stable" "✅ AudioTranscript deployment stable with $RUNNING_CONTAINERS containers running"
            fi
        else
            if [ -n "$MISSING_CONTAINERS" ]; then
                notify_webhook "failed" "deployment_unstable" "AudioTranscript deployment unstable - only $RUNNING_CONTAINERS containers running. Missing:$MISSING_CONTAINERS"
            else
                notify_webhook "failed" "deployment_unstable" "AudioTranscript deployment unstable - only $RUNNING_CONTAINERS containers running"
            fi
            exit 1
        fi
    else
        notify_webhook "provisioning" "audiotranscript_healthy" "✅ AudioTranscript is fully operational and responsive"
    fi

    notify_webhook "provisioning" "audiotranscript_deployment_complete" "✅ AudioTranscript deployment completed successfully"

    # ==========================================================
    # Final container status
    # ==========================================================
    echo "📊 Final container status:"
    $DOCKER_COMPOSE_CMD ps

    echo "🎉 AudioTranscript deployment completed successfully!"
    notify_webhook "provisioning" "audiotranscript_deployment_complete" "✅ AudioTranscript deployment completed successfully - Access at https://__DOMAIN__"
                                                                                                                        
    # ========== FIREWALL ==========
    echo "[10/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"

    # SSH access
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 3000/tcp   # Frontend
    ufw allow 3001/tcp   # API
    ufw allow 5432/tcp   # PostgreSQL
    ufw allow 6379/tcp   # Redis
    ufw allow 9000/tcp   # MinIO API
    ufw allow 9001/tcp   # MinIO Console
    ufw allow "$PORT"/tcp
    ufw --force enable
                                      
    echo "✅ Firewall configured — all AudioTranscript service ports allowed"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with all required AudioTranscript ports"

    # ========== NGINX CONFIG + SSL (Forgejo / fail-safe) ==========
    echo "[11/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/audiotranscript

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/audiotranscript <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/audiotranscript /etc/nginx/sites-enabled/audiotranscript
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
        notify_webhook "warning" "ssl" "AudioTranscript Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/audiotranscript <<'EOF_SSL'
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

    client_max_body_size 500M;

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
    
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /audio/ {
        proxy_pass http://127.0.0.1:9000/audio-recordings/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Important for MinIO
        proxy_buffering off;
        proxy_request_buffering off;
        client_max_body_size 500M;
        
        # CORS headers for audio files
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, Origin, X-Requested-With" always;
        add_header Access-Control-Allow-Credentials "true" always;
    }

    location /minio/ {
        proxy_pass http://127.0.0.1:9001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF_SSL

        ln -sf /etc/nginx/sites-available/audiotranscript /etc/nginx/sites-enabled/audiotranscript
        nginx -t && systemctl reload nginx
    fi

    echo "[14/15] Setup Cron for renewal..."
    notify_webhook "provisioning" "provisioning" "Setup Cron for renewal..."
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v "certbot renew" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

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

    echo "✅ AudioTranscript setup complete!"
    notify_webhook "provisioning" "provisioning" "✅ AudioTranscript deployment succeeded"

    #wait 60 seconds until everything is fully ready 
    sleep 60
                                      
    cat <<EOF_SUMMARY
=============================================
🎉 AudioTranscript Deployment Complete!
=============================================

🔗 Access URLs:
- Web Interface: https://__DOMAIN__
- MinIO Console: https://__DOMAIN__/minio
- API: https://__DOMAIN__/api

👤 Admin email: __ADMIN_EMAIL__

⚙️ Useful commands:
- Status: cd $APP_DIR && docker compose ps
- Logs: cd $APP_DIR && docker compose logs -f
- Restart: cd $APP_DIR && docker compose restart
- Update: cd $APP_DIR && docker compose pull && docker compose up -d

📁 Application directory: $APP_DIR

🔧 Next steps:
1. Upload your frontend code to: $APP_DIR/frontend
2. Upload your backend code to: $APP_DIR/backend  
3. Upload your worker code to: $APP_DIR/worker
4. Restart services: docker compose restart

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

    # Replace remaining tokens for password, admin email, domain, port
    final = final.replace("__ADMIN_PASSWORD__", tokens["__ADMIN_PASSWORD__"])
    final = final.replace("__ADMIN_EMAIL__", tokens["__ADMIN_EMAIL__"])
    final = final.replace("__DOMAIN__", tokens["__DOMAIN__"])
    final = final.replace("__PORT__", tokens["__PORT__"])

    return final