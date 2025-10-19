import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT_UI=8080,
    PORT_VPN=1194,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh",
):
    """
    Returns a full 15-step OpenVPN provisioning script with UI, Docker, and Nginx SSL.
    (Styled consistently with Bytestash provisioning conventions)
    """
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT_UI__": str(PORT_UI),
        "__PORT_VPN__": str(PORT_VPN),
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__OPENVPN_DIR__": "/opt/openvpn",
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
    }

    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # OpenVPN Server Provisioning Script (Bytestash Style)
    # ----------------------------------------------------------------------

    __WEBHOOK_FUNCTION__

    error_handler() {
        local exit_code=$?
        local line_number=$1
        echo "❌ ERROR: Script failed at line $line_number (exit code $exit_code)"
        notify_webhook "failed" "unexpected_error" "Script failed at line $line_number with code $exit_code"
        exit $exit_code
    }
    trap 'error_handler ${LINENO}' ERR

    LOG_FILE="/var/log/openvpn_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    OPENVPN_DIR="__OPENVPN_DIR__"
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    PORT_UI="__PORT_UI__"
    PORT_VPN="__PORT_VPN__"
    WEBHOOK_URL="__WEBHOOK_URL__"

    READY_TIMEOUT=300
    SLEEP_INTERVAL=10

    echo "[1/15] 🚀 Starting OpenVPN provisioning..."
    notify_webhook "provisioning" "starting" "Beginning OpenVPN setup"

    # ----------------------------------------------------------------------
    # Step 2: Validate Inputs
    # ----------------------------------------------------------------------
    echo "[2/15] 🔍 Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and ports"

    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "❌ ERROR: Invalid domain format: $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain: $DOMAIN"
        exit 1
    fi

    for port in "$PORT_UI" "$PORT_VPN"; do
        if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
            echo "❌ ERROR: Invalid port number: $port"
            notify_webhook "failed" "validation" "Invalid port number: $port"
            exit 1
        fi
    done
    sleep 2

    # ----------------------------------------------------------------------
    # Step 3: Install System Dependencies
    # ----------------------------------------------------------------------
    echo "[3/15] 🧩 Installing system dependencies..."
    notify_webhook "provisioning" "dependencies" "Installing required system packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get upgrade -y -qq
    apt-get install -y -qq curl git nginx certbot python3-certbot-nginx python3-pip python3-venv jq ufw xxd lsb-release software-properties-common
    sleep 5

    # ----------------------------------------------------------------------
    # Step 4: Install Docker
    # ----------------------------------------------------------------------
    echo "[4/15] 🐳 Installing Docker and Docker Compose..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine and Compose"
    apt-get install -y -qq ca-certificates curl gnupg lsb-release apt-transport-https
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
      tee /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    systemctl enable docker
    systemctl start docker
    sleep 5

    # ----------------------------------------------------------------------
    # Step 5: Clone OpenVPN Repo
    # ----------------------------------------------------------------------
    echo "[5/15] 📦 Cloning OpenVPN repository..."
    notify_webhook "provisioning" "clone_repo" "Cloning SongDrop/openvpnserver-with-ui"
    git clone https://github.com/SongDrop/openvpnserver-with-ui.git "$OPENVPN_DIR"
    cd "$OPENVPN_DIR"

    # ----------------------------------------------------------------------
    # Step 6: Override docker-compose.yml
    # ----------------------------------------------------------------------
    echo "[6/15] ⚙️ Writing docker-compose.yml..."
    notify_webhook "provisioning" "compose_file" "Writing OpenVPN docker-compose.yml"

    cat > docker-compose.yml <<EOF
    version: "3.5"
    services:
      openvpn:
        container_name: openvpn
        image: iamjanam/openvpn-server-with-ui:latest
        privileged: true
        ports:
          - "${PORT_VPN}:1194/udp"
        environment:
          TRUST_SUB: "10.0.70.0/24"
          GUEST_SUB: "10.0.71.0/24"
          HOME_SUB: "192.168.88.0/24"
        volumes:
          - ./pki:/etc/openvpn/pki
          - ./clients:/etc/openvpn/clients
          - ./config:/etc/openvpn/config
          - ./staticclients:/etc/openvpn/staticclients
          - ./log:/var/log/openvpn
          - ./fw-rules.sh:/opt/app/fw-rules.sh
          - ./checkpsw.sh:/opt/app/checkpsw.sh
        cap_add:
          - NET_ADMIN
        restart: always
        depends_on:
          - openvpn-ui

      openvpn-ui:
        container_name: openvpn-ui
        image: d3vilh/openvpn-ui:latest
        environment:
          - OPENVPN_ADMIN_USERNAME=admin
          - OPENVPN_ADMIN_PASSWORD=__ADMIN_PASSWORD__
        privileged: true
        ports:
          - "${PORT_UI}:8080/tcp"
        volumes:
          - ./:/etc/openvpn
          - ./db:/opt/openvpn-ui/db
          - ./pki:/usr/share/easy-rsa/pki
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: always
    EOF
    sleep 2

    # ----------------------------------------------------------------------
    # Step 7: Start Containers
    # ----------------------------------------------------------------------
    echo "[7/15] 🚀 Starting OpenVPN containers..."
    notify_webhook "provisioning" "containers" "Launching OpenVPN and UI containers"
    docker compose pull || true
    docker compose up -d || true
    sleep 10

    # ----------------------------------------------------------------------
    # Step 8: Configure Firewall
    # ----------------------------------------------------------------------
    echo "[8/15] 🔥 Configuring firewall (UFW)..."
    notify_webhook "provisioning" "firewall" "Applying UFW rules"
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow "$PORT_UI"/tcp
    ufw allow "$PORT_VPN"/udp
    ufw --force enable
    sleep 3

    # ----------------------------------------------------------------------
    # Step 9: Wait for UI Readiness
    # ----------------------------------------------------------------------
    echo "[9/15] ⏳ Waiting for OpenVPN UI readiness..."
    notify_webhook "provisioning" "ui_wait" "Waiting for UI to respond"
    elapsed=0; READY=false
    while [ $elapsed -lt $READY_TIMEOUT ]; do
        if curl -sf http://127.0.0.1:$PORT_UI/ >/dev/null 2>&1; then
            READY=true; break
        fi
        sleep $SLEEP_INTERVAL
        elapsed=$((elapsed + SLEEP_INTERVAL))
    done
    if [ "$READY" = false ]; then
        echo "❌ OpenVPN UI did not respond in time"
        notify_webhook "failed" "ui_timeout" "OpenVPN UI failed to start"
        exit 1
    fi

   # ========== NGINX CONFIG + SSL (OpenVPN / fail-safe style) ==========
    echo "[10/15] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL..."

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/openvpn_ui

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/openvpn_ui <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/openvpn_ui /etc/nginx/sites-enabled/openvpn_ui
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
        notify_webhook "warning" "ssl" "OpenVPN Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "provisioning" "ssl" "✅ SSL certificate obtained"

    # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/openvpn_ui <<'EOF_SSL'
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

    location / {
        proxy_pass http://127.0.0.1:${PORT_UI};
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

        ln -sf /etc/nginx/sites-available/openvpn_ui /etc/nginx/sites-enabled/openvpn_ui
        nginx -t && systemctl reload nginx
    fi

    echo "[11/15] Setting up cron for SSL renewal..."
    notify_webhook "provisioning" "cron_setup" "Setting up daily SSL renewal cron job"

    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "certbot renew" || true; \
        echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ----------------------------------------------------------------------
    # Step 12–15: Final Checks
    # ----------------------------------------------------------------------
    echo "[12-15/15] ✅ Running final verification..."
    notify_webhook "provisioning" "verification" "Verifying OpenVPN installation"

    if ! docker ps | grep -q openvpn; then
        echo "❌ OpenVPN container not running"
        notify_webhook "failed" "container_check" "OpenVPN container failed to start"
        exit 1
    fi

    echo "🌐 Checking HTTPS response for ${DOMAIN}..."
    curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN} || true

    echo "✅ OpenVPN provisioning complete!"
    notify_webhook "provisioning" "completed" "✅ OpenVPN setup completed successfully"
    """)

    # -------------------------------
    # Inject webhook function
    # -------------------------------
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
            "details": { "step": "$step", "message": "$message" }
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
        webhook_fn = "notify_webhook() { return 0; }"

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
