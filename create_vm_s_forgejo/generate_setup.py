import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
    WEBHOOK_URL="",
    ALLOW_EMBED_WEBSITE="",
    location="",
    resource_group=""
):
    """
    Returns a full bash provisioning script for Forgejo with enhanced error handling.
    """
    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__ALLOW_EMBED_WEBSITE__": ALLOW_EMBED_WEBSITE,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__FORGEJO_DIR__": "/opt/forgejo",
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__MAX_UPLOAD_SIZE_MB__": "1024",
        "__MAX_UPLOAD_SIZE_BYTES__": str(1024 * 1024 * 1024),
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Forgejo Provisioning Script (generated)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    # Error handling with webhook notifications
    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging Setup ---
    LOG_FILE="/var/log/forgejo_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    PORT="__PORT__"
    FORGEJO_DIR="__FORGEJO_DIR__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    ALLOW_EMBED_WEBSITE="__ALLOW_EMBED_WEBSITE__"
    MAX_UPLOAD_SIZE_MB="__MAX_UPLOAD_SIZE_MB__"
    MAX_UPLOAD_SIZE_BYTES="__MAX_UPLOAD_SIZE_BYTES__"

    # Generate LFS JWT secret
    LFS_JWT_SECRET=$(openssl rand -hex 32)
    notify_webhook "provisioning" "lfs_secret_generated" "LFS JWT secret generated"

    echo "[1/15] Starting Forgejo provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Forgejo setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/15] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and inputs"

    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "ERROR: Invalid domain format: $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain format: $DOMAIN"
        exit 1
    fi

    if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
        echo "ERROR: Invalid port number: $PORT (must be 1024-65535)"
        notify_webhook "failed" "validation" "Invalid port: $PORT"
        exit 1
    fi

    notify_webhook "provisioning" "validation_complete" "Input validation completed successfully"

    # ========== SYSTEM DEPENDENCIES ==========
    echo "[3/15] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"

    export DEBIAN_FRONTEND=noninteractive
    
    # Update package lists with retry logic
    echo "Updating package lists..."
    notify_webhook "provisioning" "package_update" "Updating package lists"
    for i in {1..3}; do
        if apt-get update -q; then
            notify_webhook "provisioning" "package_update_success" "Package lists updated successfully"
            break
        fi
        echo "Package update attempt $i failed, retrying in 5 seconds..."
        notify_webhook "warning" "package_update_retry" "Package update attempt $i failed, retrying"
        sleep 5
    done

    # Upgrade system with error handling
    echo "Upgrading system packages..."
    notify_webhook "provisioning" "system_upgrade" "Upgrading system packages"
    if ! apt-get upgrade -y -q; then
        echo "WARNING: System upgrade had issues, continuing anyway..."
        notify_webhook "warning" "upgrade_issues" "System upgrade encountered issues"
    else
        notify_webhook "provisioning" "upgrade_complete" "System upgrade completed"

    # Install packages with individual error handling
    echo "Installing required packages..."
    notify_webhook "provisioning" "package_installation" "Installing required packages"
    PACKAGES=(
        curl git nginx certbot python3-pip python3-venv jq
        make net-tools openssl ufw
    )

    for package in "${PACKAGES[@]}"; do
        echo "Installing $package..."
        if ! apt-get install -y -q "$package"; then
            echo "WARNING: Failed to install $package, attempting to continue..."
            notify_webhook "warning" "package_install" "Failed to install $package"
        else
            notify_webhook "provisioning" "package_installed" "Successfully installed $package"
        fi
    done

    # Install git-lfs separately with better error handling
    echo "Installing git-lfs..."
    notify_webhook "provisioning" "git_lfs_install" "Installing git-lfs"
    if ! apt-get install -y -q git-lfs; then
        echo "WARNING: git-lfs not available in main repos, trying alternative..."
        notify_webhook "warning" "git_lfs_fallback" "git-lfs not in main repos, trying alternative"
        # Try alternative installation method for git-lfs
        curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash
        apt-get install -y -q git-lfs || {
            echo "ERROR: Failed to install git-lfs"
            notify_webhook "failed" "git_lfs_install" "Failed to install git-lfs"
            exit 1
        }
        notify_webhook "provisioning" "git_lfs_success" "git-lfs installed via alternative method"
    else
        notify_webhook "provisioning" "git_lfs_success" "git-lfs installed successfully"

    # Install python3-certbot-nginx separately
    echo "Installing python3-certbot-nginx..."
    notify_webhook "provisioning" "certbot_nginx_install" "Installing python3-certbot-nginx"
    if ! apt-get install -y -q python3-certbot-nginx; then
        echo "WARNING: python3-certbot-nginx installation failed, certbot may not work with nginx"
        notify_webhook "warning" "certbot_nginx" "Failed to install python3-certbot-nginx"
    else
        notify_webhook "provisioning" "certbot_nginx_success" "python3-certbot-nginx installed"

    # Initialize git LFS
    notify_webhook "provisioning" "git_lfs_init" "Initializing git LFS"
    if command -v git-lfs >/dev/null 2>&1; then
        git lfs install
        notify_webhook "provisioning" "git_lfs_initialized" "git LFS initialized successfully"
    else
        echo "WARNING: git-lfs not available, LFS support disabled"
        notify_webhook "warning" "git_lfs_missing" "git-lfs not available"

    echo "✅ System dependencies installed successfully"
    notify_webhook "provisioning" "dependencies_ready" "System dependencies installed"

    # ========== DOCKER INSTALLATION ==========
    echo "[4/15] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"

    # Clean up any existing Docker installations
    notify_webhook "provisioning" "docker_cleanup" "Cleaning up existing Docker installations"
    apt-get remove -y docker docker-engine docker.io containerd runc || true

    # Add Docker's official GPG key with retry logic
    echo "Adding Docker GPG key..."
    notify_webhook "provisioning" "docker_gpg" "Adding Docker GPG key"
    for i in {1..3}; do
        if curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; then
            notify_webhook "provisioning" "docker_gpg_success" "Docker GPG key added successfully"
            break
        fi
        echo "Docker GPG key download attempt $i failed, retrying in 5 seconds..."
        notify_webhook "warning" "docker_gpg_retry" "Docker GPG key download attempt $i failed, retrying"
        sleep 5
    done

    chmod a+r /etc/apt/keyrings/docker.gpg
    notify_webhook "provisioning" "docker_gpg_permissions" "Docker GPG key permissions set"

    # Add Docker repository
    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list
    notify_webhook "provisioning" "docker_repo_added" "Docker repository added"

    # Update with Docker repository
    apt-get update -q
    notify_webhook "provisioning" "docker_repo_updated" "Package lists updated with Docker repo"

    # Install Docker packages
    DOCKER_PACKAGES=(
        docker-ce
        docker-ce-cli 
        containerd.io
        docker-buildx-plugin
        docker-compose-plugin
    )

    for package in "${DOCKER_PACKAGES[@]}"; do
        echo "Installing $package..."
        notify_webhook "provisioning" "docker_package_install" "Installing Docker package: $package"
        if ! apt-get install -y -q "$package"; then
            echo "ERROR: Failed to install Docker package: $package"
            notify_webhook "failed" "docker_install" "Failed to install $package"
            exit 1
        else
            notify_webhook "provisioning" "docker_package_success" "Successfully installed $package"
        fi
    done

    # Add current user to docker group
    CURRENT_USER=$(whoami)
    if [ "$CURRENT_USER" != "root" ]; then
        usermod -aG docker "$CURRENT_USER" || echo "WARNING: Could not add user to docker group"
        notify_webhook "provisioning" "docker_group_added" "User $CURRENT_USER added to docker group"
    fi

    # Start and enable Docker
    notify_webhook "provisioning" "docker_service_setup" "Setting up Docker service"
    systemctl enable docker
    if ! systemctl start docker; then
        echo "ERROR: Failed to start Docker service"
        notify_webhook "failed" "docker_start" "Failed to start Docker service"
        exit 1
    fi
    notify_webhook "provisioning" "docker_service_started" "Docker service started successfully"

    # Wait for Docker to be ready
    echo "[5/15] Waiting for Docker to start..."
    notify_webhook "provisioning" "docker_wait" "Waiting for Docker daemon"
    
    timeout=180
    while [ $timeout -gt 0 ]; do
        if docker info >/dev/null 2>&1; then
            notify_webhook "provisioning" "docker_ready" "Docker daemon is ready"
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done

    if [ $timeout -eq 0 ]; then
        echo "ERROR: Docker daemon failed to start"
        notify_webhook "failed" "docker_timeout" "Docker daemon startup timeout"
        exit 1
    fi

    echo "✅ Docker installed and running"
    notify_webhook "provisioning" "docker_ready" "Docker installed successfully"

    # ========== FORGEJO DIRECTORY SETUP ==========
    echo "[6/15] Setting up Forgejo directories..."
    notify_webhook "provisioning" "directory_setup" "Creating Forgejo directory structure"

    mkdir -p "$FORGEJO_DIR"/{data,config,ssl,data/gitea/lfs} || {
        echo "ERROR: Failed to create Forgejo directories"
        notify_webhook "failed" "directory_creation" "Failed to create Forgejo directories"
        exit 1
    }
    notify_webhook "provisioning" "directories_created" "Forgejo directories created successfully"

    chown -R 1000:1000 "$FORGEJO_DIR"/data "$FORGEJO_DIR"/config "$FORGEJO_DIR"/data/gitea
    notify_webhook "provisioning" "directory_permissions" "Directory permissions set"

    # ========== DOCKER COMPOSE CONFIGURATION ==========
    echo "[7/15] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose" "Configuring Docker Compose"

    cat > "$FORGEJO_DIR/docker-compose.yml" <<EOF
version: "3.8"
services:
  server:
    image: codeberg.org/forgejo/forgejo:latest
    container_name: forgejo
    restart: unless-stopped
    environment:
      - FORGEJO__server__DOMAIN=$DOMAIN
      - FORGEJO__server__ROOT_URL=https://$DOMAIN
      - FORGEJO__server__HTTP_PORT=3000
      - FORGEJO__server__LFS_START_SERVER=true
      - FORGEJO__server__LFS_CONTENT_PATH=/data/gitea/lfs
      - FORGEJO__server__LFS_JWT_SECRET=$LFS_JWT_SECRET
      - FORGEJO__server__LFS_MAX_FILE_SIZE=$MAX_UPLOAD_SIZE_BYTES
    volumes:
      - ./data:/data
      - ./config:/etc/gitea
      - ./ssl:/ssl
    ports:
      - "$PORT:3000"
      - "222:22"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 15s
      timeout: 10s
      retries: 40
EOF

    notify_webhook "provisioning" "docker_compose_created" "Docker Compose file created"

    # ========== FIREWALL CONFIGURATION ==========
    echo "[8/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW firewall"

    # Check if UFW is already active
    if ufw status | grep -q "Status: active"; then
        echo "UFW already active, adding rules..."
        notify_webhook "provisioning" "ufw_active" "UFW already active, adding rules"
    else
        echo "Enabling UFW..."
        notify_webhook "provisioning" "ufw_enabling" "Enabling UFW firewall"
    fi

    ufw allow 22/tcp comment "SSH" || echo "WARNING: Could not add SSH rule"
    notify_webhook "provisioning" "firewall_ssh" "SSH firewall rule added"
    ufw allow 80/tcp comment "HTTP" || echo "WARNING: Could not add HTTP rule"
    notify_webhook "provisioning" "firewall_http" "HTTP firewall rule added"
    ufw allow 443/tcp comment "HTTPS" || echo "WARNING: Could not add HTTPS rule"
    notify_webhook "provisioning" "firewall_https" "HTTPS firewall rule added"
    ufw allow "$PORT"/tcp comment "Forgejo" || echo "WARNING: Could not add Forgejo port rule"
    notify_webhook "provisioning" "firewall_forgejo" "Forgejo port firewall rule added"
    
    if ! ufw --force enable; then
        echo "WARNING: Failed to enable UFW, continuing without firewall..."
        notify_webhook "warning" "firewall_failed" "Failed to enable UFW firewall"
    else
        notify_webhook "provisioning" "firewall_enabled" "UFW firewall enabled successfully"

    # ========== SSL CERTIFICATE SETUP ==========
    echo "[9/15] Setting up SSL certificates..."
    notify_webhook "provisioning" "ssl_setup" "Configuring SSL certificates"

    # Download recommended SSL configuration
    mkdir -p /etc/letsencrypt
    notify_webhook "provisioning" "ssl_download" "Downloading SSL configuration"                      
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf || echo "WARNING: Failed to download SSL options"
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem || echo "WARNING: Failed to download SSL dhparams"
    notify_webhook "provisioning" "ssl_config_downloaded" "SSL configuration files downloaded"

    # Certificate issuance function
    issue_certificate() {
        echo "Attempting to issue SSL certificate..."
        
        if [ -f "$DNS_HOOK_SCRIPT" ]; then
            echo "Using DNS hook script for certificate validation"
            notify_webhook "provisioning" "ssl_dns_hook" "Using DNS hook script for certificate validation"
            chmod +x "$DNS_HOOK_SCRIPT"
            certbot certonly --manual --preferred-challenges=dns \
                --manual-auth-hook "$DNS_HOOK_SCRIPT add" \
                --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" \
                --agree-tos --email "$ADMIN_EMAIL" -d "$DOMAIN" -d "*.$DOMAIN" \
                --non-interactive --manual-public-ip-logging-ok || return 1
        else
            echo "Using standalone method for certificate validation"
            notify_webhook "provisioning" "ssl_standalone" "Using standalone method for certificate validation"
            systemctl stop nginx || true
            # Try production first, then staging as fallback
            if certbot certonly --standalone --preferred-challenges http \
                --agree-tos --email "$ADMIN_EMAIL" -d "$DOMAIN" --non-interactive; then
                systemctl start nginx || true
                return 0
            else
                echo "Production cert failed, trying staging..."
                notify_webhook "warning" "ssl_production_failed" "Production certificate failed, trying staging"
                if certbot certonly --standalone --preferred-challenges http \
                    --staging --agree-tos --email "$ADMIN_EMAIL" -d "$DOMAIN" --non-interactive; then
                    systemctl start nginx || true
                    return 0
                else
                    systemctl start nginx || true
                    return 1
                fi
            fi
        fi
        return 0
    }

    # Retry certificate issuance
    retries=3
    success=false
    for i in $(seq 1 $retries); do
        echo "Certificate attempt $i of $retries..."
        notify_webhook "provisioning" "ssl_attempt" "Starting SSL certificate attempt $i of $retries"
        if issue_certificate; then
            echo "✅ SSL certificate issued successfully"
            notify_webhook "provisioning" "ssl_success" "SSL certificate issued successfully"
            success=true
            break
        else
            echo "Attempt $i failed; retrying in 30 seconds..."
            notify_webhook "warning" "ssl_retry" "SSL certificate attempt $i failed, retrying"
            sleep 30
        fi
    done

    if [ "$success" = false ]; then
        echo "ERROR: Failed to obtain SSL certificate after $retries attempts"
        notify_webhook "failed" "ssl_failed" "Certbot failed after $retries attempts"
        exit 1
    fi

    # ========== NGINX CONFIGURATION ==========
    echo "[10/15] Configuring nginx reverse proxy..."
    notify_webhook "provisioning" "nginx_setup" "Setting up nginx reverse proxy"

    # Remove default nginx configurations
    rm -f /etc/nginx/sites-enabled/default || true
    rm -f /etc/nginx/sites-available/default || true
    rm -f /etc/nginx/conf.d/*.conf || true
    notify_webhook "provisioning" "nginx_cleanup" "Default nginx configurations removed"

    # Create Forgejo nginx configuration
    cat > /etc/nginx/sites-available/forgejo <<'NGINX_EOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

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
    
    client_max_body_size __MAX_UPLOAD_SIZE_MB__M;
    
    location / {
        proxy_pass http://localhost:__PORT__;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        
        # Content Security Policy for embedded websites
        add_header Content-Security-Policy "frame-ancestors 'self' __ALLOW_EMBED_WEBSITE__" always;
    }
}
NGINX_EOF

    notify_webhook "provisioning" "nginx_config_created" "Nginx configuration file created"

    # Enable site and test configuration
    ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/ || {
        echo "ERROR: Failed to enable nginx site"
        notify_webhook "failed" "nginx_enable" "Failed to enable nginx site"
        exit 1
    }
    notify_webhook "provisioning" "nginx_site_enabled" "Nginx site enabled"

    if ! nginx -t; then
        echo "ERROR: nginx configuration test failed"
        notify_webhook "failed" "nginx_test" "nginx configuration test failed"
        exit 1
    fi
    notify_webhook "provisioning" "nginx_test_passed" "Nginx configuration test passed"

    if ! systemctl restart nginx; then
        echo "ERROR: Failed to restart nginx"
        notify_webhook "failed" "nginx_restart" "Failed to restart nginx"
        exit 1
    fi
    notify_webhook "provisioning" "nginx_restarted" "Nginx restarted successfully"

    # ========== FORGEJO CONTAINER STARTUP ==========
    echo "[11/15] Starting Forgejo container..."
    notify_webhook "provisioning" "forgejo_start" "Starting Forgejo container"

    cd "$FORGEJO_DIR" || {
        echo "ERROR: Cannot change to Forgejo directory"
        notify_webhook "failed" "directory_access" "Cannot access $FORGEJO_DIR"
        exit 1
    }

    # Pull latest Forgejo image
    notify_webhook "provisioning" "image_pull" "Pulling latest Forgejo image"
    if ! docker compose pull; then
        echo "WARNING: Failed to pull latest image, using local if available"
        notify_webhook "warning" "image_pull" "Failed to pull latest Forgejo image"
    else
        notify_webhook "provisioning" "image_pulled" "Forgejo image pulled successfully"

    # Start services
    notify_webhook "provisioning" "container_start" "Starting Forgejo container"
    if ! docker compose up -d; then
        echo "ERROR: Failed to start Forgejo container"
        notify_webhook "failed" "container_start" "Failed to start Forgejo container"
        exit 1
    fi
    notify_webhook "provisioning" "container_started" "Forgejo container started successfully"

    # ========== CONTAINER HEALTH CHECK ==========
    echo "[12/15] Waiting for Forgejo to become healthy..."
    notify_webhook "provisioning" "health_check" "Checking container health"

    timeout=180
    while [ $timeout -gt 0 ]; do
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' forgejo 2>/dev/null || echo "none")
        if [ "$HEALTH" = "healthy" ]; then
            echo "✅ Forgejo container is healthy"
            notify_webhook "provisioning" "container_healthy" "Forgejo container is healthy"
            break
        fi
        echo "Container status: $HEALTH (waiting...)"
        sleep 5
        timeout=$((timeout - 5))
    done

    if [ $timeout -eq 0 ]; then
        echo "WARNING: Forgejo container did not become healthy within timeout"
        notify_webhook "warning" "health_timeout" "Forgejo health check timeout"
        # Continue anyway as the container might still be starting
    fi

    # ========== FINAL NGINX RESTART ==========
    echo "[13/15] Finalizing nginx configuration..."
    notify_webhook "provisioning" "nginx_final" "Restarting nginx with final config"

    nginx -t && systemctl restart nginx || echo "WARNING: nginx restart failed"
    notify_webhook "provisioning" "nginx_final_restart" "Nginx final restart completed"

    # ========== FINAL CHECKS ==========
    echo "[14/15] Performing final verification..."
    notify_webhook "provisioning" "verification" "Running final checks"

    # Check if Forgejo is responding
    sleep 10
    if curl -s -f "https://$DOMAIN" > /dev/null; then
        echo "✅ Forgejo is responding via HTTPS"
        notify_webhook "success" "https_check" "HTTPS access verified"
    else
        echo "WARNING: Could not verify HTTPS access to Forgejo"
        notify_webhook "warning" "https_warning" "HTTPS check failed"
    fi

    notify_webhook "provisioning" "verification_complete" "Final verification completed"

    # ========== COMPLETION MESSAGE ==========
    echo "[15/15] Forgejo setup complete!"
    notify_webhook "success" "complete" "Forgejo provisioning completed successfully"

    cat <<EOF_FINAL
=============================================
✅ Forgejo Setup Complete!
---------------------------------------------
🔗 Access URL: https://__DOMAIN__
👤 Admin email: __ADMIN_EMAIL__
🔒 Default password: __ADMIN_PASSWORD__
---------------------------------------------
⚙️ Useful commands:
- Check status: cd $FORGEJO_DIR && docker compose ps
- View logs: cd $FORGEJO_DIR && docker compose logs -f
- Restart: cd $FORGEJO_DIR && docker compose restart
- Update: cd $FORGEJO_DIR && docker compose pull && docker compose up -d
---------------------------------------------
📝 Post-installation steps:
1. Visit https://__DOMAIN__ to complete setup
2. Change the default admin password immediately
3. Configure your repository settings
4. Set up backup procedures
---------------------------------------------
Enjoy your new Forgejo instance!
=============================================
EOF_FINAL
    """)

    # ========== WEBHOOK FUNCTION HANDLING ==========
    if tokens["__WEBHOOK_URL__"]:
        webhook_fn = textwrap.dedent(r"""
        notify_webhook() {
            local status="$1"
            local step="$2"
            local message="$3"

            # Build JSON payload
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

            # Send webhook with retry logic
            curl -s -X POST "__WEBHOOK_URL__" \
                -H "Content-Type: application/json" \
                -d "$JSON_PAYLOAD" \
                --connect-timeout 10 \
                --max-time 30 \
                --retry 2 \
                --retry-delay 5 \
                --write-out "Webhook HTTP status: %{http_code}\n" \
                --output /dev/null || true
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
    final_script = script_template.replace("__WEBHOOK_FUNCTION__", webhook_fn)

    # Replace all other tokens
    for token, value in tokens.items():
        final_script = final_script.replace(token, value)

    # Replace webhook-specific tokens in the webhook function
    final_script = final_script.replace("__LOCATION__", tokens["__LOCATION__"])
    final_script = final_script.replace("__RESOURCE_GROUP__", tokens["__RESOURCE_GROUP__"])
    final_script = final_script.replace("__WEBHOOK_URL__", tokens["__WEBHOOK_URL__"])

    # Replace SSL configuration URLs
    final_script = final_script.replace("__LET_OPTIONS_URL__", tokens["__LET_OPTIONS_URL__"])
    final_script = final_script.replace("__SSL_DHPARAMS_URL__", tokens["__SSL_DHPARAMS_URL__"])

    return final_script