import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT=5000,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    UPLOAD_SIZE_MB=256,
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
):
    """
    Returns a full 15-step Bytestash provisioning script in your style.
    """
    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__BYTESTASH_DIR__": "/opt/bytestash",
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__MAX_UPLOAD_SIZE_MB__": f"{UPLOAD_SIZE_MB}M",
        "__MAX_UPLOAD_SIZE_BYTES__": str(UPLOAD_SIZE_MB * 1024 * 1024),
    }

    # ------------------ SCRIPT TEMPLATE ------------------
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Plane Provisioning Script (Forgejo style)
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
    LOG_FILE="/var/log/bytestash_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1
                                      
    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    PORT="__PORT__"
    BYTESTASH_DIR="__BYTESTASH_DIR__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    MAX_UPLOAD_SIZE_MB="__MAX_UPLOAD_SIZE_MB__"
    MAX_UPLOAD_SIZE_BYTES="__MAX_UPLOAD_SIZE_BYTES__"

    # Add missing variables
    READY_TIMEOUT=300
    SLEEP_INTERVAL=10

    echo "[1/15] Starting Bytestash provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Bytestash setup"  

    # --- Step 1: Validate Inputs ---
    echo "[2/15] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and port"
   
    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "ERROR: Invalid domain format: $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain format: $DOMAIN"
        exit 1
    fi
    
    if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
        echo "ERROR: Invalid port number: $PORT"
        notify_webhook "failed" "validation" "Invalid port: $PORT"
        exit 1
    fi

    # Generate 64-byte JWT secret (128 hex chars)
    if [ -z "${BYTESTASH_JWT_SECRET:-}" ]; then
        BYTESTASH_JWT_SECRET=$(head -c 64 /dev/urandom | xxd -p -c 64 | head -1)
        export BYTESTASH_JWT_SECRET
    fi
    
    echo "[2/15] JWT secret generated"
    notify_webhook "provisioning" "jwt_generated" "JWT secret generated"
    sleep 5

   
    # --- Step 3: System dependencies ---
    echo "[3/15] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"

    export DEBIAN_FRONTEND=noninteractive

    notify_webhook "provisioning" "apt_update" "Running apt-get update"
    apt-get update -q || { notify_webhook "failed" "apt_update" "apt-get update failed"; exit 1; }

    notify_webhook "provisioning" "apt_upgrade" "Running apt-get upgrade"
    apt-get upgrade -y -q || { notify_webhook "failed" "apt_upgrade" "apt-get upgrade failed"; exit 1; }

    # Ensure system is ready for next apt operation
    sleep 3
    fuser -vki /var/lib/dpkg/lock-frontend || true
    dpkg --configure -a

    notify_webhook "provisioning" "apt_install" "Installing required packages"
    apt-get install -y -q \
        curl git nginx certbot python3-certbot-nginx python3-pip python3-venv jq make ufw xxd \
        software-properties-common \
    || { notify_webhook "failed" "apt_install" "Base package install failed"; exit 1; }

    # ========== DOCKER INSTALLATION ==========
    echo "[4/15] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    # Install prerequisites
    apt-get install -y -q ca-certificates curl gnupg lsb-release apt-transport-https || {
        echo "❌ Failed to install Docker prerequisites"
        notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
        exit 1
    }

    # Remove old versions (ignore errors)
    apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

    # Setup Docker's official GPG key
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg || {
        echo "❌ Failed to download Docker GPG key"
        notify_webhook "failed" "docker_gpg" "Failed to download Docker GPG key"
        exit 1
    }
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Update package list with new repository
    apt-get update -q || {
        echo "❌ Failed to update package list after adding Docker repo"
        notify_webhook "failed" "docker_repo" "Failed to update package list"
        exit 1
    }

    # Install Docker with retries
    for i in {1..3}; do
        echo "Docker install attempt $i/3..."
        if apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin; then
            break
        fi
        echo "⚠️ Docker install attempt $i failed; retrying in 5 seconds..."
        sleep 5
        if [ $i -eq 3 ]; then
            echo "❌ Docker installation failed after 3 attempts"
            notify_webhook "failed" "docker_install" "Docker install failed after 3 attempts"
            exit 1
        fi
    done

    # ========== DOCKER COMPOSE INSTALLATION ==========
    echo "[4.5/15] Installing Docker Compose..."
    notify_webhook "provisioning" "docker_compose_install" "Installing Docker Compose"
    
    # Try Docker Compose plugin first (now that Docker repo is available)
    if apt-get install -y -q docker-compose-plugin; then
        echo "✅ Docker Compose plugin installed via apt"
    else
        echo "⚠️ Docker Compose plugin not available, installing via pip"
        # Ensure pip is properly installed and updated
        apt-get install -y -q python3-pip python3-venv || {
            echo "❌ Failed to install python3-pip"
            notify_webhook "failed" "docker_compose" "Failed to install python3-pip for Docker Compose"
            exit 1
        }
        # Update pip and install docker-compose
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
                                      
    # ========== BYTESTASH DIRECTORY SETUP ==========
    echo "[5/15] Creating Bytestash directories..."
    notify_webhook "provisioning" "directories" "Creating Bytestash directories"

    mkdir -p "$BYTESTASH_DIR" || {
        echo "ERROR: Failed to create Plane data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Plane directory"
        exit 1
    }
    chown -R 1000:1000 "$BYTESTASH_DIR"
    cd "$BYTESTASH_DIR"
    echo "✅ Bytestash directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ Bytestash directory created successfully"
    
    sleep 5
                                      
    # --- Step 4: Docker Compose ---
    echo "[6/15] Creating Docker Compose configuration..."
    notify_webhook "provisioning" "docker_compose" "Creating docker-compose.yml"

    cat > "$BYTESTASH_DIR/docker-compose.yml" <<EOF
version: "3.8"

services:
  bytestash:
    image: ghcr.io/jordan-dalby/bytestash:latest
    container_name: bytestash
    restart: on-failure:5

    healthcheck:
      test: ["CMD-SHELL", "nc -z 127.0.0.1 5000 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 90s

    volumes:
      - ./data:/data/snippets:rw

    environment:
      JWT_SECRET: "${BYTESTASH_JWT_SECRET}"
      TOKEN_EXPIRY: "24h"
      ALLOW_NEW_ACCOUNTS: "true"

    ports:
      - "${PORT}:5000"
EOF


    sleep 5

    # --- Step 5: Start Docker container ---
    echo "[7/15] Starting Bytestash container..."
    notify_webhook "provisioning" "container_start" "Starting Bytestash container"
    cd "$BYTESTASH_DIR"

    # Create the data directory with proper permissions
    mkdir -p data
    chown -R 1000:1000 data

    # Export the JWT secret for docker-compose
    export BYTESTASH_JWT_SECRET

    # Debug: Show environment
    echo "Debug: Current directory: $(pwd)"
    echo "Debug: JWT secret length: ${#BYTESTASH_JWT_SECRET}"
    echo "Debug: Docker Compose file:"
    cat docker-compose.yml

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

    # Pull & start (don't exit immediately on failure so we can collect diagnostics)
    $COMPOSE_CMD pull || echo "Warning: Image pull failed, will try to run anyway"
    $COMPOSE_CMD up -d || echo "Warning: docker compose up returned non-zero (continuing to collect diagnostics)"

    # Wait for container to initialize briefly so logs appear
    echo "Waiting for container to initialize..."
    sleep 5

    # --- Always collect diagnostics and send to webhook (even if container exited) ---
    # docker ps -a (no-trunc) and focus on bytestash if present
    DOCKER_PS_OUTPUT=$(docker ps -a --no-trunc 2>/dev/null || echo "docker ps failed")
    SHORT_PS=$(echo "$DOCKER_PS_OUTPUT" | grep -i bytestash || echo "$DOCKER_PS_OUTPUT" | head -n 20)
    SHORT_PS_ESCAPED=$(echo "$SHORT_PS" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
    notify_webhook "provisioning" "docker_ps" "=== docker ps output ===\\n$SHORT_PS_ESCAPED"

    # docker inspect (first chunk)
    INSPECT_OUTPUT=$(docker inspect bytestash 2>/dev/null || echo "inspect failed")
    INSPECT_ESCAPED=$(echo "$INSPECT_OUTPUT" | head -n 50 | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
    notify_webhook "provisioning" "docker_inspect" "=== docker inspect (first 50 lines) ===\\n$INSPECT_ESCAPED"

    # docker logs (last 100 lines if available)
    LOG_TAIL=$(docker logs bytestash --tail 100 2>/dev/null || echo "no logs")
    LOG_ESCAPED=$(echo "$LOG_TAIL" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
    notify_webhook "provisioning" "docker_logs" "=== container logs (last 100 lines) ===\\n$LOG_ESCAPED"

    sleep 5

    # Show compose/service status locally (keeps original debugging behavior)
    echo "=== Docker Compose Status ==="
    if docker compose version &> /dev/null; then
        docker compose ps || true
    else
        docker-compose ps || true
    fi

    echo "=== Port Mapping Check ==="
    docker port bytestash 2>/dev/null || echo "Could not check port mapping"

    notify_webhook "provisioning" "container_started" "✅ Docker container start attempted and diagnostics sent"

    sleep 5

    # Now evaluate container lifecycle status and fail fast if needed
    CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' bytestash 2>/dev/null || echo "nonexistent")
    echo "Container status: $CONTAINER_STATUS"
    if [ "$CONTAINER_STATUS" != "running" ]; then
        # Send an extra diagnostics burst (in case it died after the earlier snapshot)
        DOCKER_PS_OUTPUT2=$(docker ps -a --no-trunc 2>/dev/null || echo "docker ps failed")
        PS2_ESCAPED=$(echo "$DOCKER_PS_OUTPUT2" | head -n 50 | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
        notify_webhook "provisioning" "docker_ps_followup" "=== docker ps (follow-up) ===\\n$PS2_ESCAPED"

        LOG_TAIL2=$(docker logs bytestash --tail 200 2>/dev/null || echo "no logs")
        LOG2_ESCAPED=$(echo "$LOG_TAIL2" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
        notify_webhook "provisioning" "docker_logs_followup" "=== container logs (follow-up last 200 lines) ===\\n$LOG2_ESCAPED"

        echo "❌ Bytestash container is not running. Status: $CONTAINER_STATUS"
        notify_webhook "failed" "container_start" "Bytestash failed to start (status: $CONTAINER_STATUS). Diagnostics posted."
        exit 1
    fi

    echo "✅ Bytestash container is running"
    notify_webhook "provisioning" "container_running" "Bytestash container running successfully"
    sleep 5


    # --- Firewall ---
    echo "[8/15] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW"
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable
    UFW_STATUS=$(ufw status verbose 2>/dev/null || echo "ufw not present")
    UFW_STATUS_ESCAPED=$(echo "$UFW_STATUS" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
    notify_webhook "provisioning" "firewall_status" "UFW status:\\n$UFW_STATUS_ESCAPED"

    # --- Step 9: Wait for readiness (HTTP probe) ---
    echo "[9/15] Waiting for Bytestash readiness..."
    notify_webhook "provisioning" "http_probe" "Waiting for HTTP readiness"

    CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' bytestash 2>/dev/null || echo "nonexistent")
    echo "Container status: $CONTAINER_STATUS"
    if [ "$CONTAINER_STATUS" != "running" ]; then
        docker logs bytestash 2>/dev/null || echo "No logs available"
        notify_webhook "failed" "http_probe" "Bytestash container not running. Status: $CONTAINER_STATUS"
        exit 1
    fi

    docker top bytestash || echo "Could not check container processes"

    elapsed=0
    READY=false
    while [ $elapsed -lt $READY_TIMEOUT ]; do
        if [ "$(docker inspect -f '{{.State.Status}}' bytestash 2>/dev/null)" != "running" ]; then
            echo "❌ Container stopped during startup"
            docker logs bytestash 2>/dev/null || true
            break
        fi

        echo "Testing connection to port $PORT..."
        if netstat -tuln | grep ":$PORT " >/dev/null; then
            echo "✅ Port $PORT is bound on host"
        else
            echo "❌ Port $PORT is NOT bound on host"
        fi

        for endpoint in "/" "/health" "/api/health" "/status"; do
            if curl -v "http://127.0.0.1:$PORT$endpoint" 2>&1 | grep -q "HTTP.*200"; then
                echo "✅ Successfully connected to $endpoint"
                READY=true
                break 2
            fi
        done

        if [ $((elapsed % 30)) -eq 0 ]; then
            docker logs bytestash --since "1m ago" 2>/dev/null | tail -10 || echo "No recent logs"
        fi

        sleep $SLEEP_INTERVAL
        elapsed=$((elapsed + SLEEP_INTERVAL))
    done

    if [ "$READY" = false ]; then
        notify_webhook "failed" "http_probe" "Bytestash not responding after $READY_TIMEOUT seconds"
        exit 1
    fi

    echo "✅ Bytestash is ready and responding"
    notify_webhook "provisioning" "http_ready" "✅ Bytestash HTTP probe successful"
    sleep 5

    # ========== NGINX CONFIG + SSL (Bytestash / fail-safe) ==========
    echo "[11/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/bytestash

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/bytestash <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/bytestash /etc/nginx/sites-enabled/bytestash
    nginx -t && systemctl restart nginx

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html

    # Attempt to obtain SSL certificate
    # Use --staging if you hit the daily limit
    # certbot --nginx -d "__DOMAIN__" --staging --non-interactive --agree-tos -m "__ADMIN_EMAIL__"
    if ! certbot --nginx -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__"; then
        echo "⚠️ Certbot nginx plugin failed; trying webroot fallback"
        systemctl start nginx || true
        certbot certonly --webroot -w /var/www/html -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__" || true
    fi

    # Fail-safe check
    if [ ! -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        echo "⚠️ SSL certificate not found! Continuing without SSL..."
        notify_webhook "warning" "ssl" "Bytestash Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/bytestash <<'EOF_SSL'
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

    client_max_body_size __MAX_UPLOAD_SIZE_MB__;

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

        ln -sf /etc/nginx/sites-available/bytestash /etc/nginx/sites-enabled/bytestash
        nginx -t && systemctl reload nginx
    fi

    echo "[12/15] Setup Cron for renewal..."
    notify_webhook "provisioning" "cron_setup" "Setup Cron for renewal..."
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "certbot renew" || true; \
    echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FINAL CHECKS ==========
    echo "[13/15] Final verification..."
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

    echo "[14/15] Final system checks..."
    # Verify Docker container is running
    if ! docker ps | grep -q bytestash; then
        echo "❌ Bytestash container is not running"
        notify_webhook "failed" "verification" "Bytestash container not running"
        exit 1
    fi
                                      
    # --- Step 15: Final summary ---
    echo "[15/15] Bytestash provisioning complete!"
    notify_webhook "provisioning" "bytestash_installed" "✅ Bytestash setup completed successfully"
    

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