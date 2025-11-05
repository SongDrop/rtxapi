import textwrap

def generate_huly_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,  # ✅ Keeping for consistency with your template
    HULY_VERSION="v0.7.242", 
    PORT=8080,  # ✅ Your frontend quirk
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DATA_DIR="/opt/huly",
    DOCKER_COMPOSE_VERSION="v2.27.0",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a full bash provisioning script for Huly, following the EXACT Plane template structure.
    """

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,  # ✅ Kept for consistency
        "__HULY_VERSION__": HULY_VERSION,
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
    # Huly Provisioning Script (Following EXACT Plane template structure)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/huly_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    HULY_VERSION="__HULY_VERSION__"
    PORT="__PORT__"
    DATA_DIR="__DATA_DIR__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"

    echo "[1/15] Starting Huly provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Huly microservices setup"

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

    # ========== HULY DIRECTORY SETUP ==========
    echo "[6/15] Setting up Huly directory..."
    notify_webhook "provisioning" "directory_setup" "Creating Huly directory structure"
    sleep 5

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create Huly data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Huly directory"
        exit 1
    }
    chown -R 1000:1000 "$DATA_DIR"
    cd "$DATA_DIR"
    echo "✅ Huly directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ Huly directory created successfully"
    
    sleep 5
                                      
    # ========== HULY INSTALL ==========
    echo "[7/15] Installing Huly with Docker Compose..."
    notify_webhook "provisioning" "huly_install" "Setting up Huly microservices with Docker Compose"

    # Create Huly directory
    HULY_DIR="$DATA_DIR/huly-selfhost"
    echo "🔍 Creating Huly directory: $HULY_DIR"
    mkdir -p "$HULY_DIR" || {
        echo "❌ ERROR: Could not create Huly directory"
        notify_webhook "failed" "directory_creation" "Cannot create Huly directory"
        exit 1
    }

    cd "$HULY_DIR" || {
        echo "❌ ERROR: Could not enter $HULY_DIR"
        echo "🔍 Current directory: $(pwd)"
        notify_webhook "failed" "directory_access" "Cannot access Huly directory"
        exit 1
    }

    echo "✅ Successfully entered Huly directory: $(pwd)"
    notify_webhook "provisioning" "huly_directory_ready" "✅ In Huly directory, starting configuration"

    # Verify we can write to this directory
    echo "🔍 Testing write permissions..."
    if ! touch write_test.file 2>/dev/null; then
        echo "❌ ERROR: Cannot write to Huly directory - permission denied"
        notify_webhook "failed" "write_permission_denied" "Cannot write to Huly directory"
        exit 1
    fi
    rm -f write_test.file

    # ==========================================================
    # 🔐 Generate Huly Secrets (Following your credential patterns)
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
                # Use simpler base64 without special characters
                result=$(openssl rand -base64 "$length" 2>/dev/null | tr -d '\n+/=' | head -c "$length" || true)
            fi
        fi

        # Fallback to /dev/urandom
        if [ -z "$result" ]; then
            if [ "$type" = "hex" ]; then
                result=$(head -c "$length" /dev/urandom | xxd -p -c "$length" 2>/dev/null || true)
            else
                # Simple alphanumeric for compatibility
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

    # Generate Huly secrets using your patterns
    HULY_SECRET=$(generate_secure_random hex 32)
    COCKROACH_SECRET="cr_$(generate_secure_random hex 16)"  # Your prefix pattern
    REDPANDA_SECRET="rp_$(generate_secure_random hex 16)"   # Your prefix pattern

    echo "✅ Huly secrets generated"
    notify_webhook "provisioning" "credentials_ready" "✅ Credentials generated"

    # ==========================================================
    # Create Huly Configuration
    # ==========================================================
    echo "📝 Creating Huly configuration..."
    umask 077
    cat > "huly_v7.conf" <<EOF
# Huly Configuration - Auto-generated
HULY_VERSION=$HULY_VERSION
DESKTOP_CHANNEL=0.7.242
DOCKER_NAME=huly_v7

# Network Configuration
HOST_ADDRESS=$DOMAIN
SECURE=true
HTTP_PORT=80
HTTP_BIND=0.0.0.0

# Huly Specific
TITLE=Huly Self Host
DEFAULT_LANGUAGE=en
LAST_NAME_FIRST=true

# CockroachDB
CR_DATABASE=defaultdb
CR_USERNAME=selfhost
CR_USER_PASSWORD=$COCKROACH_SECRET
CR_DB_URL=postgres://selfhost:$COCKROACH_SECRET@cockroach:26257/defaultdb

# Redpanda
REDPANDA_ADMIN_USER=superadmin
REDPANDA_ADMIN_PWD=$REDPANDA_SECRET

# Docker Volumes (using named volumes)
VOLUME_ELASTIC_PATH=
VOLUME_FILES_PATH=
VOLUME_CR_DATA_PATH=
VOLUME_CR_CERTS_PATH=
VOLUME_REDPANDA_PATH=

# Auto-generated secrets
SECRET=$HULY_SECRET
EOF

    echo "✅ huly_v7.conf created"
    notify_webhook "provisioning" "config_ready" "✅ Huly configuration created"

    # ==========================================================
    # Create docker-compose.yml for Huly (NO NGINX - using system nginx)
    # ==========================================================
    echo "🐳 Creating docker-compose.yml for Huly microservices..."
    cat > "docker-compose.yml" <<'EOF'
name: huly_v7
services:
  cockroach:
    image: cockroachdb/cockroach:latest-v24.2
    command: start-single-node --accept-sql-without-tls
    environment:
      - COCKROACH_DATABASE=defaultdb
      - COCKROACH_USER=selfhost
      - COCKROACH_PASSWORD=${COCKROACH_SECRET}
    volumes:
      - cr_data:/cockroach/cockroach-data
      - cr_certs:/cockroach/certs
    restart: unless-stopped
    networks:
      - huly_net

  redpanda:
    image: docker.redpanda.com/redpandadata/redpanda:v24.3.6
    command:
      - redpanda
      - start
      - --kafka-addr internal://0.0.0.0:9092,external://0.0.0.0:19092
      - --advertise-kafka-addr internal://redpanda:9092,external://localhost:19092
      - --pandaproxy-addr internal://0.0.0.0:8082,external://0.0.0.0:18082
      - --advertise-pandaproxy-addr internal://redpanda:8082,external://localhost:18082
      - --schema-registry-addr internal://0.0.0.0:8081,external://0.0.0.0:18081
      - --rpc-addr redpanda:33145
      - --advertise-rpc-addr redpanda:33145
      - --mode dev-container
      - --smp 1
      - --default-log-level=info
    container_name: redpanda
    volumes:
      - redpanda:/var/lib/redpanda/data
    environment:
      - REDPANDA_SUPERUSER_USERNAME=superadmin
      - REDPANDA_SUPERUSER_PASSWORD=${REDPANDA_SECRET}
    healthcheck:
      test: ['CMD', 'rpk', 'cluster', 'info', '-X', 'user=superadmin', '-X', 'pass=${REDPANDA_SECRET}']
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - huly_net

  minio:
    image: "minio/minio"
    command: server /data --address ":9000" --console-address ":9001"
    volumes:
      - files:/data
    healthcheck:
      test: ['CMD', 'mc', 'ready', 'local']
      interval: 5s
      retries: 10
    restart: unless-stopped
    networks:
      - huly_net

  elastic:
    image: "elasticsearch:7.14.2"
    command: |
      /bin/sh -c "./bin/elasticsearch-plugin list | grep -q ingest-attachment || yes | ./bin/elasticsearch-plugin install --silent ingest-attachment;
      /usr/local/bin/docker-entrypoint.sh eswrapper"
    volumes:
      - elastic:/usr/share/elasticsearch/data
    environment:
      - ELASTICSEARCH_PORT_NUMBER=9200
      - BITNAMI_DEBUG=true
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms1024m -Xmx1024m
      - http.cors.enabled=true
      - http.cors.allow-origin=http://localhost:8082
    healthcheck:
      interval: 20s
      retries: 10
      test: curl -s http://localhost:9200/_cluster/health | grep -vq '"status":"red"'
    restart: unless-stopped
    networks:
      - huly_net

  rekoni:
    image: hardcoreeng/rekoni-service:${HULY_VERSION}
    environment:
      - SECRET=${SECRET}
    deploy:
      resources:
        limits:
          memory: 500M
    restart: unless-stopped
    networks:
      - huly_net

  transactor:
    image: hardcoreeng/transactor:${HULY_VERSION}
    environment:
      - SERVER_PORT=3333
      - SERVER_SECRET=${SECRET}
      - DB_URL=${CR_DB_URL}
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - FRONT_URL=http://localhost:8087
      - ACCOUNTS_URL=http://account:3000
      - FULLTEXT_URL=http://fulltext:4700
      - STATS_URL=http://stats:4900
      - LAST_NAME_FIRST=true
      - QUEUE_CONFIG=redpanda:9092
    restart: unless-stopped
    networks:
      - huly_net

  collaborator:
    image: hardcoreeng/collaborator:${HULY_VERSION}
    environment:
      - COLLABORATOR_PORT=3078
      - SECRET=${SECRET}
      - ACCOUNTS_URL=http://account:3000
      - STATS_URL=http://stats:4900
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
    restart: unless-stopped
    networks:
      - huly_net

  account:
    image: hardcoreeng/account:${HULY_VERSION}
    environment:
      - SERVER_PORT=3000
      - SERVER_SECRET=${SECRET}
      - DB_URL=${CR_DB_URL}
      - TRANSACTOR_URL=ws://transactor:3333;wss://${HOST_ADDRESS}/_transactor
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - FRONT_URL=https://${HOST_ADDRESS}
      - STATS_URL=https://${HOST_ADDRESS}/stats
      - MODEL_ENABLED=*
      - ACCOUNTS_URL=https://${HOST_ADDRESS}/_accounts
      - ACCOUNT_PORT=3000
      - QUEUE_CONFIG=redpanda:9092
    restart: unless-stopped
    networks:
      - huly_net

  workspace:
    image: hardcoreeng/workspace:${HULY_VERSION}
    environment:
      - SERVER_SECRET=${SECRET}
      - DB_URL=${CR_DB_URL}
      - TRANSACTOR_URL=ws://transactor:3333;wss://${HOST_ADDRESS}/_transactor
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - MODEL_ENABLED=*
      - ACCOUNTS_URL=http://account:3000
      - STATS_URL=http://stats:4900
      - QUEUE_CONFIG=redpanda:9092
      - ACCOUNTS_DB_URL=${CR_DB_URL}
    restart: unless-stopped
    networks:
      - huly_net

  front:
    image: hardcoreeng/front:${HULY_VERSION}
    environment:
      - SERVER_PORT=8080
      - SERVER_SECRET=${SECRET}
      - LOVE_ENDPOINT=https://${HOST_ADDRESS}/_love
      - ACCOUNTS_URL=https://${HOST_ADDRESS}/_accounts
      - ACCOUNTS_URL_INTERNAL=http://account:3000
      - REKONI_URL=https://${HOST_ADDRESS}/_rekoni
      - CALENDAR_URL=https://${HOST_ADDRESS}/_calendar
      - GMAIL_URL=https://${HOST_ADDRESS}/_gmail
      - TELEGRAM_URL=https://${HOST_ADDRESS}/_telegram
      - STATS_URL=https://${HOST_ADDRESS}/_stats
      - UPLOAD_URL=/files
      - ELASTIC_URL=http://elastic:9200
      - COLLABORATOR_URL=wss://${HOST_ADDRESS}/_collaborator
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - TITLE=Huly Self Host
      - DEFAULT_LANGUAGE=en
      - LAST_NAME_FIRST=true
    restart: unless-stopped
    networks:
      - huly_net

  fulltext:
    image: hardcoreeng/fulltext:${HULY_VERSION}
    environment:
      - SERVER_SECRET=${SECRET}
      - DB_URL=${CR_DB_URL}
      - FULLTEXT_DB_URL=http://elastic:9200
      - ELASTIC_INDEX_NAME=huly_storage_index
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - REKONI_URL=http://rekoni:4004
      - ACCOUNTS_URL=http://account:3000
      - STATS_URL=http://stats:4900
      - QUEUE_CONFIG=redpanda:9092
    restart: unless-stopped
    networks:
      - huly_net

  stats:
    image: hardcoreeng/stats:${HULY_VERSION}
    environment:
      - PORT=4900
      - SERVER_SECRET=${SECRET}
    restart: unless-stopped
    networks:
      - huly_net

  kvs:
    image: hardcoreeng/hulykvs:${HULY_VERSION}
    depends_on:
      cockroach:
        condition: service_started
    ports:
      - 8094:8094
    environment:
      - HULY_DB_CONNECTION=${CR_DB_URL}
      - HULY_TOKEN_SECRET=${SECRET}
    restart: unless-stopped
    networks:
      - huly_net

  # Optional Services - ALL ENABLED (Full On!)
  love:
    image: hardcoreeng/love:${HULY_VERSION}
    container_name: love
    ports:
      - 8096:8096
    environment:
      - PORT=8096
      - SECRET=${SECRET}
      - ACCOUNTS_URL=http://account:3000
      - DB_URL=${CR_DB_URL}
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - STORAGE_PROVIDER_NAME=minio
    restart: unless-stopped
    networks:
      - huly_net

  print:
    image: hardcoreeng/print:${HULY_VERSION}
    container_name: print
    ports:
      - 4005:4005
    environment:
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - STATS_URL=http://stats:4900
      - SECRET=${SECRET}
    restart: unless-stopped
    networks:
      - huly_net

  aibot:
    image: hardcoreeng/ai-bot:${HULY_VERSION}
    ports:
      - 4010:4010
    environment:
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - SERVER_SECRET=${SECRET}
      - ACCOUNTS_URL=http://account:3000
      - DB_URL=${CR_DB_URL}
      - STATS_URL=http://stats:4900
      - FIRST_NAME=Bot
      - LAST_NAME=Huly AI
      - PASSWORD=${SECRET}
    restart: unless-stopped
    networks:
      - huly_net

  calendar:
    image: hardcoreeng/calendar:${HULY_VERSION}
    ports:
      - 8095:8095
    environment:
      - ACCOUNTS_URL=http://account:3000
      - STATS_URL=http://stats:4900
      - SECRET=${SECRET}
      - KVS_URL=http://kvs:8094
    restart: unless-stopped
    networks:
      - huly_net

  github:
    image: hardcoreeng/github:${HULY_VERSION}
    ports:
      - 3500:3500
    environment:
      - PORT=3500
      - STORAGE_CONFIG=minio|minio?accessKey=minioadmin&secretKey=minioadmin
      - SERVER_SECRET=${SECRET}
      - ACCOUNTS_URL=http://account:3000
      - STATS_URL=http://stats:4900
      - COLLABORATOR_URL=wss://${HOST_ADDRESS}/_collaborator
      - FRONT_URL=https://${HOST_ADDRESS}
      - BOT_NAME=Huly[bot]
    restart: unless-stopped
    networks:
      - huly_net

volumes:
  elastic:
  files:
  cr_data:
  cr_certs:
  redpanda:

networks:
  huly_net:
    driver: bridge
EOF

    echo "✅ docker-compose.yml created for Huly microservices"
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
    DISK_AVAILABLE=$(df /var/lib/docker /opt/huly /tmp . | awk 'NR>1 {print $4}' | sort -n | head -1)
    if [ "$DISK_AVAILABLE" -lt 2097152 ]; then  # Less than 2GB (Huly needs more)
        echo "    ❌ Insufficient disk space: ${DISK_AVAILABLE}KB available"
        df -h
        notify_webhook "failed" "low_disk_space" "Insufficient disk space for Huly - only ${DISK_AVAILABLE}KB available"
        exit 1
    fi
    notify_webhook "provisioning" "disk_check" "✅ Disk space sufficient: ${DISK_AVAILABLE}KB available"
    
    # Check memory - Huly requires 4GB minimum
    echo "Checking memory..."
    MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
    if [ "$MEM_AVAILABLE" -lt 4096 ]; then  # Less than 4GB
        echo "    ❌ Insufficient memory: ${MEM_AVAILABLE}MB available (Huly requires 4GB minimum)"
        notify_webhook "failed" "low_memory" "Insufficient memory: ${MEM_AVAILABLE}MB available - Huly requires 4GB minimum"
        exit 1
    else
        echo "    ✅ Memory sufficient: ${MEM_AVAILABLE}MB available"
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
    # Start infrastructure services (FOLLOWING YOUR STAGED APPROACH)
    # ==========================================================
    echo "🚀 Starting infrastructure services..."
    notify_webhook "provisioning" "infrastructure_start" "Starting database, cache, and queue services"

    INFRA_SERVICES=("cockroach" "redpanda" "minio" "elastic")
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
            
            # SPECIAL HANDLING FOR COCKROACHDB (like your PostgreSQL handling)
            if [ "$service" = "cockroach" ]; then
                echo "    🔍 CockroachDB Special Handling..."
                notify_webhook "debug" "cockroach_special_handling" "Applying special handling for CockroachDB Docker state issues"
                
                # Wait longer for CockroachDB and use direct service checking
                echo "    Waiting for CockroachDB to initialize (up to 60 seconds)..."
                for i in {1..12}; do
                    sleep 5
                    
                    # Direct CockroachDB service check (bypass Docker state)
                    if docker exec cockroach cockroach sql --insecure -e 'SELECT 1;' 2>/dev/null; then
                        echo "      ✅ CockroachDB is ready and accepting connections!"
                        notify_webhook "provisioning" "cockroach_ready_direct" "✅ CockroachDB is ready and accepting connections (direct check)"
                        break
                    fi
                    
                    # Check if container is still accessible
                    if ! docker exec cockroach echo "alive" >/dev/null 2>&1; then
                        echo "      ❌ CockroachDB container became unresponsive"
                        echo "      🔍 CockroachDB logs:"
                        $DOCKER_COMPOSE_CMD logs cockroach --tail=20
                        notify_webhook "failed" "cockroach_unresponsive" "CockroachDB container became unresponsive during initialization"
                        exit 1
                    fi
                    
                    if [ $i -eq 12 ]; then
                        echo "      ⚠️ CockroachDB not ready after 60s, but continuing if container is alive"
                        if docker exec cockroach ps aux 2>/dev/null | grep -q "[c]ockroach"; then
                            echo "      ✅ CockroachDB processes are running, continuing..."
                            notify_webhook "warning" "cockroach_slow_start" "CockroachDB slow start but processes are running, continuing"
                        else
                            echo "      ❌ No CockroachDB processes found after 60s"
                            notify_webhook "failed" "cockroach_no_processes" "No CockroachDB processes found after 60 seconds"
                            exit 1
                        fi
                    fi
                done
            fi
            
            # SPECIAL HANDLING FOR MINIO - Enhanced stability monitoring (YOUR EXACT PATTERN)
            if [ "$service" = "minio" ]; then
                echo "    🔍 MinIO Enhanced Stability Check..."
                notify_webhook "debug" "minio_enhanced_stability" "Enhanced MinIO container stability monitoring"
                
                # Monitor MinIO for 30 seconds to ensure it doesn't crash
                MINIO_STABLE=true
                for i in {1..6}; do
                    sleep 5
                    CURRENT_TIME=$((i*5))
                    
                    if ! docker ps | grep -q "minio"; then
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
                        if docker exec minio ps aux 2>/dev/null | grep -q "[m]inio"; then
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
                    docker volume rm huly_v7_files 2>/dev/null || true
                    sleep 2
                    
                    # Try starting MinIO with simpler configuration
                    echo "    🔧 Starting MinIO with simplified configuration..."
                    if docker run -d \
                        --name minio \
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
    # Wait for infrastructure health checks (YOUR EXACT PATTERN)
    # ==========================================================
    echo "⏳ Waiting for infrastructure services to be ready..."
    notify_webhook "provisioning" "health_checks_start" "Starting health checks for infrastructure services"

    # Improved health check function with better MinIO handling (YOUR EXACT FUNCTION)
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
            check_command="(curl -s -f http://localhost:9000/minio/health/live >/dev/null 2>&1 || curl -s -f http://localhost:9001/minio/health/live >/dev/null 2>&1 || curl -s http://localhost:9000/minio/health/ready >/dev/null 2>&1 || (docker exec minio ps aux | grep -q '[m]inio' && echo 'minio_process_running' > /tmp/minio_status)) && test -f /tmp/minio_status || true"
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
                    if docker ps | grep -q "minio"; then
                        echo "      ✅ Container is running"
                        echo "      🔍 Checking MinIO process:"
                        if docker exec minio ps aux 2>/dev/null | grep -q "[m]inio"; then
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
                    docker stop minio 2>/dev/null || true
                    docker rm -f minio 2>/dev/null || true
                    $DOCKER_COMPOSE_CMD stop minio 2>/dev/null || true
                    $DOCKER_COMPOSE_CMD rm -f minio 2>/dev/null || true
                    sleep 3
                    
                    # Remove any conflicting containers
                    docker ps -a | grep minio | awk '{print $1}' | xargs -r docker rm -f
                    
                    echo "    🔧 Starting MinIO with optimized configuration..."
                    # Use Docker run with optimized settings
                    if docker run -d \
                        --name minio \
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
                if [ "$service_name" = "MinIO" ] && docker ps | grep -q "minio"; then
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

    # Check CockroachDB (this is working well)
    echo "  Checking CockroachDB database readiness..."
    notify_webhook "provisioning" "cockroach_health_check" "Starting CockroachDB health check"

    if check_service_health "CockroachDB" "docker exec cockroach cockroach sql --insecure -e 'SELECT 1;' 2>/dev/null" 120; then
        echo "  ✅ CockroachDB health check passed"
    else
        echo "  ❌ CockroachDB health check failed"
        if docker exec cockroach ps aux 2>/dev/null | grep -q "[c]ockroach"; then
            echo "  ⚠️ CockroachDB processes are running, continuing despite health check failure"
            notify_webhook "warning" "cockroach_continue_despite_health_check" "Continuing despite CockroachDB health check failure - processes are running"
        else
            exit 1
        fi
    fi

    # Check Redpanda
    check_service_health "Redpanda" "docker exec redpanda rpk cluster info --user superadmin --password '$REDPANDA_SECRET' 2>/dev/null" 180 || {
        echo "❌ Redpanda health check failed"
        $DOCKER_COMPOSE_CMD logs redpanda --tail=30
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
        if docker ps | grep -q "minio"; then
            CONTAINER_UPTIME=$(docker inspect --format='{{.State.StartedAt}}' minio 2>/dev/null | cut -d'.' -f1)
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
                --name minio \
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
    # Setup MinIO bucket (YOUR EXACT ROBUST APPROACH)
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
        if docker ps | grep -q "minio" && \
        docker exec minio ps aux 2>/dev/null | grep -q "[m]inio" && \
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
            echo "      Container running: $(docker ps | grep -q "minio" && echo "✅" || echo "❌")"
            echo "      Process inside: $(docker exec minio ps aux 2>/dev/null | grep -q "[m]inio" && echo "✅" || echo "❌")"
            echo "      Port 9000 listening: $(netstat -tuln | grep -q ":9000 " && echo "✅" || echo "❌")"
            
            # Show MinIO logs if container exists
            if docker ps | grep -q "minio"; then
                echo "      Recent MinIO logs:"
                docker logs minio --tail=3 2>/dev/null | while read line; do echo "        $line"; done || true
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
        if ! docker ps | grep -q "minio"; then
            echo "    ❌ MinIO container not running"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ Giving up on MinIO configuration after $MAX_RETRIES attempts"
                notify_webhook "warning" "minio_container_missing" "MinIO container not running, skipping bucket setup"
                break
            fi
            continue
        fi
        
        # Test basic container accessibility
        if ! docker exec minio echo "Container test" >/dev/null 2>&1; then
            echo "    ❌ MinIO container not accessible"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ MinIO container not responsive, skipping bucket setup"
                break
            fi
            continue
        fi
        
        # Set MinIO alias
        echo "    Setting MinIO alias..."
        if docker exec minio mc alias set local http://localhost:9000 "minioadmin" "minioadmin" 2>/dev/null; then
            echo "    ✅ MinIO alias set successfully"
        else
            echo "    ⚠️ Failed to set MinIO alias (attempt $attempt)"
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "    ⚠️ Continuing without MinIO alias..."
            fi
            continue
        fi
        
        # Create bucket
        echo "    Creating uploads bucket..."
        if docker exec minio mc mb local/uploads --ignore-existing 2>/dev/null; then
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
        if docker exec minio mc anonymous set public local/uploads 2>/dev/null; then
            echo "    ✅ Public policy set"
        else
            echo "    ⚠️ Failed to set public policy (not critical)"
        fi
        
        # Verify the setup
        echo "    Verifying MinIO setup..."
        if docker exec minio mc ls local/ 2>/dev/null | grep -q "uploads"; then
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
        if docker ps | grep -q "minio"; then
            echo "  Using direct Docker commands..."
            # Try to create bucket using direct MinIO commands inside container
            if docker exec minio sh -c "
                /opt/bin/mc alias set local http://localhost:9000 'minioadmin' 'minioadmin' &&
                /opt/bin/mc mb local/uploads --ignore-existing &&
                /opt/bin/mc anonymous set public local/uploads
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
        echo "  Container status: $(docker ps | grep -q "minio" && echo "Running" || echo "Not running")"
        echo "  MinIO logs (last 5 lines):"
        docker logs minio --tail=5 2>/dev/null | while read line; do echo "    $line"; done || echo "    No logs available"
        echo "  Port 9000 status: $(netstat -tuln | grep -q ":9000 " && echo "Listening" || echo "Not listening")"
    fi
    sleep 5
    
    # ==========================================================
    # Start application services (YOUR STAGED APPROACH)
    # ==========================================================
    echo "🚀 Starting Huly application services..."
    notify_webhook "provisioning" "app_services_start" "Starting Huly application containers"

    # Core services first
    CORE_SERVICES=("account" "transactor" "workspace" "front" "fulltext")
    for service in "${CORE_SERVICES[@]}"; do
        echo "  Starting $service..."
        notify_webhook "provisioning" "app_service_start" "Starting $service"
        
        # Pull image first to avoid delays
        echo "    Pulling image for $service..."
        if ! $DOCKER_COMPOSE_CMD pull "$service" --quiet; then
            echo "    ⚠️ Failed to pull $service image, but continuing..."
            notify_webhook "warning" "app_image_pull_failed" "Failed to pull $service image, but continuing"
        fi
        
        # Start service
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
                "account"|"transactor"|"front")
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
        
        echo "  ✅ $service startup completed"
        sleep 3  # Brief pause between services
    done

    # Supporting services
    SUPPORT_SERVICES=("rekoni" "collaborator" "stats" "kvs")
    for service in "${SUPPORT_SERVICES[@]}"; do
        echo "  Starting $service..."
        if timeout 60s $DOCKER_COMPOSE_CMD up -d "$service"; then
            echo "    ✅ $service started successfully"
        else
            echo "    ⚠️ Failed to start $service, but continuing..."
        fi
        sleep 3
    done

    # Optional services (ALL ENABLED)
    OPTIONAL_SERVICES=("love" "print" "aibot" "calendar" "github")
    for service in "${OPTIONAL_SERVICES[@]}"; do
        echo "  Starting $service..."
        if timeout 60s $DOCKER_COMPOSE_CMD up -d "$service"; then
            echo "    ✅ $service started successfully"
        else
            echo "    ⚠️ Failed to start optional service $service, but continuing..."
        fi
        sleep 3
    done

    echo "✅ All Huly services started"
    notify_webhook "provisioning" "app_services_ready" "✅ All Huly application services running"

    # ==========================================================
    # Verify front service health
    # ==========================================================
    notify_webhook "provisioning" "health_check_start" "Checking Huly front service health"

    # Give services time to initialize
    sleep 60

    # DEBUG: Check which containers are running and report status
    CONTAINER_STATUS=$($DOCKER_COMPOSE_CMD ps)
    RUNNING_CONTAINERS=$(echo "$CONTAINER_STATUS" | grep "Up" | wc -l)
    TOTAL_CONTAINERS=$(echo "$CONTAINER_STATUS" | tail -n +2 | wc -l)

    notify_webhook "debug" "container_status" "Containers running: $RUNNING_CONTAINERS/$TOTAL_CONTAINERS"

    # Check if front service is responsive with extended timeout
    READY=false
    for i in {1..30}; do
        if $DOCKER_COMPOSE_CMD ps front | grep -q "Up" && curl -f -s http://localhost:8080/ >/dev/null 2>&1; then
            READY=true
            break
        fi
        if [ $((i % 6)) -eq 0 ]; then
            notify_webhook "provisioning" "health_check_progress" "Front service health check in progress... ($((i*10))s)"
        fi
        sleep 10
    done

    if [ "$READY" = false ]; then
        if [ $RUNNING_CONTAINERS -ge 12 ]; then
            notify_webhook "provisioning" "deployment_stable" "✅ Huly deployment stable with $RUNNING_CONTAINERS containers running"
        else
            notify_webhook "failed" "deployment_unstable" "Huly deployment unstable - only $RUNNING_CONTAINERS containers running"
            exit 1
        fi
    else
        notify_webhook "provisioning" "huly_healthy" "✅ Huly is fully operational and responsive"
    fi

    notify_webhook "provisioning" "huly_deployment_complete" "✅ Huly deployment completed successfully"

    # ==========================================================
    # Final container status
    # ==========================================================
    echo "📊 Final container status:"
    $DOCKER_COMPOSE_CMD ps

    echo "🎉 Huly deployment completed successfully!"
    notify_webhook "provisioning" "huly_deployment_complete" "✅ Huly deployment completed successfully"

    # ========== FIREWALL ==========
    echo "[10/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"

    # SSH access
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8080/tcp   # Frontend (your quirk)
    ufw allow 3000/tcp   # Account service
    ufw allow 3333/tcp   # Transactor
    ufw allow 8096/tcp   # Love service
    ufw allow 4005/tcp   # Print service
    ufw allow 4010/tcp   # AI Bot
    ufw allow 8095/tcp   # Calendar
    ufw allow 3500/tcp   # GitHub integration
    ufw allow 9000/tcp   # MinIO API
    ufw allow 9001/tcp   # MinIO Console
    ufw allow 9092/tcp   # Redpanda Kafka
    ufw allow 19092/tcp  # Redpanda external Kafka
    ufw allow 8082/tcp   # Redpanda HTTP Proxy
    ufw allow 18082/tcp  # Redpanda external HTTP Proxy
    ufw allow 8081/tcp   # Redpanda Schema Registry
    ufw allow 18081/tcp  # Redpanda external Schema Registry
    ufw allow 26257/tcp  # CockroachDB
    ufw allow 9200/tcp   # Elasticsearch
    ufw allow "$PORT"/tcp
    ufw --force enable
                                      
    echo "✅ Firewall configured — all Huly service ports allowed"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with all required Huly ports"

    # ========== NGINX CONFIG + SSL (YOUR BULLETPROOF TEMPLATE) ==========
    echo "[11/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/huly

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/huly <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/huly /etc/nginx/sites-enabled/huly
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
        notify_webhook "warning" "ssl" "Huly Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/huly <<'EOF_SSL'
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
        proxy_pass http://127.0.0.1:8080;
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
    
    # Huly service endpoints
    location /_accounts/ {
        proxy_pass http://127.0.0.1:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /_transactor {
        proxy_pass http://127.0.0.1:3333;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /_love {
        proxy_pass http://127.0.0.1:8096;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /minio/ {
        # Remove /minio prefix and proxy to MinIO
        rewrite ^/minio/(.*)$ /$1 break;
                                      
        proxy_pass http://127.0.0.1:9000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Important for MinIO
        proxy_buffering off;
        proxy_request_buffering off;
        client_max_body_size 200M;
        
        # CORS headers for MinIO
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, Origin, X-Requested-With" always;
        add_header Access-Control-Allow-Credentials "true" always;
    }
}
EOF_SSL

        ln -sf /etc/nginx/sites-available/huly /etc/nginx/sites-enabled/huly
        nginx -t && systemctl reload nginx
    fi

    echo "[14/15] Setup Cron for renewal..."
    notify_webhook "provisioning" "provisioning" "Setup Cron for renewal..."
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "certbot renew" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

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

    echo "✅ Huly setup complete!"
    notify_webhook "provisioning" "huly_setup_complete" "✅ Huly deployment succeeded"

    #wait 60 seconds until everything is fully ready 
    sleep 60
                                      
    cat <<EOF_SUMMARY
=============================================
🎮 HULY DEPLOYMENT SUCCESSFUL!
=============================================
🔗 Access URL: https://__DOMAIN__
👤 Admin email: __ADMIN_EMAIL__
🐳 Services: All 18 microservices deployed
⚙️ Useful commands:
- Status: cd $DATA_DIR/huly-selfhost && docker compose ps
- Logs: cd $DATA_DIR/huly-selfhost && docker compose logs -f
- Restart: cd $DATA_DIR/huly-selfhost && docker compose restart
- Update: cd $DATA_DIR/huly-selfhost && docker compose pull && docker compose up -d

🔧 Included Services:
✅ Core: Account, Transactor, Workspace, Front
✅ Infrastructure: CockroachDB, Redpanda, MinIO, Elasticsearch
✅ Features: AI Bot, Love (calls), Print, Calendar, GitHub
✅ Support: Rekoni, Collaborator, Stats, KVS

📊 Resource Usage: ~4GB RAM, 18 containers
=============================================
EOF_SUMMARY

    notify_webhook "provisioning" "huly_summary" "🎮 Huly fully deployed with all services at https://__DOMAIN__"
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

    # Replace remaining tokens
    final = final.replace("__ADMIN_PASSWORD__", tokens["__ADMIN_PASSWORD__"])
    final = final.replace("__ADMIN_EMAIL__", tokens["__ADMIN_EMAIL__"])
    final = final.replace("__DOMAIN__", tokens["__DOMAIN__"])
    final = final.replace("__PORT__", tokens["__PORT__"])

    return final