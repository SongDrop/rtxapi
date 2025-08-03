def generate_setup(DOMAIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT, VM_IP, PIN_URL, VOLUME_DIR="/opt/moonlight-embed", WEBHOOK_URL=""):
    github_url = "https://github.com/moonlight-stream/moonlight-embedded.git"
    
    # Define the Moonlight Embedded directory path
    MOONLIGHT_EMBEDDED_DIR = f"{VOLUME_DIR}/moonlight-embedded"

    libnice_git_url = "https://gitlab.freedesktop.org/libnice/libnice"
    libsrtp_tar_url = "https://github.com/cisco/libsrtp/archive/v2.2.0.tar.gz"
    usrsctp_git_url = "https://github.com/sctplab/usrsctp"
    libwebsockets_git_url = "https://github.com/warmcat/libwebsockets.git"
    janus_git_url = "https://github.com/meetecho/janus-gateway.git"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"

    # Webhook notification function with proper JSON structure
    webhook_notification = ""
    if WEBHOOK_URL:
        webhook_notification = f'''
notify_webhook() {{
  local status=$1
  local step=$2
  local message=$3
  
  if [ -z "${{WEBHOOK_URL}}" ]; then
    return 0
  fi
  
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Notifying webhook: status=$status step=$step"
  
  # Prepare the JSON payload matching Azure Function expectations
  JSON_PAYLOAD=$(cat <<EOF
{{
  "vm_name": "$(hostname)",
  "status": "$status",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "details": {{
    "step": "$step",
    "message": "$message"
  }}
}}
EOF
  )

  curl -X POST \\
    "${{WEBHOOK_URL}}" \\
    -H "Content-Type: application/json" \\
    -d "$JSON_PAYLOAD" \\
    --connect-timeout 10 \\
    --max-time 30 \\
    --retry 2 \\
    --retry-delay 5 \\
    --silent \\
    --output /dev/null \\
    --write-out "Webhook notification result: %{{http_code}}"

  return $?
}}
'''
    else:
        webhook_notification = '''
notify_webhook() {
  # No webhook URL configured
  return 0
}
'''

    script_template = f'''#!/bin/bash

set -e

export DEBIAN_FRONTEND=noninteractive

# === User config ===
DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
FRONTEND_PORT={FRONTEND_PORT}
BACKEND_PORT={BACKEND_PORT}
VM_IP="{VM_IP}"
PIN_URL="{PIN_URL}"
INSTALL_DIR="{VOLUME_DIR}"
LOG_DIR="${{INSTALL_DIR}}/logs"
DOCKER_IMAGE_NAME="moonlight-embed-app"
DOCKER_CONTAINER_NAME="moonlight-embed-container"
JANUS_INSTALL_DIR="/opt/janus"
MOONLIGHT_EMBEDDED_DIR="{MOONLIGHT_EMBEDDED_DIR}"
WEBHOOK_URL="{WEBHOOK_URL}"

{webhook_notification}

# === Validate domain format ===
if ! [[ "${{DOMAIN_NAME}}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain format"
    notify_webhook "failed" "validation" "Invalid domain format"
    exit 1
fi

notify_webhook "provisioning" "starting" "Beginning system setup"

echo "[1/10] Updating system and installing base dependencies..."
notify_webhook "provisioning" "system_update" "Updating system packages"
apt-get update
apt-get install -y --no-install-recommends \\
    curl git nginx certbot python3-certbot-nginx \\
    docker.io ufw build-essential cmake autoconf automake libtool pkg-config \\
    libmicrohttpd-dev libjansson-dev libssl-dev libsofia-sip-ua-dev \\
    libglib2.0-dev libopus-dev libogg-dev libcurl4-openssl-dev libconfig-dev \\
    libavcodec-dev libavformat-dev libavutil-dev libswscale-dev

echo "[2/10] Installing libsrtp..."
notify_webhook "provisioning" "install_libsrtp" "Installing libsrtp"
cd /tmp
wget {libsrtp_tar_url} -O libsrtp.tar.gz
tar xzf libsrtp.tar.gz
cd libsrtp-2.2.0
./configure --prefix=/usr --enable-openssl
make shared_library && make install
ldconfig
cd -

echo "[3/10] Installing usrsctp..."
notify_webhook "provisioning" "install_usrsctp" "Installing usrsctp"
cd /tmp
git clone {usrsctp_git_url}
cd usrsctp
./bootstrap
./configure --prefix=/usr
make && make install
ldconfig
cd -

echo "[4/10] Installing libwebsockets..."
notify_webhook "provisioning" "install_libwebsockets" "Installing libwebsockets"
cd /tmp
git clone {libwebsockets_git_url}
cd libwebsockets
git checkout v4.3-stable
mkdir build
cd build
cmake -DLWS_MAX_SMP=1 -DCMAKE_INSTALL_PREFIX:PATH=/usr -DCMAKE_C_FLAGS="-fpic" ..
make && make install
ldconfig
cd -

echo "[5/10] Installing libnice..."
notify_webhook "provisioning" "install_libnice" "Installing libnice"
cd /tmp
git clone {libnice_git_url}
cd libnice
./autogen.sh
./configure --prefix=/usr
make && make install
ldconfig
cd -

echo "[6/10] Setting up installation directory..."
notify_webhook "provisioning" "setup_directories" "Creating installation directories"
mkdir -p "${{INSTALL_DIR}}"
mkdir -p "${{LOG_DIR}}"
cd "${{INSTALL_DIR}}"

echo "[7/10] Installing Moonlight Embedded..."
notify_webhook "provisioning" "install_moonlight" "Installing Moonlight Embedded"
mkdir -p "${{MOONLIGHT_EMBEDDED_DIR}}"
if [ ! -d "${{MOONLIGHT_EMBEDDED_DIR}}/.git" ]; then
    git clone {github_url} "${{MOONLIGHT_EMBEDDED_DIR}}"
fi

cd "${{MOONLIGHT_EMBEDDED_DIR}}"
git pull
mkdir -p build
cd build
cmake .. && make -j$(nproc) && make install

echo "[8/10] Installing Janus Gateway..."
notify_webhook "provisioning" "install_janus" "Installing Janus Gateway"
if [ ! -d "${{JANUS_INSTALL_DIR}}" ]; then
    git clone {janus_git_url} /tmp/janus-gateway
    cd /tmp/janus-gateway
    sh autogen.sh
    ./configure --prefix="${{JANUS_INSTALL_DIR}}" --enable-post-processing \\
        --enable-data-channels --enable-websockets --enable-rest \\
        --enable-plugin-streaming
    make
    make install
    make configs
    
    # Configure Janus for Moonlight streaming
    cat > ${{JANUS_INSTALL_DIR}}/etc/janus/janus.plugin.streaming.jcfg <<EOF
streaming: {{
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
}}
EOF
fi

echo "[9/10] Setting up systemd services..."
notify_webhook "provisioning" "setup_services" "Configuring system services"

# Janus service
cat > /etc/systemd/system/janus.service <<EOF
[Unit]
Description=Janus WebRTC Server
After=network.target

[Service]
Type=simple
User=root
ExecStart=${{JANUS_INSTALL_DIR}}/bin/janus
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Moonlight streaming service
cat > /etc/systemd/system/moonlight-stream.service <<EOF
[Unit]
Description=Moonlight to Janus Streaming Service
After=network.target janus.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/moonlight stream ${{VM_IP}} -app Steam -codec h264 -bitrate 20000 -fps 60 -unsupported -remote -rtp 127.0.0.1 5004 5005
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable janus.service moonlight-stream.service
systemctl start janus.service moonlight-stream.service

echo "[10/10] Configuring firewall and SSL..."
notify_webhook "provisioning" "security_setup" "Configuring firewall and SSL"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 5004:5005/udp
ufw allow 7088/tcp
ufw allow 8088/tcp
ufw allow 10000-10200/udp
ufw --force enable

mkdir -p /etc/letsencrypt
curl -s {letsencrypt_options_url} > /etc/letsencrypt/options-ssl-nginx.conf
curl -s {ssl_dhparams_url} > /etc/letsencrypt/ssl-dhparams.pem

notify_webhook "provisioning" "ssl_setup" "Requesting SSL certificates"
certbot --nginx -d "${{DOMAIN_NAME}}" --staging --agree-tos --email "${{ADMIN_EMAIL}}" --redirect --no-eff-email

rm -f /etc/nginx/sites-enabled/default

cat > /etc/nginx/sites-available/moonlightembed <<EOF
server {{
    listen 80;
    server_name {DOMAIN_NAME};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {DOMAIN_NAME};

    ssl_certificate /etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN_NAME}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {{
        proxy_pass http://localhost:8088;
        proxy_set_header Host \$host;
    }}

    location /janus-ws {{
        proxy_pass http://localhost:7088;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }}

    client_max_body_size 1024M;
}}
EOF

ln -sf /etc/nginx/sites-available/moonlightembed /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

notify_webhook "completed" "finished" "Setup completed successfully"

echo "============================================================"
echo "✅ Moonlight to Browser Streaming Setup Complete!"
echo "============================================================"
echo ""
echo "🌐 Connection Information:"
echo "------------------------------------------------------------"
echo "🔗 Moonlight PIN Service: https://pin.{DOMAIN_NAME}"
echo "🔑 PIN: {ADMIN_PASSWORD}"
echo "------------------------------------------------------------"
echo ""
echo "🎥 Streaming Access:"
echo "------------------------------------------------------------"
echo "1. Open https://{DOMAIN_NAME}/janus/streaming/test.html"
echo "2. Use these settings:"
echo "   - Video: H.264"
echo "   - Audio: Opus"
echo "   - Port: 5004"
echo "   - Secret: moonlightstream"
echo "------------------------------------------------------------"
echo ""
echo "⚙️ Service Status Commands:"
echo "------------------------------------------------------------"
echo "Janus Gateway: systemctl status janus.service"
echo "Moonlight Stream: systemctl status moonlight-stream.service"
echo "Nginx: systemctl status nginx"
echo "------------------------------------------------------------"
echo ""
echo "🔧 IMPORTANT Setup Notes:"
echo "------------------------------------------------------------"
echo "1. On your Windows 10 machine:"
echo "   - Install Sunshine from https://github.com/LizardByte/Sunshine"
echo "   - Use PIN: {ADMIN_PASSWORD} when pairing"
echo "2. The stream will be available at the Janus test page"
echo "============================================================"
'''
    return script_template