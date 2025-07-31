def generate_setup(DOMAIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT, PC_HOST, PIN_URL, VOLUME_DIR="/opt/ubuntu"):
    SERVICE_USER = "ubuntu"
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
 
echo "[10/10] Configuring firewall..."

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow {FRONTEND_PORT}/tcp
ufw allow {BACKEND_PORT}/tcp
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
    client_max_body_size 1024M;
}}
EOF

ln -sf /etc/nginx/sites-available/moonlightembed /etc/nginx/sites-enabled/

nginx -t && systemctl restart nginx

echo "============================================"
echo "✅ Setup Complete!"
echo ""
echo "🔗 Access your app at: https://{DOMAIN_NAME}"
echo ""
echo "============================================"
'''
    return script_template