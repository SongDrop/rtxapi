def generate_setup(DOMAIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT, PC_HOST, PIN_URL, VOLUME_DIR="/opt/moonlight-embed"):
    SERVICE_USER = "moonlightembedded"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"

    script_template = f'''#!/bin/bash

set -e

# === User config ===
DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
FRONTEND_PORT={FRONTEND_PORT}
BACKEND_PORT={BACKEND_PORT}
PC_HOST="{PC_HOST}"
PIN_URL="{PIN_URL}"
INSTALL_DIR="{VOLUME_DIR}"
LOG_DIR="${{INSTALL_DIR}}/logs"
DOCKER_IMAGE_NAME="moonlight-embed-app"
DOCKER_CONTAINER_NAME="moonlight-embed-container"
JANUS_INSTALL_DIR="/opt/janus"

# === Validate domain format ===
if ! [[ "${{DOMAIN_NAME}}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain format"
    exit 1
fi

echo "[1/10] Updating system and installing dependencies..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \\
    curl git nginx certbot python3-certbot-nginx \\
    nodejs npm docker.io ufw build-essential cmake autoconf automake libtool pkg-config gengetopt \\
    libmicrohttpd-dev libjansson-dev libssl-dev libsrtp2-dev libsofia-sip-ua-dev libglib2.0-dev \\
    libopus-dev libogg-dev libcurl4-openssl-dev liblua5.3-dev libconfig-dev libnanomsg-dev

# Install Node.js 20 if not available or wrong version
if ! command -v node &> /dev/null || [[ "$(node -v)" != v20* ]]; then
    echo "Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Enable and start Docker service
systemctl start docker || true
systemctl enable docker || true

echo "[2/10] Setting up installation directory..."
mkdir -p "${{INSTALL_DIR}}"
mkdir -p "${{LOG_DIR}}"
cd "${{INSTALL_DIR}}"

# Clone or update Moonlight Embed repo
if [ ! -d ".git" ]; then
    echo "Cloning Moonlight Embed repo..."
    git clone https://github.com/your/moonlight-embed.git .
else
    echo "Pulling latest changes..."
    git pull
fi

echo "[3/10] Creating Dockerfile..."

cat > "${{INSTALL_DIR}}/Dockerfile" <<EOF
FROM node:20-slim

WORKDIR /app

COPY . .

RUN npm install
RUN npm run build

EXPOSE {BACKEND_PORT} {FRONTEND_PORT} 8889 8890  # Include ports for WebRTC signaling

CMD ["npm", "start"]
EOF

echo "[4/10] Building Docker image..."
docker build -t ${{DOCKER_IMAGE_NAME}} "${{INSTALL_DIR}}"

echo "[5/10] Stopping existing container if any..."
docker stop ${{DOCKER_CONTAINER_NAME}} || true
docker rm ${{DOCKER_CONTAINER_NAME}} || true

echo "[6/10] Starting Docker container..."
docker run -d --name ${{DOCKER_CONTAINER_NAME}} \\
    -p {BACKEND_PORT}:{BACKEND_PORT} \\
    -p {FRONTEND_PORT}:{FRONTEND_PORT} \\
    -p 8889:8889 \\
    -p 8890:8890 \\
    ${{DOCKER_IMAGE_NAME}}

echo "[7/10] Setting up systemd service for Moonlight Embed container..."

cat > /etc/systemd/system/moonlight-embed.service <<EOF
[Unit]
Description=Moonlight Embed Docker Container
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker start -a {{}DOCKER_CONTAINER_NAME}
ExecStop=/usr/bin/docker stop -t 10 {{}DOCKER_CONTAINER_NAME}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable moonlight-embed.service
systemctl start moonlight-embed.service

echo "[8/10] Installing and building Janus Gateway and dependencies..."

# Clone and install libnice (recommended latest)
if [ ! -d "/tmp/libnice" ]; then
    git clone https://gitlab.freedesktop.org/libnice/libnice /tmp/libnice
    cd /tmp/libnice
    ./autogen.sh
    ./configure --prefix=/usr
    make && make install
fi

# Install libsrtp (v2.2.0)
if [ ! -d "/tmp/libsrtp-2.2.0" ]; then
    cd /tmp
    wget https://github.com/cisco/libsrtp/archive/v2.2.0.tar.gz
    tar xfv v2.2.0.tar.gz
    cd libsrtp-2.2.0
    ./configure --prefix=/usr --enable-openssl
    make shared_library && make install
fi

# Install usrsctp
if [ ! -d "/tmp/usrsctp" ]; then
    cd /tmp
    git clone https://github.com/sctplab/usrsctp
    cd usrsctp
    ./bootstrap
    ./configure --prefix=/usr
    make && make install
fi

# Install libwebsockets
if [ ! -d "/tmp/libwebsockets" ]; then
    cd /tmp
    git clone https://github.com/warmcat/libwebsockets.git
    cd libwebsockets
    git checkout v2.4-stable
    mkdir build
    cd build
    cmake -DLWS_MAX_SMP=1 -DCMAKE_INSTALL_PREFIX:PATH=/usr -DCMAKE_C_FLAGS="-fpic" ..
    make && make install
fi

# Clone Janus Gateway and build
if [ ! -d "{JANUS_INSTALL_DIR}" ]; then
    git clone https://github.com/meetecho/janus-gateway.git /tmp/janus-gateway
    cd /tmp/janus-gateway
    sh autogen.sh
    ./configure --prefix={JANUS_INSTALL_DIR}
    make
    make install
    make configs
fi

echo "[9/10] Setting up systemd service for Janus Gateway..."

cat > /etc/systemd/system/janus.service <<EOF
[Unit]
Description=Janus WebRTC Server
After=network.target

[Service]
Type=simple
User=root
ExecStart={JANUS_INSTALL_DIR}/bin/janus
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable janus.service
systemctl start janus.service

echo "[10/10] Configuring firewall..."

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow {FRONTEND_PORT}/tcp
ufw allow {BACKEND_PORT}/tcp
ufw allow 8889/tcp
ufw allow 8890/tcp
# Janus default ports, adjust if needed
ufw allow 7088/tcp
ufw allow 8088/tcp
ufw --force enable

echo "[11/11] Setting up SSL certificate..."

mkdir -p /etc/letsencrypt
curl -s {letsencrypt_options_url} > /etc/letsencrypt/options-ssl-nginx.conf
curl -s {ssl_dhparams_url} > /etc/letsencrypt/ssl-dhparams.pem

certbot --nginx -d "${{DOMAIN_NAME}}" --staging --agree-tos --email "${{ADMIN_EMAIL}}" --redirect --no-eff-email

echo "Configuring nginx..."

rm -f /etc/nginx/sites-enabled/default

cat > /etc/nginx/sites-available/moonlightembed <<EOF
map $http_upgrade $connection_upgrade {{
    default upgrade;
    '' close;
}}

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

    location /ws {{
        proxy_pass http://localhost:{BACKEND_PORT}/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }}

    location /api {{
        proxy_pass http://localhost:{BACKEND_PORT}/api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_buffering off;
        proxy_request_buffering off;
    }}

    location / {{
        proxy_pass http://localhost:{FRONTEND_PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
    }}

    # WebRTC signaling ports proxy (adjust if your app uses different ports)
    location /wssignaling/ {{
        proxy_pass http://localhost:8889/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_buffering off;
    }}

    location /webrtc/ {{
        proxy_pass http://localhost:8890/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_buffering off;
    }}

    # Janus admin and streaming plugin ports (default HTTP and HTTPS ports)
    location /janus/ {{
        proxy_pass http://localhost:8088/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_buffering off;
    }}

    location /janusws/ {{
        proxy_pass http://localhost:7088/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_buffering off;
    }}

    client_max_body_size 1024M;
}}
EOF

ln -sf /etc/nginx/sites-available/moonlightembed /etc/nginx/sites-enabled/

nginx -t && systemctl restart nginx

echo "============================================"
echo "✅ Moonlight Embed and Janus Gateway Setup Complete!"
echo ""
echo "🔗 Access your app at: https://{DOMAIN_NAME}"
echo ""
echo "⚙️ Service Status:"
echo "   - Moonlight Embed Docker container: docker ps --filter name={DOCKER_CONTAINER_NAME}"
echo "   - Janus Gateway service: systemctl status janus"
echo "   - Nginx: systemctl status nginx"
echo ""
echo "📜 Logs:"
echo "   - Moonlight Embed Docker logs: docker logs -f {DOCKER_CONTAINER_NAME}"
echo "   - Janus logs: journalctl -u janus -f"
echo "   - Nginx logs: journalctl -u nginx -f"
echo ""
echo "🔑 IMPORTANT:"
echo " - Your PC host for streaming is set to: {PC_HOST}"
echo " - To start streaming, visit the PIN URL to get or enter the PIN:"
echo "   {PIN_URL}"
echo " - Once PIN is entered, Moonlight Embed will connect to your PC for streaming."
echo " - Janus Gateway is installed and running to handle WebRTC streaming."
echo "============================================"
'''
    return script_template