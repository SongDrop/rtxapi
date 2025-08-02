def generate_setup(DOMAIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT, VM_IP, PIN_URL, VOLUME_DIR="/opt/moonlight-embed"):
    SERVICE_USER = "moonlightembed"
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

# === Validate domain format ===
if ! [[ "${{DOMAIN_NAME}}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain format"
    exit 1
fi

echo "[1/8] Updating system and installing dependencies..."
apt-get update
apt-get install -y --no-install-recommends \\
    curl git nginx certbot python3-certbot-nginx \\
    docker.io ufw build-essential cmake autoconf automake libtool pkg-config \\
    libmicrohttpd-dev libjansson-dev libssl-dev libsrtp2-dev libsofia-sip-ua-dev \\
    libglib2.0-dev libopus-dev libogg-dev libcurl4-openssl-dev libconfig-dev \\
    libavcodec-dev libavformat-dev libavutil-dev libswscale-dev

# Enable and start Docker service
systemctl start docker || true
systemctl enable docker || true

echo "[2/8] Setting up installation directory..."
mkdir -p "${{INSTALL_DIR}}"
mkdir -p "${{LOG_DIR}}"
cd "${{INSTALL_DIR}}"

echo "[3/8] Installing Moonlight Embedded..."
mkdir -p "${{MOONLIGHT_EMBEDDED_DIR}}"
if [ ! -d "${{MOONLIGHT_EMBEDDED_DIR}}/.git" ]; then
    git clone {github_url} "${{MOONLIGHT_EMBEDDED_DIR}}"
fi

cd "${{MOONLIGHT_EMBEDDED_DIR}}"
git pull
mkdir -p build
cd build
cmake .. && make -j$(nproc) && make install

echo "[4/8] Installing Janus Gateway and dependencies..."

# Install libnice
if [ ! -d "/tmp/libnice" ]; then
    git clone {libnice_git_url} /tmp/libnice
    cd /tmp/libnice
    ./autogen.sh
    ./configure --prefix=/usr
    make && make install
    cd -
fi

# Install Janus
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

echo "[5/8] Setting up systemd services..."

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

echo "[6/8] Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 5004:5005/udp  # Moonlight streaming ports
ufw allow 7088/tcp       # Janus WebSockets
ufw allow 8088/tcp       # Janus HTTP
ufw allow 10000-10200/udp # WebRTC ports
ufw --force enable

echo "[7/8] Setting up SSL certificate..."
mkdir -p /etc/letsencrypt
curl -s {letsencrypt_options_url} > /etc/letsencrypt/options-ssl-nginx.conf
curl -s {ssl_dhparams_url} > /etc/letsencrypt/ssl-dhparams.pem

certbot --nginx -d "${{DOMAIN_NAME}}" --staging --agree-tos --email "${{ADMIN_EMAIL}}" --redirect --no-eff-email

echo "[8/8] Configuring nginx..."
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

echo "============================================"
echo "✅ Moonlight to Browser Streaming Setup Complete!"
echo ""
echo "To access the stream:"
echo "1. Open https://{DOMAIN_NAME}/janus/streaming/test.html"
echo "2. Use these settings:"
echo "   - Video: H.264"
echo "   - Audio: Opus"
echo "   - Port: 5004"
echo "   - Secret: moonlightstream"
echo ""
echo "⚙️ Service Status:"
echo "   - Janus Gateway: systemctl status janus.service"
echo "   - Moonlight Stream: systemctl status moonlight-stream.service"
echo ""
echo "🔑 IMPORTANT:"
echo "1. On your Windows 10 machine:"
echo "   - Install Sunshine from https://github.com/LizardByte/Sunshine"
echo "   - Configure Sunshine with the same PIN shown at {PIN_URL}"
echo "2. The stream will be available at the Janus test page"
echo "============================================"
'''
    return script_template