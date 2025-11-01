import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    FRONTEND_PORT,
    BACKEND_PORT,
    VM_IP,
    PIN_URL,
    VOLUME_DIR="/opt/moonlight-embed",
    WEBHOOK_URL="",
    location="",
    resource_group="",
    DOCKER_COMPOSE_VERSION="v2.27.0",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a full bash provisioning script for Moonlight Embed, in Forgejo/Plane style.
    """

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__FRONTEND_PORT__": str(FRONTEND_PORT),
        "__BACKEND_PORT__": str(BACKEND_PORT),
        "__VM_IP__": VM_IP,
        "__PIN_URL__": PIN_URL,
        "__DATA_DIR__": VOLUME_DIR,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DOCKER_COMPOSE_VERSION__": DOCKER_COMPOSE_VERSION,
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__MOONLIGHT_REPO__": "https://github.com/moonlight-stream/moonlight-embedded.git",
        "__LIBNICE_REPO__": "https://gitlab.freedesktop.org/libnice/libnice",
        "__LIBSRTP_URL__": "https://github.com/cisco/libsrtp/archive/v2.2.0.tar.gz",
        "__USRSCTP_REPO__": "https://github.com/sctplab/usrsctp",
        "__LIBWEBSOCKETS_REPO__": "https://github.com/warmcat/libwebsockets.git",
        "__JANUS_REPO__": "https://github.com/meetecho/janus-gateway.git",
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Moonlight Embed Provisioning Script (Forgejo/Plane style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/moonlight_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    FRONTEND_PORT="__FRONTEND_PORT__"
    BACKEND_PORT="__BACKEND_PORT__"
    VM_IP="__VM_IP__"
    PIN_URL="__PIN_URL__"
    DATA_DIR="__DATA_DIR__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DNS_HOOK_SCRIPT="__DNS_HOOK_SCRIPT__"

    MOONLIGHT_EMBEDDED_DIR="$DATA_DIR/moonlight-embedded"
    JANUS_INSTALL_DIR="/opt/janus"
    LOG_DIR="$DATA_DIR/logs"

    echo "[1/18] Starting Moonlight Embed provisioning..."
    notify_webhook "provisioning" "starting" "Beginning Moonlight game streaming setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/18] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and streaming configuration"

    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "ERROR: Invalid domain $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain format"
        exit 1
    fi

    if ! [[ "$FRONTEND_PORT" =~ ^[0-9]+$ ]] || [ "$FRONTEND_PORT" -lt 1 ] || [ "$FRONTEND_PORT" -gt 65535 ]; then
        echo "ERROR: Invalid frontend port $FRONTEND_PORT"
        notify_webhook "failed" "validation" "Invalid frontend port number"
        exit 1
    fi

    if ! [[ "$BACKEND_PORT" =~ ^[0-9]+$ ]] || [ "$BACKEND_PORT" -lt 1 ] || [ "$BACKEND_PORT" -gt 65535 ]; then
        echo "ERROR: Invalid backend port $BACKEND_PORT"
        notify_webhook "failed" "validation" "Invalid backend port number"
        exit 1
    fi

    # Validate IP address format
    if [[ ! "$VM_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "ERROR: Invalid VM IP address $VM_IP"
        notify_webhook "failed" "validation" "Invalid VM IP address format"
        exit 1
    fi

    # ========== SYSTEM DEPENDENCIES ==========
    echo "[3/18] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages and build tools"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get upgrade -y -q
    apt-get install -y -q curl git nginx certbot python3-pip python3-venv jq make net-tools python3-certbot-nginx openssl ufw

    # Install build dependencies
    apt-get install -y -q build-essential cmake autoconf automake libtool pkg-config \
        libmicrohttpd-dev libjansson-dev libssl-dev libsofia-sip-ua-dev \
        libglib2.0-dev libopus-dev libogg-dev libcurl4-openssl-dev libconfig-dev \
        libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
        wget

    echo "✅ System dependencies installed"
    notify_webhook "provisioning" "dependencies_ready" "✅ System dependencies installed successfully"

    # ========== PRE-STARTUP CHECKS ==========
    echo "[4/18] Running system pre-checks..."
    notify_webhook "provisioning" "system_checks" "Running system pre-checks"

    # Check available disk space (compilation needs significant space)
    echo "    Checking disk space..."
    DISK_AVAILABLE=$(df /tmp /opt /var/lib/docker . | awk 'NR>1 {print $4}' | sort -n | head -1)
    if [ "$DISK_AVAILABLE" -lt 2097152 ]; then  # Less than 2GB
        echo "    ❌ Insufficient disk space: ${DISK_AVAILABLE}KB available"
        df -h
        notify_webhook "failed" "low_disk_space" "Insufficient disk space for compilation - only ${DISK_AVAILABLE}KB available"
        exit 1
    fi
    notify_webhook "provisioning" "disk_check" "✅ Disk space sufficient: ${DISK_AVAILABLE}KB available"
    
    # Check memory (compilation is memory intensive)
    echo "    Checking memory..."
    MEM_AVAILABLE=$(free -m | awk 'NR==2{print $7}')
    if [ "$MEM_AVAILABLE" -lt 1024 ]; then  # Less than 1GB available
        echo "    ⚠️ Low memory available: ${MEM_AVAILABLE}MB (compilation needs memory)"
        notify_webhook "warning" "low_memory" "Low memory available: ${MEM_AVAILABLE}MB - compilation may be slow"
    else
        notify_webhook "provisioning" "memory_check" "✅ Memory sufficient: ${MEM_AVAILABLE}MB available"
    fi
    
    # Check CPU cores for parallel compilation
    CPU_CORES=$(nproc)
    echo "    ✅ CPU cores available: $CPU_CORES"
    notify_webhook "provisioning" "cpu_check" "✅ CPU cores available: $CPU_CORES"

    echo "✅ System pre-checks passed"
    notify_webhook "provisioning" "system_checks_passed" "✅ All system pre-checks passed"

    # ========== CREATE DIRECTORIES ==========
    echo "[5/18] Creating directories..."
    notify_webhook "provisioning" "directory_setup" "Creating Moonlight directory structure"

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create Moonlight data directory"
        notify_webhook "failed" "directory_creation" "Failed to create Moonlight directory"
        exit 1
    }
    mkdir -p "$LOG_DIR"
    mkdir -p "$MOONLIGHT_EMBEDDED_DIR"
    
    cd "$DATA_DIR"
    echo "✅ Directories created"
    notify_webhook "provisioning" "directory_ready" "✅ Moonlight directory structure created"

    # ========== INSTALL LIBSRTP ==========
    echo "[6/18] Installing libsrtp..."
    notify_webhook "provisioning" "install_libsrtp" "Installing Secure RTP library"

    cd /tmp
    if ! wget -q "__LIBSRTP_URL__" -O libsrtp.tar.gz; then
        echo "❌ Failed to download libsrtp"
        notify_webhook "failed" "libsrtp_download" "Failed to download libsrtp"
        exit 1
    fi

    tar xzf libsrtp.tar.gz
    cd libsrtp-2.2.0
    if ./configure --prefix=/usr --enable-openssl && make shared_library && make install; then
        echo "✅ libsrtp installed successfully"
        notify_webhook "provisioning" "libsrtp_installed" "✅ libsrtp installed successfully"
    else
        echo "❌ libsrtp installation failed"
        notify_webhook "failed" "libsrtp_install" "libsrtp installation failed"
        exit 1
    fi
    ldconfig

    # ========== INSTALL USRSCTP ==========
    echo "[7/18] Installing usrsctp..."
    notify_webhook "provisioning" "install_usrsctp" "Installing SCTP library"

    cd /tmp
    if [ ! -d "usrsctp" ]; then
        git clone "__USRSCTP_REPO__" || {
            echo "❌ Failed to clone usrsctp"
            notify_webhook "failed" "usrsctp_clone" "Failed to clone usrsctp repository"
            exit 1
        }
    fi
    
    cd usrsctp
    ./bootstrap
    if ./configure --prefix=/usr && make -j$CPU_CORES && make install; then
        echo "✅ usrsctp installed successfully"
        notify_webhook "provisioning" "usrsctp_installed" "✅ usrsctp installed successfully"
    else
        echo "❌ usrsctp installation failed"
        notify_webhook "failed" "usrsctp_install" "usrsctp installation failed"
        exit 1
    fi
    ldconfig

    # ========== INSTALL LIBWEBSOCKETS ==========
    echo "[8/18] Installing libwebsockets..."
    notify_webhook "provisioning" "install_libwebsockets" "Installing WebSocket library"

    cd /tmp
    if [ ! -d "libwebsockets" ]; then
        git clone "__LIBWEBSOCKETS_REPO__" || {
            echo "❌ Failed to clone libwebsockets"
            notify_webhook "failed" "libwebsockets_clone" "Failed to clone libwebsockets repository"
            exit 1
        }
    fi
    
    cd libwebsockets
    git checkout v4.3-stable
    mkdir -p build
    cd build
    if cmake -DLWS_MAX_SMP=1 -DCMAKE_INSTALL_PREFIX:PATH=/usr -DCMAKE_C_FLAGS="-fpic" .. && \
       make -j$CPU_CORES && make install; then
        echo "✅ libwebsockets installed successfully"
        notify_webhook "provisioning" "libwebsockets_installed" "✅ libwebsockets installed successfully"
    else
        echo "❌ libwebsockets installation failed"
        notify_webhook "failed" "libwebsockets_install" "libwebsockets installation failed"
        exit 1
    fi
    ldconfig

    # ========== INSTALL LIBNICE ==========
    echo "[9/18] Installing libnice..."
    notify_webhook "provisioning" "install_libnice" "Installing ICE library"

    cd /tmp
    if [ ! -d "libnice" ]; then
        git clone "__LIBNICE_REPO__" || {
            echo "❌ Failed to clone libnice"
            notify_webhook "failed" "libnice_clone" "Failed to clone libnice repository"
            exit 1
        }
    fi
    
    cd libnice
    ./autogen.sh
    if ./configure --prefix=/usr && make -j$CPU_CORES && make install; then
        echo "✅ libnice installed successfully"
        notify_webhook "provisioning" "libnice_installed" "✅ libnice installed successfully"
    else
        echo "❌ libnice installation failed"
        notify_webhook "failed" "libnice_install" "libnice installation failed"
        exit 1
    fi
    ldconfig

    # ========== INSTALL MOONLIGHT EMBEDDED ==========
    echo "[10/18] Installing Moonlight Embedded..."
    notify_webhook "provisioning" "install_moonlight" "Installing Moonlight Embedded client"

    cd "$MOONLIGHT_EMBEDDED_DIR"
    if [ ! -d ".git" ]; then
        git clone "__MOONLIGHT_REPO__" . || {
            echo "❌ Failed to clone Moonlight Embedded"
            notify_webhook "failed" "moonlight_clone" "Failed to clone Moonlight Embedded repository"
            exit 1
        }
    else
        git pull origin master
    fi

    mkdir -p build
    cd build
    if cmake .. && make -j$CPU_CORES && make install; then
        echo "✅ Moonlight Embedded installed successfully"
        notify_webhook "provisioning" "moonlight_installed" "✅ Moonlight Embedded installed successfully"
    else
        echo "❌ Moonlight Embedded installation failed"
        notify_webhook "failed" "moonlight_install" "Moonlight Embedded installation failed"
        exit 1
    fi

    # ========== INSTALL JANUS GATEWAY ==========
    echo "[11/18] Installing Janus Gateway..."
    notify_webhook "provisioning" "install_janus" "Installing Janus WebRTC Gateway"

    if [ ! -d "$JANUS_INSTALL_DIR" ]; then
        cd /tmp
        git clone "__JANUS_REPO__" janus-gateway || {
            echo "❌ Failed to clone Janus Gateway"
            notify_webhook "failed" "janus_clone" "Failed to clone Janus Gateway repository"
            exit 1
        }
        
        cd janus-gateway
        sh autogen.sh
        if ./configure --prefix="$JANUS_INSTALL_DIR" --enable-post-processing \
            --enable-data-channels --enable-websockets --enable-rest \
            --enable-plugin-streaming && \
           make -j$CPU_CORES && make install && make configs; then
            echo "✅ Janus Gateway installed successfully"
            notify_webhook "provisioning" "janus_installed" "✅ Janus Gateway installed successfully"
        else
            echo "❌ Janus Gateway installation failed"
            notify_webhook "failed" "janus_install" "Janus Gateway installation failed"
            exit 1
        fi

        # Configure Janus for Moonlight streaming
        cat > $JANUS_INSTALL_DIR/etc/janus/janus.plugin.streaming.jcfg <<EOF
streaming: {
    enabled: true,
    type: "rtp",
    audio: true,
    video: true,
    videoport: 5004,
    videopt: 96,
    videortpmap: "H264/90000",
    audiopt: 111,
    audiortpmap: "opus/48000/2",
    secret: "moonlightstream",
    permanent: true
}
EOF
    else
        echo "✅ Janus Gateway already installed"
        notify_webhook "provisioning" "janus_exists" "✅ Janus Gateway already installed"
    fi

    # ========== CONFIGURE SYSTEMD SERVICES ==========
    echo "[12/18] Configuring systemd services..."
    notify_webhook "provisioning" "setup_services" "Configuring system services"

    # Janus service
    cat > /etc/systemd/system/janus.service <<EOF
[Unit]
Description=Janus WebRTC Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$JANUS_INSTALL_DIR
ExecStart=$JANUS_INSTALL_DIR/bin/janus
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Moonlight streaming service
    cat > /etc/systemd/system/moonlight-stream.service <<EOF
[Unit]
Description=Moonlight to Janus Streaming Service
After=network.target janus.service
Wants=janus.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/moonlight stream $VM_IP -app Steam -codec h264 -bitrate 20000 -fps 60 -unsupported -remote -rtp 127.0.0.1 5004 5005
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload

    # ========== NGINX CONFIG + SSL ==========
    echo "[13/18] Configuring nginx reverse proxy with SSL..."
    notify_webhook "provisioning" "nginx_ssl" "Configuring nginx reverse proxy with SSL"

    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/moonlight

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "__LET_OPTIONS_URL__" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "__SSL_DHPARAMS_URL__" -o /etc/letsencrypt/ssl-dhparams.pem

    # Temporary HTTP server for certbot validation
    cat > /etc/nginx/sites-available/moonlight <<'EOF_TEMP'
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

    ln -sf /etc/nginx/sites-available/moonlight /etc/nginx/sites-enabled/moonlight
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
        notify_webhook "warning" "ssl" "Moonlight Certbot failed, SSL not installed for __DOMAIN__"
    else
        echo "✅ SSL certificate obtained"
        notify_webhook "warning" "ssl" "✅ SSL certificate obtained"

        # Replace nginx config for HTTPS proxy only if SSL exists
        cat > /etc/nginx/sites-available/moonlight <<'EOF_SSL'
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

    # Janus WebSocket endpoint
    location /janus-ws {
        proxy_pass http://localhost:7088;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Janus HTTP API
    location /janus {
        proxy_pass http://localhost:8088;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files for Janus demo pages
    location / {
        root /usr/share/janus/demos;
        index index.html;
        try_files $uri $uri/ =404;
    }

    client_max_body_size 1024M;
}
EOF_SSL

        ln -sf /etc/nginx/sites-available/moonlight /etc/nginx/sites-enabled/moonlight
        nginx -t && systemctl reload nginx
    fi

    echo "[14/18] Setup Cron for renewal..."
    notify_webhook "provisioning" "cron_setup" "Setting up SSL certificate renewal"
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "__CERTBOT_CRON__" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    # ========== FIREWALL CONFIGURATION ==========
    echo "[15/18] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW for streaming services"

    ufw allow 22/tcp    # SSH
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    ufw allow 5004:5005/udp  # RTP streaming
    ufw allow 7088/tcp  # Janus WebSockets
    ufw allow 8088/tcp  # Janus HTTP
    ufw allow 10000-10200/udp  # WebRTC ports
    ufw --force enable

    echo "✅ Firewall configured"
    notify_webhook "provisioning" "firewall_ready" "✅ UFW configured with streaming ports"

    # ========== START SERVICES ==========
    echo "[16/18] Starting streaming services..."
    notify_webhook "provisioning" "start_services" "Starting Janus and Moonlight services"

    systemctl enable janus.service moonlight-stream.service
    
    if systemctl start janus.service; then
        echo "✅ Janus service started successfully"
        notify_webhook "provisioning" "janus_started" "✅ Janus service started successfully"
    else
        echo "❌ Failed to start Janus service"
        journalctl -u janus.service --no-pager -n 20
        notify_webhook "failed" "janus_start_failed" "Failed to start Janus service"
        exit 1
    fi

    sleep 5

    if systemctl start moonlight-stream.service; then
        echo "✅ Moonlight streaming service started successfully"
        notify_webhook "provisioning" "moonlight_started" "✅ Moonlight streaming service started successfully"
    else
        echo "⚠️ Moonlight streaming service failed to start (may need Windows machine to be ready)"
        notify_webhook "warning" "moonlight_start_failed" "Moonlight streaming service failed to start - may need Windows machine"
    fi

    # ========== HEALTH CHECKS ==========
    echo "[17/18] Performing health checks..."
    notify_webhook "provisioning" "health_checks" "Checking streaming services health"

    # Check Janus service
    echo "    Checking Janus Gateway..."
    if systemctl is-active --quiet janus.service; then
        echo "    ✅ Janus Gateway is running"
        notify_webhook "provisioning" "janus_healthy" "✅ Janus Gateway is running"
    else
        echo "    ❌ Janus Gateway is not running"
        notify_webhook "failed" "janus_unhealthy" "Janus Gateway is not running"
        exit 1
    fi

    # Check if Janus is listening on ports
    echo "    Checking Janus ports..."
    if netstat -tuln | grep -q ':7088'; then
        echo "    ✅ Janus WebSocket port (7088) is listening"
    else
        echo "    ⚠️ Janus WebSocket port not listening"
    fi

    if netstat -tuln | grep -q ':8088'; then
        echo "    ✅ Janus HTTP port (8088) is listening"
    else
        echo "    ⚠️ Janus HTTP port not listening"
    fi

    # ========== FINAL VERIFICATION ==========
    echo "[18/18] Final verification..."
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

    echo "🎉 Moonlight Embed deployment completed successfully!"
    notify_webhook "provisioning" "deployment_complete" "✅ Moonlight Embed deployment completed successfully"

    cat <<EOF_SUMMARY
=============================================
🎮 Moonlight Game Streaming Setup Complete!
=============================================

🌐 Access Information:
------------------------------------------------------------
🔗 Streaming Portal: https://$DOMAIN/janus/streaming/test.html
🔗 PIN Service: $PIN_URL
🔑 PIN: $ADMIN_PASSWORD
------------------------------------------------------------

🎥 Streaming Configuration:
------------------------------------------------------------
1. On your Windows machine ($VM_IP):
   - Install Sunshine: https://github.com/LizardByte/Sunshine
   - Use PIN: $ADMIN_PASSWORD for pairing

2. Access the streaming portal:
   - Open: https://$DOMAIN/janus/streaming/test.html
   - Settings:
     • Video: H.264
     • Audio: Opus  
     • Port: 5004
     • Secret: moonlightstream
------------------------------------------------------------

⚙️ Service Management:
------------------------------------------------------------
Janus Gateway:    systemctl status janus.service
Moonlight Stream: systemctl status moonlight-stream.service
Nginx:            systemctl status nginx

Start streaming:  systemctl start moonlight-stream.service
Stop streaming:   systemctl stop moonlight-stream.service
------------------------------------------------------------

📊 Service Status:
------------------------------------------------------------
Janus: $(systemctl is-active janus.service)
Moonlight: $(systemctl is-active moonlight-stream.service)
Nginx: $(systemctl is-active nginx)
------------------------------------------------------------

🔧 Troubleshooting:
------------------------------------------------------------
- Check logs: journalctl -u janus.service -f
- Test WebRTC: https://$DOMAIN/janus/streaming/test.html
- Verify Windows Sunshine is running on $VM_IP
- Ensure PIN pairing is completed
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