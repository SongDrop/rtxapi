import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    MAILCOW_ADMIN_PASSWORD,
    PORT=80,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DATA_DIR="/opt/mailcow-dockerized",
    DOCKER_COMPOSE_VERSION="v2.24.5",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a full bash provisioning script for Mailcow, in Forgejo/Plane style.
    """

    import re

    def get_base_domain(domain):
        domain = domain.strip('.')
        parts = domain.split('.')
        if len(parts) < 2:
            raise ValueError(f"'{domain}' is not a valid FQDN to derive base domain")
        return '.'.join(parts[-2:])

    # Validate domain
    fqdn_pattern = re.compile(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not fqdn_pattern.match(DOMAIN_NAME):
        raise ValueError(f"{DOMAIN_NAME} is not a valid FQDN (e.g., mail.example.com)")

    base_domain = get_base_domain(DOMAIN_NAME)

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__BASE_DOMAIN__": base_domain,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": MAILCOW_ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__DATA_DIR__": DATA_DIR,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DOCKER_COMPOSE_VERSION__": DOCKER_COMPOSE_VERSION,
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__MAILCOW_REPO__": "https://github.com/mailcow/mailcow-dockerized.git",
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Mailcow Provisioning Script (Forgejo/Plane style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/mailcow_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    BASE_DOMAIN="__BASE_DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    PORT="__PORT__"
    DATA_DIR="__DATA_DIR__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"
    MAILCOW_REPO="__MAILCOW_REPO__"

    echo "[1/16] Starting Mailcow provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Mailcow email server setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/16] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and configuration"

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
    echo "[3/16] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get upgrade -y -q
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx openssl ufw netcat-openbsd software-properties-common apt-transport-https ca-certificates gnupg lsb-release

    # ========== DOCKER INSTALLATION ==========
    echo "[4/16] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    # Remove old docker.io package if exists
    apt-get remove -y docker.io >/dev/null 2>&1 || true

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

    # ========== MAILCOW DIRECTORY SETUP ==========
    echo "[5/16] Setting up Mailcow directory..."
    notify_webhook "provisioning" "directory_setup" "Creating Mailcow directory structure"
    sleep 5

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create Mailcow data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Mailcow directory"
        exit 1
    }
    cd "$DATA_DIR"
    echo "✅ Mailcow directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ Mailcow directory created successfully"
    
    sleep 5

    # ========== CLONE MAILCOW REPOSITORY ==========
    echo "[6/16] Cloning Mailcow repository..."
    notify_webhook "provisioning" "clone_repo" "Cloning Mailcow Dockerized repository"

    if [ -d ".git" ]; then
        echo "⚠️ Repository exists, pulling latest changes..."
        git pull origin master
        notify_webhook "provisioning" "repo_updated" "✅ Mailcow repository updated"
    else
        git clone "$MAILCOW_REPO" .
        echo "✅ Mailcow repository cloned"
        notify_webhook "provisioning" "repo_cloned" "✅ Mailcow repository cloned successfully"
    fi

    # ========== PORT AVAILABILITY CHECK ==========
    echo "[7/16] Checking port availability..."
    notify_webhook "provisioning" "port_check" "Checking required ports"

    CRITICAL_PORTS=(25 80 443 465 587 993 995)
    CONFLICTS_FOUND=false

    for port in "${CRITICAL_PORTS[@]}"; do
        if ss -tuln | grep -q ":$port "; then
            echo "    ⚠️ Port $port is in use"
            CONFLICTS_FOUND=true
            # Try to stop common services that might use these ports
            systemctl stop nginx 2>/dev/null || true
            systemctl stop apache2 2>/dev/null || true
            systemctl stop postfix 2>/dev/null || true
            systemctl stop dovecot 2>/dev/null || true
            fuser -k "$port/tcp" 2>/dev/null || true
        else
            echo "    ✅ Port $port is available"
        fi
    done

    if [ "$CONFLICTS_FOUND" = true ]; then
        echo "    ⚠️ Some ports had conflicts but cleanup was attempted"
        notify_webhook "warning" "port_conflicts" "Some ports had conflicts but cleanup attempted"
        sleep 5
    else
        echo "    ✅ All required ports are available"
        notify_webhook "provisioning" "ports_available" "✅ All required ports available"
    fi

    # ========== GENERATE MAILCOW CONFIG ==========
    echo "[8/16] Generating Mailcow configuration..."
    notify_webhook "provisioning" "config_generation" "Generating Mailcow configuration"

    # Generate config non-interactively
    printf '%s\nEtc/UTC\n1\n' "$DOMAIN" | ./generate_config.sh

    if [ -f "mailcow.conf" ]; then
        echo "✅ Mailcow configuration generated"
        notify_webhook "provisioning" "config_generated" "✅ Mailcow configuration generated successfully"
    else
        echo "❌ Failed to generate Mailcow configuration"
        notify_webhook "failed" "config_failed" "Failed to generate Mailcow configuration"
        exit 1
    fi

    # ========== PRE-STARTUP CHECKS ==========
    echo "[9/16] Running system pre-checks..."
    notify_webhook "provisioning" "system_checks" "Running system pre-checks"

    # Check available disk space (Mailcow needs significant space)
    echo "    Checking disk space..."
    DISK_AVAILABLE=$(df /var/lib/docker /opt/mailcow-dockerized /tmp . | awk 'NR>1 {print $4}' | sort -n | head -1)
    if [ "$DISK_AVAILABLE" -lt 5242880 ]; then  # Less than 5GB
        echo "    ❌ Insufficient disk space: ${DISK_AVAILABLE}KB available"
        df -h
        notify_webhook "failed" "low_disk_space" "Insufficient disk space for Mailcow - only ${DISK_AVAILABLE}KB available"
        exit 1
    fi
    notify_webhook "provisioning" "disk_check" "✅ Disk space sufficient: ${DISK_AVAILABLE}KB available"
    
    # Check memory (Mailcow is memory intensive)
    echo "    Checking memory..."
    MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
    if [ "$MEM_AVAILABLE" -lt 2048 ]; then  # Less than 2GB available
        echo "    ⚠️ Low memory available: ${MEM_AVAILABLE}MB (Mailcow needs at least 4GB total)"
        notify_webhook "warning" "low_memory" "Low memory available: ${MEM_AVAILABLE}MB - Mailcow recommends 4GB+"
    else
        notify_webhook "provisioning" "memory_check" "✅ Memory sufficient: ${MEM_AVAILABLE}MB available"
    fi
    
    # Clean up any existing containers that might conflict
    echo "    Cleaning up any existing containers..."
    notify_webhook "provisioning" "cleanup" "Cleaning up existing containers"
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    sleep 2
    
    echo "✅ System pre-checks passed"
    notify_webhook "provisioning" "system_checks_passed" "✅ All system pre-checks passed"

    # ========== START MAILCOW SERVICES ==========
    echo "[10/16] Starting Mailcow services..."
    notify_webhook "provisioning" "services_start" "Starting Mailcow multi-container stack"

    # Detect Docker Compose command
    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi

    # Pull images first
    echo "    Pulling Docker images..."
    notify_webhook "provisioning" "pulling_images" "Pulling Mailcow and dependency images"
    
    if ! $DOCKER_COMPOSE_CMD pull --quiet; then
        echo "    ⚠️ Failed to pull some images, but continuing..."
        notify_webhook "warning" "image_pull_failed" "Failed to pull some images, but continuing"
    else
        echo "    ✅ Images pulled successfully"
        notify_webhook "provisioning" "images_pulled" "✅ Docker images pulled successfully"
    fi

    # Start services
    echo "    Starting Mailcow stack..."
    notify_webhook "provisioning" "stack_start" "Starting Mailcow email stack"
    
    if timeout 300s $DOCKER_COMPOSE_CMD up -d; then
        echo "    ✅ Mailcow stack started successfully"
        notify_webhook "provisioning" "stack_started" "✅ Mailcow stack started successfully"
    else
        echo "    ❌ Failed to start Mailcow stack"
        echo "    🔍 Docker Compose output:"
        $DOCKER_COMPOSE_CMD up -d
        echo "    🔍 Container status:"
        $DOCKER_COMPOSE_CMD ps
        notify_webhook "failed" "stack_start_failed" "Failed to start Mailcow stack - check Docker logs"
        exit 1
    fi

    # ========== HEALTH CHECKS ==========
    echo "[11/16] Performing health checks..."
    notify_webhook "provisioning" "health_checks" "Checking Mailcow services health"

    # Wait for services to initialize (Mailcow takes time to setup)
    echo "    Waiting for Mailcow services to initialize..."
    sleep 60

    # Check container status
    echo "    Checking container status..."
    RUNNING_CONTAINERS=$($DOCKER_COMPOSE_CMD ps --services --filter "status=running" | wc -l)
    TOTAL_CONTAINERS=$($DOCKER_COMPOSE_CMD ps --services | wc -l)

    if [ "$RUNNING_CONTAINERS" -eq "$TOTAL_CONTAINERS" ]; then
        echo "    ✅ All containers running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
        notify_webhook "provisioning" "containers_running" "✅ All containers running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
    else
        echo "    ⚠️ Some containers not running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
        $DOCKER_COMPOSE_CMD ps
        notify_webhook "warning" "containers_partial" "Some containers not running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
    fi

    # Check Mailcow web interface
    echo "    Checking Mailcow web interface..."
    READY=false
    for i in {1..30}; do
        if curl -f -s -k https://localhost >/dev/null 2>&1 || \
           curl -f -s http://localhost >/dev/null 2>&1; then
            READY=true
            break
        fi
        if [ $((i % 6)) -eq 0 ]; then
            echo "    Still waiting for Mailcow... (${i}s)"
            notify_webhook "provisioning" "health_check_progress" "Waiting for Mailcow to be ready... (${i}s)"
        fi
        sleep 5
    done

    if [ "$READY" = true ]; then
        echo "    ✅ Mailcow is responsive"
        notify_webhook "provisioning" "mailcow_healthy" "✅ Mailcow is healthy and responsive"
    else
        echo "    ⚠️ Mailcow not fully responsive, but continuing..."
        notify_webhook "warning" "mailcow_slow_start" "Mailcow taking longer to start, but continuing"
    fi

    # ========== NGINX CONFIG + SSL (Forgejo / fail-safe) ==========
    echo "[12/16] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/mailcow

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/mailcow <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/mailcow /etc/nginx/sites-enabled/mailcow
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
        notify_webhook "warning" "ssl" "Mailcow Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/mailcow <<'EOF_SSL'
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
        proxy_pass https://localhost;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_buffering off;
        proxy_request_buffering off;
        
        # Mailcow specific headers
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Server $host;
    }
}
EOF_SSL

        ln -sf /etc/nginx/sites-available/mailcow /etc/nginx/sites-enabled/mailcow
        nginx -t && systemctl reload nginx
    fi

    echo "[13/16] Setup Cron for renewal..."
    notify_webhook "provisioning" "cron_setup" "Setting up SSL certificate renewal"
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "__CERTBOT_CRON__" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FIREWALL CONFIGURATION ==========
    echo "[14/16] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW for email services"

    # Email service ports
    ufw allow 22/tcp    # SSH
    ufw allow 25/tcp    # SMTP
    ufw allow 465/tcp   # SMTPS
    ufw allow 587/tcp   # Submission
    ufw allow 110/tcp   # POP3
    ufw allow 995/tcp   # POP3S
    ufw allow 143/tcp   # IMAP
    ufw allow 993/tcp   # IMAPS
    ufw allow 4190/tcp  # ManageSieve
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS

    # Allow Docker bridge network traffic
    ufw allow in on docker0
    ufw allow out on docker0

    # Outbound email traffic
    ufw allow out 25/tcp
    ufw allow out 53
    ufw allow out 443/tcp
    ufw allow out 587/tcp

    ufw --force enable

    echo "✅ Firewall configured"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with email service ports"

    # ========== FINAL VERIFICATION ==========
    echo "[15/16] Final verification..."
    notify_webhook "provisioning" "final_verification" "Performing final verification"

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

    # Display final status
    echo "📊 Final container status:"
    $DOCKER_COMPOSE_CMD ps

    # Test web interface accessibility
    echo "🔍 Testing web interface..."
    if curl -f -s -k "https://$DOMAIN" >/dev/null 2>&1; then
        echo "    ✅ Mailcow web interface accessible via domain"
        notify_webhook "provisioning" "web_accessible" "✅ Mailcow web interface accessible via domain"
    else
        echo "    ⚠️ Mailcow not immediately accessible via domain (may need DNS propagation)"
        notify_webhook "warning" "domain_check_delayed" "Mailcow domain access may need DNS propagation"
    fi

    echo "[16/16] Displaying DNS configuration..."
    notify_webhook "provisioning" "dns_config" "Displaying DNS configuration instructions"

    echo "🎉 Mailcow deployment completed successfully!"
    notify_webhook "provisioning" "deployment_complete" "✅ Mailcow deployment completed successfully"

    cat <<EOF_SUMMARY
=============================================
📧 Mailcow Email Server Deployment Complete!
🔗 Access URL: https://$DOMAIN
📧 Admin email: $ADMIN_EMAIL
🔐 Admin password: $ADMIN_PASSWORD
⚙️ Useful commands:
- Status: cd $DATA_DIR && docker compose ps
- Logs: cd $DATA_DIR && docker compose logs -f
- Restart: cd $DATA_DIR && docker compose restart
- Update: cd $DATA_DIR && docker compose pull && docker compose up -d
- Stop: cd $DATA_DIR && docker compose down

📋 IMPORTANT DNS RECORDS to configure:
A Record: $DOMAIN -> Your Server IP
CNAME: autodiscover -> $DOMAIN
CNAME: autoconfig -> $DOMAIN
MX Record for $BASE_DOMAIN: $DOMAIN (priority 10)
SRV Record: _autodiscover._tcp -> 0 5 443 $DOMAIN
TXT Record (SPF): "v=spf1 mx -all"
TXT Record (_DMARC): "v=DMARC1; p=quarantine; adkim=s; aspf=s"

🔐 After setup, add these from Mailcow UI:
- TLSA for _25._tcp.$DOMAIN
- TXT for dkim._domainkey.$BASE_DOMAIN

📊 Services included:
  • Postfix (SMTP)
  • Dovecot (IMAP/POP3)
  • Redis (Caching)
  • Nginx (Web)
  • PHP-FPM
  • SOGo (Groupware)
  • Rspamd (Spam filter)
  • ClamAV (Virus scanner)
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

    # Replace CERTBOT_CRON token
    certbot_cron = "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
    final = final.replace("__CERTBOT_CRON__", certbot_cron)

    return final