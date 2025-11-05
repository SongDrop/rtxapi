import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL, 
    ADMIN_PASSWORD,
    WEB_PORT=8080,
    DAEMON_PORT=5657,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DATABASE_TYPE="mysql",  # Default to mysql now
    MYSQL_HOST="localhost",
    MYSQL_USER="pufferpanel", 
    MYSQL_PASSWORD="",  # Will auto-generate
    MYSQL_DATABASE="pufferpanel",
):
    """
    Returns a full 15-step PufferPanel provisioning script with all game server dependencies.
    """
    
    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__WEB_PORT__": str(WEB_PORT),
        "__DAEMON_PORT__": str(DAEMON_PORT),
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__PUFFERPANEL_DIR__": "/var/lib/pufferpanel",
        "__CONFIG_DIR__": "/etc/pufferpanel", 
        "__DATABASE_TYPE__": DATABASE_TYPE,
        "__MYSQL_HOST__": MYSQL_HOST,
        "__MYSQL_USER__": MYSQL_USER,
        "__MYSQL_PASSWORD__": MYSQL_PASSWORD,  # Will be generated in script
        "__MYSQL_DATABASE__": MYSQL_DATABASE,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
    }

    # ------------------ SCRIPT TEMPLATE ------------------
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # PufferPanel Provisioning Script 
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    # Enhanced error logging
    error_handler() {
        local exit_code=$?
        local line_number=$1
        echo "ERROR: Script failed at line $line_number with exit code $exit_code"
        notify_webhook "failed" "unexpected_error" "Script exited on line $line_number with code $exit_code"
        exit $exit_code
    }
    trap 'error_handler ${LINENO}' ERR
                                      
    # --- Logging ---
    LOG_FILE="/var/log/pufferpanel_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1
                                      
    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    WEB_PORT="__WEB_PORT__"
    DAEMON_PORT="__DAEMON_PORT__"
    PUFFERPANEL_DIR="__PUFFERPANEL_DIR__"
    CONFIG_DIR="__CONFIG_DIR__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    DATABASE_TYPE="__DATABASE_TYPE__"
    MYSQL_HOST="__MYSQL_HOST__"
    MYSQL_USER="__MYSQL_USER__"
    MYSQL_PASSWORD="__MYSQL_PASSWORD__"
    MYSQL_DATABASE="__MYSQL_DATABASE__"

    # Add missing variables
    READY_TIMEOUT=300
    SLEEP_INTERVAL=10

    echo "[1/15] Starting PufferPanel provisioning..."
    notify_webhook "provisioning" "starting" "Beginning PufferPanel setup"  

    # ==========================================================
    # 🔐 Generate Secure Credentials (Following your patterns)
    # ==========================================================
    echo "[2/15] Generating secure credentials..."
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

    # Generate MySQL password if empty
    if [ -z "$MYSQL_PASSWORD" ]; then
        MYSQL_PASSWORD=$(generate_secure_random "alphanumeric" 16)
    fi

    # Generate PufferPanel secret
    PUFFERPANEL_SECRET=$(generate_secure_random "hex" 32)

    echo "✅ Secure credentials generated"
    notify_webhook "provisioning" "credentials_ready" "MYSQL_USER: $MYSQL_USER, MYSQL_PASSWORD: $MYSQL_PASSWORD, PUFFERPANEL_SECRET: [hidden]"
    sleep 5

    # --- Input Validation ---
    echo "[3/15] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and ports"
   
    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "ERROR: Invalid domain format: $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain format: $DOMAIN"
        exit 1
    fi
    
    for port in "$WEB_PORT" "$DAEMON_PORT"; do
        if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
            echo "ERROR: Invalid port number: $port"
            notify_webhook "failed" "validation" "Invalid port: $port"
            exit 1
        fi
    done

    sleep 5
                                      
    # ==========================================================
    # Step 4: Install System Dependencies
    # ==========================================================
    echo "[4/15] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"

    # Set non-interactive mode for apt
    export DEBIAN_FRONTEND=noninteractive

    # ----------------------------------------------------------
    # Update package lists
    # ----------------------------------------------------------
    notify_webhook "provisioning" "apt_update" "Running apt-get update"
    if ! apt-get update -q; then
        notify_webhook "failed" "apt_update" "apt-get update failed"
        exit 1
    fi

    # ----------------------------------------------------------
    # Upgrade installed packages
    # ----------------------------------------------------------
    notify_webhook "provisioning" "apt_upgrade" "Running apt-get upgrade"
    if ! apt-get upgrade -y -q; then
        notify_webhook "failed" "apt_upgrade" "apt-get upgrade failed"
        exit 1
    fi

    # ----------------------------------------------------------
    # Ensure no locks block future operations
    # ----------------------------------------------------------
    sleep 3
    fuser -vki /var/lib/dpkg/lock-frontend || true
    dpkg --configure -a

    # ----------------------------------------------------------
    # Install ALL required packages (PHP, MySQL, Java, SteamCMD, etc.)
    # ----------------------------------------------------------
    notify_webhook "provisioning" "apt_install" "Installing ALL required packages"

    # Add PHP repository
    apt-get install -y -q software-properties-common
    add-apt-repository ppa:ondrej/php -y
    apt-get update -q

    # Add multiverse for SteamCMD
    add-apt-repository multiverse -y
    dpkg --add-architecture i386
    apt-get update -q

    # Install ALL packages
    REQUIRED_PACKAGES=(
        # Base system
        curl git nginx certbot python3-certbot-nginx python3-pip python3-venv jq make ufw xxd
        # PHP stack
        openssl php-fpm php-cli php-curl php-mysql
        # MySQL
        mysql-client mysql-server
        # Java for Minecraft
        openjdk-8-jre-headless
        # SteamCMD and dependencies
        lib32gcc1 steamcmd
        # Build tools
        build-essential
    )

    if ! apt-get install -y -q "${REQUIRED_PACKAGES[@]}"; then
        notify_webhook "failed" "apt_install" "Base package install failed"
        exit 1
    fi

    echo "✅ All system dependencies installed"
    notify_webhook "provisioning" "system_dependencies_success" "✅ All system dependencies installed successfully"
    sleep 5

    # ========== SECURE MYSQL INSTALLATION ==========
    echo "[5/15] Securing MySQL installation..."
    notify_webhook "provisioning" "mysql_secure" "Running mysql_secure_installation"

    # Start MySQL service
    systemctl start mysql
    systemctl enable mysql

    # Secure MySQL installation with generated password
    mysql --user=root <<-EOF
        ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_PASSWORD';
        DELETE FROM mysql.user WHERE User='';
        DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
        DROP DATABASE IF EXISTS test;
        DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
        FLUSH PRIVILEGES;
EOF

    # Create PufferPanel database and user
    mysql --user=root --password="$MYSQL_PASSWORD" <<-EOF
        CREATE DATABASE IF NOT EXISTS $MYSQL_DATABASE;
        CREATE USER IF NOT EXISTS '$MYSQL_USER'@'localhost' IDENTIFIED BY '$MYSQL_PASSWORD';
        GRANT ALL PRIVILEGES ON $MYSQL_DATABASE.* TO '$MYSQL_USER'@'localhost';
        FLUSH PRIVILEGES;
EOF

    echo "✅ MySQL secured and database created"
    notify_webhook "provisioning" "mysql_ready" "MySQL secured: MYSQL_USER: $MYSQL_USER, MYSQL_PASSWORD: $MYSQL_PASSWORD, MYSQL_DATABASE: $MYSQL_DATABASE"
    sleep 5

    # ========== DOCKER INSTALLATION ==========
    echo "[6/15] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"

    # Install prerequisites
    apt-get install -y -q ca-certificates curl gnupg lsb-release apt-transport-https || {
        echo "❌ Failed to install Docker prerequisites"
        notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
        exit 1
    }

    # Remove old versions (ignore errors)
    apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

    # Setup variables
    DOCKER_GPG_URL="https://download.docker.com/linux/ubuntu/gpg"
    DOCKER_KEYRING="/etc/apt/keyrings/docker.gpg"
    RETRY_MAX=3
    RETRY_DELAY=5

    mkdir -p /etc/apt/keyrings
    chmod a+r /etc/apt/keyrings || true

    # --- Download Docker GPG key with retries ---
    for attempt in $(seq 1 $RETRY_MAX); do
        echo "Downloading Docker GPG key (attempt $attempt/$RETRY_MAX)..."
        if curl -fsSL "$DOCKER_GPG_URL" | gpg --dearmor -o "$DOCKER_KEYRING"; then
            chmod a+r "$DOCKER_KEYRING"
            echo "✅ Docker GPG key downloaded successfully"
            break
        else
            echo "⚠️ Attempt $attempt failed to download Docker GPG key"
            notify_webhook "warning" "docker_gpg_retry" "Attempt $attempt to download Docker GPG key failed"
            sleep $RETRY_DELAY
            if [ $attempt -eq $RETRY_MAX ]; then
                echo "❌ Docker GPG key download failed after $RETRY_MAX attempts"
                notify_webhook "failed" "docker_gpg" "Failed to download Docker GPG key after retries"
                exit 1
            fi
        fi
    done

    # --- Add Docker repository ---
    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=$DOCKER_KEYRING] https://download.docker.com/linux/ubuntu $CODENAME stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # --- Update package list ---
    apt-get update -q || {
        echo "❌ Failed to update package list after adding Docker repo"
        notify_webhook "failed" "docker_repo" "Failed to update package list"
        exit 1
    }

    # --- Install Docker packages with retries ---
    DOCKER_PACKAGES=(docker-ce docker-ce-cli containerd.io docker-buildx-plugin)
    for attempt in $(seq 1 $RETRY_MAX); do
        echo "Installing Docker packages (attempt $attempt/$RETRY_MAX)..."
        if apt-get install -y -q "${DOCKER_PACKAGES[@]}"; then
            echo "✅ Docker installed successfully"
            break
        else
            echo "⚠️ Docker install attempt $attempt failed, retrying in $RETRY_DELAY seconds..."
            notify_webhook "warning" "docker_install_retry" "Attempt $attempt to install Docker failed"
            sleep $RETRY_DELAY
            if [ $attempt -eq $RETRY_MAX ]; then
                echo "❌ Docker installation failed after $RETRY_MAX attempts"
                notify_webhook "failed" "docker_install" "Docker install failed after retries"
                exit 1
            fi
        fi
    done

    # ========== DOCKER COMPOSE INSTALLATION ==========
    echo "[6.5/15] Installing Docker Compose..."
    notify_webhook "provisioning" "docker_compose_install" "Installing Docker Compose"
    
    # Try Docker Compose plugin first
    if apt-get install -y -q docker-compose-plugin; then
        echo "✅ Docker Compose plugin installed via apt"
    else
        echo "⚠️ Docker Compose plugin not available, installing via pip"
        pip3 install --upgrade pip || true
        if pip3 install docker-compose; then
            echo "✅ Docker Compose installed via pip"
        else
            echo "❌ Docker Compose installation failed via both apt and pip"
            notify_webhook "failed" "docker_compose" "Docker Compose install failed via both apt and pip"
            exit 1
        fi
    fi

    # Enable and start Docker
    systemctl enable docker
    if ! systemctl start docker; then
        echo "❌ Failed to start Docker service"
        journalctl -u docker --no-pager | tail -n 20
        notify_webhook "failed" "docker_service" "Failed to start Docker service"
        exit 1
    fi
    
    # Verify Docker works
    if ! docker info >/dev/null 2>&1; then
        echo "❌ Docker daemon did not start correctly"
        journalctl -u docker --no-pager | tail -n 30
        notify_webhook "failed" "docker_daemon" "Docker daemon failed to start"
        exit 1
    fi

    echo "✅ Docker installed and running"
    notify_webhook "provisioning" "docker_ready" "✅ Docker installed successfully"
    sleep 2

    # ========== STEAMCMD SETUP ==========
    echo "[7/15] Setting up SteamCMD..."
    notify_webhook "provisioning" "steamcmd_setup" "Configuring SteamCMD"

    # Create symbolic link for SteamCMD
    ln -sf /usr/games/steamcmd /usr/local/bin/steamcmd || true

    # Verify Java installation
    JAVA_VERSION=$(java -version 2>&1 | head -n 1)
    echo "Java version: $JAVA_VERSION"
    notify_webhook "provisioning" "java_ready" "Java installed: $JAVA_VERSION"

    echo "✅ SteamCMD and Java configured"
    notify_webhook "provisioning" "steamcmd_ready" "✅ SteamCMD and Java configured successfully"
    sleep 5

    # ========== PUFFERPANEL DIRECTORY SETUP ==========
    echo "[8/15] Creating PufferPanel directories..."
    notify_webhook "provisioning" "directories" "Creating PufferPanel directories"

    # Create all required directories
    mkdir -p "$PUFFERPANEL_DIR" "$CONFIG_DIR" "/var/log/pufferpanel" || {
        echo "ERROR: Failed to create PufferPanel directories"
        notify_webhook "failed" "directory_creation" "Failed to create PufferPanel directories"
        exit 1
    }
    
    # Set proper ownership
    chown -R 1000:1000 "$PUFFERPANEL_DIR" || true
    cd "$PUFFERPANEL_DIR"
    echo "✅ PufferPanel directories ready"
    notify_webhook "provisioning" "directory_ready" "✅ PufferPanel directories created successfully"
    
    sleep 5

    # ========== DOCKER COMPOSE CONFIGURATION ==========
    echo "[9/15] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose" "Creating docker-compose.yml"

    # Generate database URL based on type
    case "$DATABASE_TYPE" in
        "mysql")
            DATABASE_URL="mysql://$MYSQL_USER:$MYSQL_PASSWORD@$MYSQL_HOST:3306/$MYSQL_DATABASE"
            ;;
        "postgres")
            DATABASE_URL="postgres://$MYSQL_USER:$MYSQL_PASSWORD@$MYSQL_HOST:5432/$MYSQL_DATABASE"
            ;;
        *)
            DATABASE_URL="file:$PUFFERPANEL_DIR/database.db?cache=shared"
            ;;
    esac

    cat > "$PUFFERPANEL_DIR/docker-compose.yml" <<EOF
version: "3.8"

services:
  pufferpanel:
    image: pufferpanel/pufferpanel:latest
    container_name: pufferpanel
    restart: unless-stopped
    ports:
      - "$WEB_PORT:8080"
      - "$DAEMON_PORT:5657"
    environment:
      - PUFFERPANEL_SECRET=$PUFFERPANEL_SECRET
      - DATABASE_URL=$DATABASE_URL
      - PUFFERPANEL_DOCKER_ROOT=/var/lib/docker
    volumes:
      - $PUFFERPANEL_DIR:/var/lib/pufferpanel
      - $CONFIG_DIR:/etc/pufferpanel
      - /var/run/docker.sock:/var/run/docker.sock
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

    echo "✅ Docker Compose configuration created"
    notify_webhook "provisioning" "docker_compose_ready" "✅ Docker Compose configuration created"
    sleep 5

    # ========== FIREWALL CONFIGURATION ==========
    echo "[10/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"

    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow "$WEB_PORT"/tcp
    ufw allow "$DAEMON_PORT"/tcp
    ufw --force enable

    UFW_STATUS=$(ufw status verbose 2>/dev/null || echo "ufw not present")
    UFW_STATUS_ESCAPED=$(echo "$UFW_STATUS" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
    notify_webhook "provisioning" "firewall_status" "UFW status:\\n$UFW_STATUS_ESCAPED"

    echo "✅ Firewall configured"
    notify_webhook "provisioning" "firewall_ready" "✅ Firewall configured successfully"
    sleep 5

    # ========== START PUFFERPANEL CONTAINER ==========
    echo "[11/15] Starting PufferPanel container..."
    notify_webhook "provisioning" "container_start" "Starting PufferPanel container"

    cd "$PUFFERPANEL_DIR"

    # Determine docker-compose command
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        echo "ERROR: Neither docker compose nor docker-compose available"
        notify_webhook "failed" "container_start" "Docker compose not available"
        exit 1
    fi

    # Pull & start container
    $COMPOSE_CMD pull || echo "Warning: Image pull failed, will try to run anyway"
    $COMPOSE_CMD up -d

    # Wait for container to initialize
    echo "Waiting for container to initialize..."
    sleep 10

    # Collect diagnostics
    DOCKER_PS_OUTPUT=$(docker ps -a --no-trunc 2>/dev/null || echo "docker ps failed")
    SHORT_PS=$(echo "$DOCKER_PS_OUTPUT" | grep -i pufferpanel || echo "$DOCKER_PS_OUTPUT" | head -n 20)
    SHORT_PS_ESCAPED=$(echo "$SHORT_PS" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
    notify_webhook "provisioning" "docker_ps" "=== docker ps output ===\\n$SHORT_PS_ESCAPED"

    # Check container status
    CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' pufferpanel 2>/dev/null || echo "nonexistent")
    echo "Container status: $CONTAINER_STATUS"

    if [ "$CONTAINER_STATUS" != "running" ]; then
        # Send additional diagnostics
        LOG_TAIL=$(docker logs pufferpanel --tail 100 2>/dev/null || echo "no logs")
        LOG_ESCAPED=$(echo "$LOG_TAIL" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
        notify_webhook "provisioning" "docker_logs" "=== container logs (last 100 lines) ===\\n$LOG_ESCAPED"

        echo "❌ PufferPanel container is not running. Status: $CONTAINER_STATUS"
        notify_webhook "failed" "container_start" "PufferPanel failed to start (status: $CONTAINER_STATUS)"
        exit 1
    fi

    echo "✅ PufferPanel container is running"
    notify_webhook "provisioning" "container_running" "✅ PufferPanel container running successfully"
    sleep 5

    # ========== WAIT FOR READINESS ==========
    echo "[12/15] Waiting for PufferPanel readiness..."
    notify_webhook "provisioning" "http_probe" "Waiting for HTTP readiness"

    elapsed=0
    READY=false

    while [ $elapsed -lt $READY_TIMEOUT ]; do
        if [ "$(docker inspect -f '{{.State.Status}}' pufferpanel 2>/dev/null)" != "running" ]; then
            echo "❌ Container stopped during startup"
            docker logs pufferpanel 2>/dev/null || true
            break
        fi

        # Test HTTP connectivity
        HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$WEB_PORT" || echo "000")
        
        if [ "$HTTP_RESPONSE" = "200" ] || [ "$HTTP_RESPONSE" = "302" ]; then
            echo "✅ PufferPanel is responding (HTTP $HTTP_RESPONSE)"
            READY=true
            break
        fi

        echo "⏳ Waiting for PufferPanel... (HTTP: $HTTP_RESPONSE, elapsed: ${elapsed}s)"

        if [ $((elapsed % 30)) -eq 0 ]; then
            docker logs pufferpanel --since "1m ago" 2>/dev/null | tail -5 || echo "No recent logs"
        fi

        sleep $SLEEP_INTERVAL
        elapsed=$((elapsed + SLEEP_INTERVAL))
    done

    if [ "$READY" = false ]; then
        notify_webhook "failed" "http_probe" "PufferPanel not responding after $READY_TIMEOUT seconds"
        exit 1
    fi

    echo "✅ PufferPanel is ready and responding"
    notify_webhook "provisioning" "http_ready" "✅ PufferPanel HTTP probe successful"
    sleep 5

    # ========== NGINX + SSL CONFIGURATION ==========
    echo "[13/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL"

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/pufferpanel

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/pufferpanel <<EOF_TEMP
server {
    listen 80;
    server_name $DOMAIN;
    root /var/www/html;

    location / {
        return 200 'Certbot validation ready';
        add_header Content-Type text/plain;
    }
}
EOF_TEMP

    ln -sf /etc/nginx/sites-available/pufferpanel /etc/nginx/sites-enabled/pufferpanel
    nginx -t && systemctl restart nginx

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html

    # Attempt to obtain SSL certificate
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL"; then
        echo "✅ SSL certificate obtained"
        notify_webhook "provisioning" "ssl_success" "✅ SSL certificate obtained for $DOMAIN"

        # Replace with HTTPS config
        cat > /etc/nginx/sites-available/pufferpanel <<EOF_SSL
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

    client_max_body_size 256M;

    location / {
        proxy_pass http://127.0.0.1:$WEB_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
EOF_SSL

        ln -sf /etc/nginx/sites-available/pufferpanel /etc/nginx/sites-enabled/pufferpanel
        nginx -t && systemctl reload nginx
    else
        echo "⚠️ SSL certificate not obtained, continuing without HTTPS"
        notify_webhook "warning" "ssl_failed" "SSL certificate not obtained for $DOMAIN"
    fi

    # Setup SSL renewal cron
    (crontab -l 2>/dev/null | grep -v -F "certbot renew" || true; \
    echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    echo "✅ Nginx configuration complete"
    notify_webhook "provisioning" "nginx_ready" "✅ Nginx configuration complete"
    sleep 5

    # ========== FINAL VERIFICATION ==========
    echo "[14/15] Final verification..."
    notify_webhook "provisioning" "verification" "Performing final verification checks"

    # Verify services
    if ! nginx -t; then
        echo "ERROR: nginx config test failed"
        notify_webhook "failed" "verification" "Nginx config test failed"
        exit 1
    fi

    if ! docker ps | grep -q pufferpanel; then
        echo "❌ PufferPanel container is not running"
        notify_webhook "failed" "verification" "PufferPanel container not running"
        exit 1
    fi

    # Test HTTPS if SSL is configured
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN" || echo "000")
        echo "HTTPS check returned: $HTTPS_RESPONSE"
        if [ "$HTTPS_RESPONSE" = "200" ] || [ "$HTTPS_RESPONSE" = "302" ]; then
            notify_webhook "provisioning" "https_ready" "HTTPS accessible: $HTTPS_RESPONSE"
        else
            notify_webhook "warning" "https_check" "HTTPS check returned $HTTPS_RESPONSE"
        fi
    fi

    echo "✅ All verification checks passed"
    notify_webhook "provisioning" "verification_success" "✅ All verification checks passed"
    sleep 5

    # ========== COMPLETION ==========
    echo "[15/15] PufferPanel provisioning complete!"
    notify_webhook "provisioning" "pufferpanel_installed" "✅ PufferPanel setup completed successfully"

    # Final summary
    cat <<EOF

    🎉 PufferPanel Installation Complete!
    ========================================

    📊 Access Information:
    • Web Panel: https://$DOMAIN (or http://$DOMAIN:$WEB_PORT)
    • Daemon Port: $DAEMON_PORT

    🔐 Credentials:
    • MySQL User: $MYSQL_USER
    • MySQL Password: $MYSQL_PASSWORD
    • MySQL Database: $MYSQL_DATABASE

    🛠️ Services Installed:
    • PufferPanel (Docker)
    • MySQL Database
    • Nginx + SSL
    • Java 8 (Minecraft)
    • SteamCMD (Steam games)
    • PHP + Required extensions

    📝 Next Steps:
    1. Access https://$DOMAIN in your browser
    2. Create your admin account
    3. Start adding game servers!

    🔧 Management Commands:
    • Stop: cd $PUFFERPANEL_DIR && docker-compose down
    • Start: cd $PUFFERPANEL_DIR && docker-compose up -d
    • Logs: docker logs -f pufferpanel

    ========================================
EOF

    sleep 10
""")

    # ------------------ WEBHOOK FUNCTION HANDLING ------------------
    if tokens["__WEBHOOK_URL__"]:
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
                curl -s -X POST "__WEBHOOK_URL__" \
                    -H "Content-Type: application/json" \
                    -d "$JSON_PAYLOAD" \
                    --retry 2 --retry-delay 5 --connect-timeout 10 --max-time 30 || true
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

    return final