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
    Returns a full bash provisioning script for Forgejo using template method.
    Usage: script = generate_setup("example.com", "admin@example.com", "P@ssw0rd", "8080", ...)
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
        "__MAX_UPLOAD_SIZE_BYTES__": str(1024 * 1024 * 1024),  # 1GB in bytes
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

    # ========== SYSTEM DEPENDENCIES ==========
    echo "[3/15] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"

    export DEBIAN_FRONTEND=noninteractive

    notify_webhook "provisioning" "apt_update" "Running apt-get update"
    apt-get update -q || { notify_webhook "failed" "apt_update" "apt-get update failed"; exit 1; }

    notify_webhook "provisioning" "apt_upgrade" "Running apt-get upgrade"
    apt-get upgrade -y -q || { notify_webhook "failed" "apt_upgrade" "apt-get upgrade failed"; exit 1; }

    notify_webhook "provisioning" "apt_install" "Installing required packages"
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq \
        make net-tools python3-certbot-nginx openssl ufw || { notify_webhook "failed" "apt_install" "apt-get install failed"; exit 1; }

    # ========== GIT LFS INSTALLATION ==========
    notify_webhook "provisioning" "git_lfs_install" "Installing git-lfs"
    sleep 5

    if ! command -v git-lfs >/dev/null 2>&1; then
        notify_webhook "provisioning" "git_lfs_install" "git-lfs not found, installing from packagecloud"
        sleep 5
        curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash || {
            notify_webhook "failed" "git_lfs_install" "Failed to add git-lfs repository"
            exit 1
        }
        apt-get update -q || { 
            notify_webhook "failed" "apt_update" "apt-get update failed during git-lfs install"
            exit 1
        }
        apt-get install -y git-lfs || { 
            notify_webhook "failed" "git_lfs_install" "apt-get install git-lfs failed"
            exit 1
        }
        notify_webhook "provisioning" "git_lfs_install" "git-lfs installed successfully"
    else
        notify_webhook "provisioning" "git_lfs_install" "git-lfs already installed"
    fi
    sleep 5

    notify_webhook "provisioning" "git_lfs_init" "Initializing git-lfs globally"
    sleep 5
    if ! sudo git lfs install --system; then
        notify_webhook "warning" "git_lfs_init" "System-level git-lfs initialization failed, falling back to user-level"
        git lfs install --skip-repo || {
            notify_webhook "failed" "git_lfs_init" "User-level git-lfs initialization also failed"
            exit 1
        }
    fi
    notify_webhook "provisioning" "git_lfs_init" "git-lfs initialized successfully"
    sleep 5

    # ========== DOCKER INSTALLATION ==========
    echo "[4/15] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    apt-get remove -y docker docker-engine docker.io containerd runc || true
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list

    apt-get update -q
    apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    CURRENT_USER=$(whoami)
    if [ "$CURRENT_USER" != "root" ]; then
        usermod -aG docker "$CURRENT_USER" || true
    fi

    systemctl enable docker
    systemctl start docker

    echo "[5/15] Waiting for Docker to start..."
    notify_webhook "provisioning" "docker_wait" "Waiting for Docker daemon"
    sleep 5

    timeout=180
    while [ $timeout -gt 0 ]; do
        if docker info >/dev/null 2>&1; then
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

    notify_webhook "provisioning" "docker_ready" "Docker installed successfully"
    sleep 5

    # ========== FORGEJO DIRECTORY SETUP ==========
    echo "[6/15] Setting up Forgejo directories..."
    notify_webhook "provisioning" "directory_setup" "Creating Forgejo directory structure"
    sleep 5

    mkdir -p "$FORGEJO_DIR"/{data,config,ssl,data/gitea/lfs} || {
        echo "ERROR: Failed to create Forgejo directories"
        notify_webhook "failed" "directory_creation" "Failed to create Forgejo directories"
        exit 1
    }
    chown -R 1000:1000 "$FORGEJO_DIR"/data "$FORGEJO_DIR"/config "$FORGEJO_DIR"/data/gitea
    sleep 5
                                      
    # ========== DOCKER COMPOSE CONFIGURATION ==========
    echo "[7/15] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose" "Configuring Docker Compose"
    sleep 5

    cat > "$FORGEJO_DIR/docker-compose.yml" <<EOF
version: "3.8"
networks:
  forgejo:
    external: false

services:
  server:
    image: codeberg.org/forgejo/forgejo:12
    container_name: forgejo
    restart: unless-stopped
    environment:
      - USER_UID=1000
      - USER_GID=1000
      - FORGEJO__server__DOMAIN=$DOMAIN
      - FORGEJO__server__ROOT_URL=https://$DOMAIN
      - FORGEJO__server__HTTP_PORT=3000
      - FORGEJO__server__LFS_START_SERVER=true
      - FORGEJO__server__LFS_CONTENT_PATH=/data/gitea/lfs
      - FORGEJO__server__LFS_JWT_SECRET=$LFS_JWT_SECRET
      - FORGEJO__server__LFS_MAX_FILE_SIZE=$MAX_UPLOAD_SIZE_BYTES
    volumes:
      - ./data:/data
      - ./config:/data/config
      - ./ssl:/data/ssl
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "$PORT:3000"
      - "222:22"
    networks:
      - forgejo
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 15s
      timeout: 10s
      retries: 40
EOF

    sleep 5
    notify_webhook "provisioning" "docker_compose_ready" "Docker Compose configuration created"
    sleep 5


    # ========== FIREWALL CONFIGURATION ==========
    echo "[8/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW firewall"

    if ! ufw status | grep -q inactive; then
        echo "UFW already active; adding rules"
    fi

    ufw allow 22/tcp 
    ufw allow 80/tcp 
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable

    # ========== SSL CERTIFICATE SETUP ==========
    echo "[9/15] Setting up SSL certificates..."
    notify_webhook "provisioning" "ssl_setup" "Configuring SSL certificates"

    # Download recommended SSL configuration
    mkdir -p /etc/letsencrypt                      
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf || true
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem || true

    # Certificate issuance function
    issue_certificate() {
        echo "Attempting to issue SSL certificate..."
        
        if [ -f "$DNS_HOOK_SCRIPT" ]; then
            echo "Using DNS hook script for certificate validation"
            chmod +x "$DNS_HOOK_SCRIPT"
            certbot certonly --manual --preferred-challenges=dns \
                --manual-auth-hook "$DNS_HOOK_SCRIPT add" \
                --manual-cleanup-hook "$DNS_HOOK_SCRIPT clean" \
                --agree-tos --email "$ADMIN_EMAIL" -d "$DOMAIN" -d "*.$DOMAIN" \
                --non-interactive --manual-public-ip-logging-ok || return 1
        else
            echo "Using standalone method for certificate validation"
            systemctl stop nginx || true
            # Try production first, then staging as fallback
            certbot certonly --standalone --preferred-challenges http \
                --agree-tos --email "$ADMIN_EMAIL" -d "$DOMAIN" --non-interactive || \
            certbot certonly --standalone --preferred-challenges http \
                --staging --agree-tos --email "$ADMIN_EMAIL" -d "$DOMAIN" --non-interactive || return 1
            systemctl start nginx || true
        fi
        return 0
    }

    # Retry certificate issuance
    retries=3
    success=false
    for i in $(seq 1 $retries); do
        echo "Certificate attempt $i of $retries..."
        if issue_certificate; then
            echo "✅ SSL certificate issued successfully"
            notify_webhook "provisioning" "ssl_success" "SSL certificate issued successfully"
            success=true
            break
        else
            echo "Attempt $i failed; retrying in 30 seconds..."
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
    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/default
    rm -f /etc/nginx/conf.d/*.conf

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

    # Enable site and test configuration
    ln -sf /etc/nginx/sites-available/forgejo /etc/nginx/sites-enabled/
    nginx -t && systemctl restart nginx

    # ========== FORGEJO CONTAINER STARTUP ==========
    echo "[8/15] Starting Forgejo container..."
    notify_webhook "provisioning" "forgejo_start" "Starting Forgejo container"
    sleep 5

    cd "$FORGEJO_DIR" || {
        echo "ERROR: Cannot change to Forgejo directory"
        notify_webhook "failed" "directory_access" "Cannot access $FORGEJO_DIR"
        exit 1
    }

    # Pull the latest image
    if ! docker compose pull; then
        notify_webhook "warning" "image_pull" "Failed to pull latest Forgejo image, using local if available"
    fi
    sleep 5

    # Start the container
    if ! docker compose up -d; then
        notify_webhook "failed" "forgejo_start" "Forgejo container failed to start"
        docker compose logs --no-color > "$FORGEJO_DIR/forgejo_start.log" || true
        exit 1
    else
        notify_webhook "provisioning" "forgejo_start" "Forgejo container started"
    fi
    sleep 5

    # ========== CONTAINER HEALTH CHECK ==========
    echo "[9/15] Waiting for Forgejo container to become healthy..."
    notify_webhook "provisioning" "health_check" "Checking container health"
    sleep 5

    timeout=180
    while [ $timeout -gt 0 ]; do
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' forgejo 2>/dev/null || echo "none")
        if [ "$HEALTH" = "healthy" ]; then
            echo "✅ Forgejo container is healthy"
            notify_webhook "provisioning" "health_check" "Forgejo container is healthy"
            break
        fi
        echo "Container status: $HEALTH (waiting...)"
        sleep 5
        timeout=$((timeout - 5))
    done

    if [ $timeout -eq 0 ]; then
        echo "WARNING: Forgejo container did not become healthy within timeout"
        notify_webhook "warning" "health_timeout" "Forgejo health check timeout"
        docker compose logs --no-color > "$FORGEJO_DIR/forgejo_health_timeout.log" || true
    fi
    sleep 5

    # ========== FINAL NGINX RESTART ==========
    echo "[13/15] Finalizing nginx configuration..."
    notify_webhook "provisioning" "nginx_final" "Restarting nginx with final config"

    nginx -t && systemctl restart nginx

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

    # ========== COMPLETION MESSAGE ==========
    echo "[15/15] Forgejo setup complete!"
    notify_webhook "provisioning" "provisioning" "Forgejo provisioning completed successfully"

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

 