def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    FRONTEND_PORT=3000,
    BACKEND_PORT=8000,
    REACT_APP_APP_NAME='AI Chat Assistant',
    REACT_APP_APP_LOGO='https://vhdvm.blob.core.windows.net/vhdvm/gitgpt.svg',
    VECTOR_SEARCH_ENABLED='false',
    VECTOR_SEARCH_ENDPOINT='your-search-index-endpoint',
    VECTOR_SEARCH_INDEX='your-search-index-name',
    VECTOR_SEARCH_KEY='your-search-index-ky',
    VECTOR_SEARCH_SEMANTIC_CONFIG='azureml-default',
    VECTOR_SEARCH_EMBEDDING_DEPLOYMENT='text-embedding-ada-002',
    VECTOR_SEARCH_EMBEDDING_ENDPOINT='text-embedding-endpoint',
    VECTOR_SEARCH_EMBEDDING_KEY='text-embedding-key',
    VECTOR_SEARCH_STORAGE_ENDPOINT='vector-search-endpoint',
    VECTOR_SEARCH_STORAGE_ACCESS_KEY='vector-search-key',
    VECTOR_SEARCH_STORAGE_CONNECTION_STRING='vector-search-connection-string',
    OPENAI_API_BASE="gpt-api-url",
    OPENAI_API_KEY="gpt-api-key",
    OPENAI_DEPLOYMENT_NAME="gpt-4.1-mini",
    OPENAI_API_VERSION="2025-01-01-preview",
    GPT_IMAGE_URL="gpt-image-url",
    GPT_IMAGE_KEY="gpt-image-key",
    GPT_IMAGE_VERSION="2025-04-01-preview"
):
    # URLs for certbot stuff, etc.
    gpt_repo = "https://github.com/SongDrop/gpt.git"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"

    MAX_UPLOAD_FILE_SIZE_IN_MB = 1024
    INSTALL_DIR = "/opt/gpt"
    LOG_DIR = f"{INSTALL_DIR}/logs"

    script_template = f"""#!/bin/bash

set -e

# Validate domain
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: Invalid domain format"
    exit 1
fi

# Configuration
DOMAIN_NAME="{DOMAIN_NAME}"
INSTALL_DIR="{INSTALL_DIR}"
LOG_DIR="{LOG_DIR}"
GPT_REPO="{gpt_repo}"

# ========== SYSTEM SETUP ==========
echo "[1/9] System updates and dependencies..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \\
    curl git nginx certbot \\
    python3-pip python3-venv jq make net-tools \\
    python3-certbot-nginx \\
    nodejs npm docker.io

# Install Node.js 20 if not available
if ! command -v node &> /dev/null || [[ "$(node -v)" != v20* ]]; then
    echo "Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Start Docker service (for systems with systemd)
systemctl start docker || true
systemctl enable docker || true

# ========== REPOSITORY SETUP ==========
echo "[2/9] Setting up GPT repository..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [ -d ".git" ]; then
    echo "Existing repository found, pulling latest changes..."
    git pull
elif [ -z "$(ls -A .)" ]; then
    echo "Cloning fresh repository..."
    git clone "$GPT_REPO" .
else
    echo "Directory not empty and not a git repo. Moving contents to backup..."
    mkdir -p ../gpt_backup
    mv * ../gpt_backup/ || true
    git clone "$GPT_REPO" .
fi

# ========== GENERATE DOCKERFILE ==========
echo "[3/9] Creating Dockerfile..."

cat > "$INSTALL_DIR/Dockerfile" <<EOF
# Base image
FROM python:3.10-slim

# Install system dependencies,  procps for pkill/pgrep, curl
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    libmagic-dev \
    poppler-utils \
    unzip \
    procps \
    gnupg \
    python3-venv \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy all files into container
COPY . .

# Create backend/.env file
# Ensure backend and frontend folders exist
RUN mkdir -p /app/backend /app/frontend

# Create backend/.env
RUN printf "#Backend Configuration\\n\
APP_NAME{REACT_APP_APP_NAME}\\n\
ENVIRONMENT=production\\n\
# OpenAI API Configuration\\n\
OPENAI_API_BASE={OPENAI_API_BASE}\\n\
OPENAI_API_KEY={OPENAI_API_KEY}\\n\
OPENAI_DEPLOYMENT_NAME={OPENAI_DEPLOYMENT_NAME}\\n\
OPENAI_API_VERSION={OPENAI_API_VERSION}\\n\
CORS_ORIGINS=http://localhost:{FRONTEND_PORT}\\n\
OPENAI_TEMPERATURE=0.7\\n\
OPENAI_MAX_TOKENS=4000\\n\
OPENAI_TOP_P=0.95\\n\
OPENAI_FREQUENCY_PENALTY=0\\n\
OPENAI_PRESENCE_PENALTY=0\\n\
# Vector Search Configuration\\n\
VECTOR_SEARCH_ENABLED={VECTOR_SEARCH_ENABLED}\\n\
VECTOR_SEARCH_ENDPOINT={VECTOR_SEARCH_ENDPOINT}\\n\
VECTOR_SEARCH_KEY={VECTOR_SEARCH_KEY}\\n\
VECTOR_SEARCH_INDEX={VECTOR_SEARCH_INDEX}\\n\
VECTOR_SEARCH_SEMANTIC_CONFIG={VECTOR_SEARCH_SEMANTIC_CONFIG}\\n\
VECTOR_SEARCH_EMBEDDING_DEPLOYMENT={VECTOR_SEARCH_EMBEDDING_DEPLOYMENT}\\n\
VECTOR_SEARCH_EMBEDDING_ENDPOINT={VECTOR_SEARCH_EMBEDDING_ENDPOINT}\\n\
VECTOR_SEARCH_EMBEDDING_KEY={VECTOR_SEARCH_EMBEDDING_KEY}\\n\
# Vector Search Storage\\n\
VECTOR_SEARCH_STORAGE_ENDPOINT={VECTOR_SEARCH_STORAGE_ENDPOINT}\\n\
VECTOR_SEARCH_STORAGE_ACCESS_KEY={VECTOR_SEARCH_STORAGE_ACCESS_KEY}\\n\
VECTOR_SEARCH_STORAGE_CONNECTION_STRING={VECTOR_SEARCH_STORAGE_CONNECTION_STRING}\\n\
# Server Configuration\\n\
HOST=0.0.0.0\\n\
PORT={BACKEND_PORT}\\n\
CORS_ORIGINS=http://localhost:{FRONTEND_PORT},http://localhost:{BACKEND_PORT},https://{DOMAIN_NAME}, wss://{DOMAIN_NAME}/ws\\n\
\\n\
SYSTEM_PROMPT=\\"You are an AI assistant. You aim to be helpful, honest, and direct in your interactions.\\"\\n" > /app/backend/.env

# Create frontend/.env
RUN printf "#Frontend Configuration\\n\
REACT_APP_API_URL=https://{DOMAIN_NAME}\\n\
REACT_APP_WS_URL=wss://{DOMAIN_NAME}/ws\\n\
WDS_SOCKET_PORT=0\\n\
REACT_APP_APP_NAME={REACT_APP_APP_NAME}\\n\
REACT_APP_APP_LOGO={REACT_APP_APP_LOGO}\\n\
NODE_ENV=production\\n\
REACT_APP_PASSWORD={ADMIN_PASSWORD}\\n\
REACT_APP_GPT_IMAGE_URL={GPT_IMAGE_URL}\\n\
REACT_APP_GPT_IMAGE_KEY={GPT_IMAGE_KEY}\\n\
REACT_APP_GPT_IMAGE_VERSION={GPT_IMAGE_VERSION}\\n" > /app/frontend/.env

######IF YOU RUN IT ON LOCALHOST#####################
#REACT_APP_API_URL=http://localhost:{BACKEND_PORT}\\n\
#REACT_APP_WS_URL=ws://localhost:{BACKEND_PORT}/ws\\n\
######IF YOU RUN IT ON DOMAIN ws->wss
#REACT_APP_API_URL=https://{DOMAIN_NAME}\\n\
#REACT_APP_WS_URL=wss://{DOMAIN_NAME}/ws\\n\
######################################################

# Ensure install.sh is executable
RUN chmod +x ./docker_install.sh

# Run install-only mode for dependency install
RUN ./docker_install.sh install-only

# Expose backend port
EXPOSE 8000 3000

RUN chmod +x ./docker_restart_services.sh
RUN chmod +x ./docker_refresh_github.sh

# Default run command
# Use restart_services.sh as the container's default command
CMD ["./docker_restart_services.sh"]

EOF

echo "[4/9] Building Docker image..."
docker build -t gpt-app "$INSTALL_DIR"

echo "[5/9] Stopping existing container if any..."
docker stop gpt-container || true
docker rm gpt-container || true

echo "[6/9] Starting Docker container..."
docker run -d --name gpt-container -p {BACKEND_PORT}:{BACKEND_PORT} -p {FRONTEND_PORT}:{FRONTEND_PORT} gpt-app

# Create systemd service to manage the Docker container
echo "[7/9] Creating systemd service for Docker container..."

cat > /etc/systemd/system/gpt-docker.service <<EOF
[Unit]
Description=GPT Docker Container
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker start -a gpt-container
ExecStop=/usr/bin/docker stop -t 10 gpt-container

[Install]
WantedBy=multi-user.target
EOF

# Enable and start Docker service
systemctl daemon-reload
systemctl enable gpt-docker.service
systemctl start gpt-docker.service

# ========== LOGS DIRECTORY ==========
echo "[8/9] Creating logs directory..."
mkdir -p "$LOG_DIR"

# ========== NETWORK SECURITY ==========
echo "[9/9] Configuring firewall..."
ufw allow 22/tcp 
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow {FRONTEND_PORT}/tcp
ufw allow {BACKEND_PORT}/tcp
ufw --force enable

# ========== SSL CERTIFICATE ==========
echo "[10/10] Setting up SSL certificate..."

# Download Let's Encrypt configuration files
mkdir -p /etc/letsencrypt
curl -s "{letsencrypt_options_url}" > /etc/letsencrypt/options-ssl-nginx.conf
curl -s "{ssl_dhparams_url}" > /etc/letsencrypt/ssl-dhparams.pem

# Real certificate issuance (commented out)
certbot --nginx -d "{DOMAIN_NAME}" --non-interactive --agree-tos --email "{ADMIN_EMAIL}" --redirect

# Staging/testing certificate issuance (active command)
#certbot --nginx -d "{DOMAIN_NAME}" --staging --agree-tos --email "{ADMIN_EMAIL}" --redirect --no-eff-email

# ========== NGINX CONFIG ==========
echo "[11/11] Configuring Nginx..."

# Remove default Nginx config
rm -f /etc/nginx/sites-enabled/default

# Create GPT config
cat > /etc/nginx/sites-available/gpt <<EOF
map \$http_upgrade \$connection_upgrade {{
    default upgrade;
    '' close;
}}

server {{
    listen 80;
    server_name {DOMAIN_NAME};
    return 301 https://\$host\$request_uri;
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
        proxy_set_header Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_http_version 1.1;
    }}

    location /chat {{
        proxy_pass http://localhost:{BACKEND_PORT}/chat;
        proxy_set_header Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_http_version 1.1;
    }}
    
    location /api {{
        proxy_pass http://localhost:{BACKEND_PORT}/api;
        proxy_set_header Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_http_version 1.1;
    }}

    client_max_body_size {MAX_UPLOAD_FILE_SIZE_IN_MB}M;

    location / {{
        proxy_pass http://localhost:{FRONTEND_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
    }}
}}
EOF

ln -sf /etc/nginx/sites-available/gpt /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# ========== VERIFICATION ==========
echo "Verifying setup..."

# Verify Docker container is running
if ! docker ps --filter "name=gpt-container" --filter "status=running" | grep -q gpt-container; then
    echo "ERROR: Docker container gpt-container is not running!"
    docker logs gpt-container || true
    exit 1
fi

# Verify Nginx config
if ! nginx -t; then
    echo "ERROR: Nginx configuration test failed"
    exit 1
fi

# Verify SSL certificate
if [ ! -f "/etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem" ]; then
    echo "ERROR: SSL certificate not found!"
    exit 1
fi

echo "============================================"
echo "✅ GPT Setup Complete!"
echo ""
echo "🔗 Access: https://{DOMAIN_NAME}"
echo ""
echo "⚙️ Service Status:"
echo "   - Docker container: docker ps --filter name=gpt-container"
echo "   - Nginx: systemctl status nginx"
echo ""
echo "📜 Logs:"
echo "   - Docker container logs: docker logs -f gpt-container"
echo "   - Nginx: journalctl -u nginx -f"
echo ""
echo "⚠️ Important:"
echo "1. First-time setup may require visiting https://{DOMAIN_NAME} to complete installation"
echo "2. To update: cd {INSTALL_DIR} && git pull && docker restart gpt-container"
echo "============================================"
"""
    return script_template