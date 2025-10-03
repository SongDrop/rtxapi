import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PORT,
    VOLUME_DIR="/opt/code-server",
    WEBHOOK_URL="",
    location="",
    resource_group=""
):
    """
    Returns a full bash provisioning script as a string.
    Usage: script = generate_setup("example.com", "admin@example.com", "P@ssw0rd", "8080", ...)
    """
    # Tokens used inside the template (won't conflict with normal bash syntax)
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__ADMIN_PASSWORD__": ADMIN_PASSWORD,
        "__PORT__": str(PORT),
        "__VOLUME_DIR__": VOLUME_DIR,
        "__SERVICE_USER__": "coder",
        "__LET_OPTIONS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf",
        "__SSL_DHPARAMS_URL__": "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem",
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__WEBHOOK_URL__": WEBHOOK_URL,
    }

    # Extensions array
    extensions = [
        "ms-azuretools.vscode-azureappservice",
        "ms-azuretools.vscode-azurefunctions",
        "ms-azuretools.vscode-azureresourcegroups",
        "ms-azuretools.vscode-docker",
        "ms-azuretools.vscode-containers",
        "ms-azuretools.vscode-azurestaticwebapps",
        "ms-azuretools.vscode-azurite",
        "ms-azuretools.vscode-cosmosdb",
        "ms-kubernetes-tools.vscode-kubernetes-tools",
        "hashicorp.terraform",
        "azurerm-tools.azurerm-vscode-tools",
        "ms-python.python",
        "ms-python.debugpy",
        "ms-toolsai.jupyter",
        "ms-toolsai.jupyter-keymap",
        "ms-toolsai.vscode-jupyter-cell-tags",
        "ms-toolsai.vscode-jupyter-slideshow",
        "ms-toolsai.jupyter-renderers",
        "ms-vscode.powershell",
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "eamodio.gitlens",
        "redhat.vscode-yaml",
        "ritwickdey.liveserver",
        "formulahendry.code-runner",
        "humao.rest-client",
        "streetsidesoftware.code-spell-checker",
        "wallabyjs.quokka-vscode",
        "donjayamanne.githistory",
        "github.copilot"
    ]

    ext_block = "\n".join([f'    "{ext}"' for ext in extensions])
    # Bash template using tokens; tokens will be replaced below to avoid f-string brace problems.
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # Code Server Provisioning Script (generated)
    # ----------------------------------------------------------------------

    # --- helper: webhook notification (inlined if provided) ---
    __WEBHOOK_FUNCTION__

    # If any command later fails we will report it
    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # Logging
    LOG_FILE="/var/log/code-server-install.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    echo "[1/20] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating inputs"

    # Basic validation
    DOMAIN="__DOMAIN__"
    PORT="__PORT__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    ADMIN_PASSWORD="__ADMIN_PASSWORD__"
    VOLUME_DIR="__VOLUME_DIR__"
    SERVICE_USER="__SERVICE_USER__"

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

    # Check running port and attempt to free it
    echo "[2/20] Checking for port conflicts..."
    notify_webhook "provisioning" "port_check" "Checking port $PORT"
    
    # Improved port conflict resolution
    PORT_IN_USE=false
    if command -v ss >/dev/null 2>&1; then
        if ss -tuln 2>/dev/null | awk '{print $4}' | grep -q ":$PORT$"; then
            PORT_IN_USE=true
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln 2>/dev/null | awk '{print $4}' | grep -q ":$PORT$"; then
            PORT_IN_USE=true
        fi
    fi

    if [ "$PORT_IN_USE" = true ]; then
        echo "WARNING: Port $PORT is in use; attempting to free..."
        
        # More aggressive process termination
        echo "Stopping code-server service if running..."
        systemctl stop "code-server@$SERVICE_USER" 2>/dev/null || true
        systemctl disable "code-server@$SERVICE_USER" 2>/dev/null || true
        
        echo "Killing any processes using port $PORT..."
        # Find and kill processes using the port
        if command -v lsof >/dev/null 2>&1; then
            lsof -ti:"$PORT" | xargs -r kill -9 2>/dev/null || true
        elif command -v fuser >/dev/null 2>&1; then
            fuser -k "$PORT"/tcp 2>/dev/null || true
        else
            # Fallback method
            pkill -f "code-server" 2>/dev/null || true
            pkill -f "node.*$PORT" 2>/dev/null || true
        fi
        
        sleep 3
        
        # Verify port is free
        PORT_STILL_IN_USE=false
        if command -v ss >/dev/null 2>&1 && ss -tuln 2>/dev/null | awk '{print $4}' | grep -q ":$PORT$"; then
            PORT_STILL_IN_USE=true
        elif command -v netstat >/dev/null 2>&1 && netstat -tuln 2>/dev/null | awk '{print $4}' | grep -q ":$PORT$"; then
            PORT_STILL_IN_USE=true
        fi
        
        if [ "$PORT_STILL_IN_USE" = true ]; then
            echo "WARNING: Port $PORT still in use, but continuing anyway..."
            notify_webhook "warning" "port_conflict" "Port $PORT still in use, continuing"
        else
            echo "Successfully freed port $PORT"
        fi
    fi

    # ========== SYSTEM UPDATE & DEPENDENCIES ==========
    echo "[3/20] Updating system and installing base dependencies..."
    notify_webhook "provisioning" "system_update" "Updating apt and installing packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get upgrade -y -q
    apt-get install -y -q \
      curl wget gnupg2 lsb-release ca-certificates apt-transport-https \
      nginx certbot python3-certbot-nginx ufw git build-essential sudo cron \
      python3 python3-pip jq software-properties-common gnupg2

    # Create service user if missing
    if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
        echo "[4/20] Creating service user: $SERVICE_USER"
        notify_webhook "provisioning" "create_user" "Creating $SERVICE_USER"
        useradd -m -s /bin/bash "$SERVICE_USER"
        echo "$SERVICE_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/"$SERVICE_USER"
        chmod 440 /etc/sudoers.d/"$SERVICE_USER"
    fi

    # ========== NODE.JS (LTS) ==========
    echo "[5/20] Installing Node.js LTS (20.x)..."
    notify_webhook "provisioning" "nodejs" "Installing Node.js"
    apt-get remove -y nodejs npm || true
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -q nodejs
    NODE_VERSION=$(node --version 2>/dev/null || echo "none")
    echo "Node.js version: $NODE_VERSION"
    npm install -g npm@latest --no-progress

    # Install useful global npm tools (non-fatal)
    echo "[6/20] Installing global npm tools (yarn, netlify-cli)..."
    notify_webhook "provisioning" "npm_tools" "Installing npm CLI tools"
    npm install -g yarn --no-progress || true
    npm install -g netlify-cli --no-progress || true

    # ========== PYENV and Python (root and service user) ==========
    echo "[7/20] Installing pyenv for root and $SERVICE_USER..."
    notify_webhook "provisioning" "pyenv" "Installing pyenv and Python 3.9.7"
    # install build deps
    apt-get install -y -q make build-essential libssl-dev zlib1g-dev \
      libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
      libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev || true

    export HOME=/root
    if [ -d "$HOME/.pyenv" ]; then
        echo "Updating existing pyenv for root..."
        cd "$HOME/.pyenv" && git pull || true
    else
        curl -fsSL https://pyenv.run | bash || true
    fi

    # add pyenv to current shell
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    if command -v pyenv >/dev/null 2>&1; then
        eval "$(pyenv init --path)" || true
        eval "$(pyenv init -)" || true
    fi

    if ! pyenv versions --bare 2>/dev/null | grep -q '^3.9.7$'; then
        pyenv install -s 3.9.7 || true
    fi
    pyenv global 3.9.7 || true
    echo "Python version: $(python --version 2>&1 || echo 'unknown')"

    # Install pyenv for service user (non-fatal)
    su - "$SERVICE_USER" -c 'if [ ! -d "$HOME/.pyenv" ]; then curl -fsSL https://pyenv.run | bash || true; fi'

    # ========== ELECTRON dependencies (optional, non-fatal) ==========
    echo "[8/20] Installing Electron dependencies (optional)..."
    notify_webhook "provisioning" "electron" "Installing Electron libs"
    apt-get install -y -q libgtk-3-0 libnotify4 libnss3 libxss1 libasound2-data \
      libasound2-plugins libxtst6 xauth xvfb || true

    # ========== DOCKER ==========
    echo "[9/20] Installing Docker..."
    notify_webhook "provisioning" "docker" "Installing Docker"
    curl -fsSL https://get.docker.com | sh || true
    usermod -aG docker "$SERVICE_USER" || true

    # ========== KUBECTL ==========
    echo "[10/20] Installing kubectl..."
    notify_webhook "provisioning" "kubectl" "Installing kubectl"
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" || true
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl || true
    rm -f kubectl || true

    # ========== TERRAFORM ==========
    echo "[11/20] Installing Terraform..."
    notify_webhook "provisioning" "terraform" "Installing Terraform"
    curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor --batch --yes -o /usr/share/keyrings/hashicorp.gpg || true
    echo "deb [signed-by=/usr/share/keyrings/hashicorp.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" > /etc/apt/sources.list.d/hashicorp.list || true
    apt-get update -q && apt-get install -y -q terraform || true

    # ========== INSTALL & CONFIGURE CODE-SERVER ==========
    echo "[12/20] Installing code-server..."
    notify_webhook "provisioning" "code_server" "Installing code-server"

    # Run official installer
    curl -fsSL https://code-server.dev/install.sh -o /tmp/install-code-server.sh
    chmod +x /tmp/install-code-server.sh
    if ! bash /tmp/install-code-server.sh; then
        echo "⚠️ code-server installer failed, continuing for debugging"
        notify_webhook "warning" "code_server" "Installer failed, continuing"
    fi

    # Detect code-server binary
    CODE_BIN=$(command -v code-server || true)
    if [ -z "$CODE_BIN" ]; then
        for path in /usr/local/bin/code-server /usr/bin/code-server /opt/code-server/bin/code-server /home/$SERVICE_USER/.local/bin/code-server; do
            if [ -x "$path" ]; then
                CODE_BIN="$path"
                echo "Found code-server binary at $CODE_BIN"
                notify_webhook "provisioning" "code_server" "Found binary at $CODE_BIN"
                break
            fi
        done
    fi

    if [ -z "$CODE_BIN" ]; then
        echo "❌ code-server binary not found! Check installer logs"
        notify_webhook "failed" "code_server" "Binary not found after install"
        exit 1
    fi

    if ! "$CODE_BIN" --version >/dev/null 2>&1; then
        echo "❌ code-server binary invalid"
        notify_webhook "failed" "code_server" "Binary check failed"
        exit 1
    fi

    echo "✅ code-server installed at $CODE_BIN"
    notify_webhook "provisioning" "code_server" "Verified binary at $CODE_BIN"

    # Setup directories
    CONFIG_DIR="/home/$SERVICE_USER/.config/code-server"
    DATA_DIR="/home/$SERVICE_USER/.local/share/code-server"
    EXT_DIR="$DATA_DIR/extensions"
    mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$EXT_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "/home/$SERVICE_USER/.config" "/home/$SERVICE_USER/.local"
    chmod 700 "$CONFIG_DIR" "$DATA_DIR" "$EXT_DIR"

    # Write config.yaml
    cat > "$CONFIG_DIR/config.yaml" << EOF
bind-addr: 127.0.0.1:__PORT__
auth: password
password: __ADMIN_PASSWORD__
cert: false
EOF
                                      
    chown "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR/config.yaml"
    chmod 600 "$CONFIG_DIR/config.yaml"

    # Ensure stable path for code-server binary
    ln -sf "$CODE_BIN" /usr/local/bin/code-server
    CODE_BIN="/usr/local/bin/code-server"

    # Create systemd service
    echo "[14/20] Creating systemd service..."
    notify_webhook "provisioning" "systemd" "Creating systemd unit"

    cat > /etc/systemd/system/code-server.service << EOF
[Unit]
Description=code-server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=/home/$SERVICE_USER
Environment=HOME=/home/$SERVICE_USER
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$CODE_BIN --config $CONFIG_DIR/config.yaml --user-data-dir $DATA_DIR --extensions-dir $EXT_DIR
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable code-server.service

    # Start service
    echo "[15/20] Starting code-server service..."
    notify_webhook "provisioning" "service_start" "Starting code-server service"
    systemctl restart code-server.service

    # Wait for readiness
    READY=false
    for i in {1..12}; do
        if curl -fsS http://127.0.0.1:__PORT__ >/dev/null 2>&1; then
            READY=true
            break
        fi
        echo "⏳ code-server not up yet (try $i/12)..."
        sleep 5
    done

    if [ "$READY" = false ]; then
        echo "❌ code-server failed to start!"
        systemctl status code-server.service --no-pager
        journalctl -u code-server.service -n 50 --no-pager
        notify_webhook "failed" "service_start" "code-server failed to start"
        exit 1
    fi

    echo "✅ code-server is running"
    notify_webhook "provisioning" "service_start" "✅ code-server is running"

    # Install VSCode extensions
    echo "[16/20] Installing VSCode extensions..."
    notify_webhook "provisioning" "extensions" "Installing VSCode extensions"

    extensions=(
        __EXTENSIONS__
    )

    install_extension() {
        local ext="$1"
        local max_attempts=2
        local attempt=1
        local installed=false

        is_installed() {
            sudo -u "$SERVICE_USER" HOME="/home/$SERVICE_USER" "$CODE_BIN" \
                --list-extensions | grep -q "^$ext\$"
        }

        echo "📦 Installing $ext..."
        notify_webhook "provisioning" "extension_install" "Installing $ext"

        if is_installed; then
            echo "✅ $ext already installed, skipping"
            notify_webhook "provisioning" "extension_skip" "$ext already installed"
            return 0
        fi

        # Try Open VSX (retry)
        while [ $attempt -le $max_attempts ] && [ "$installed" = false ]; do
            if sudo -u "$SERVICE_USER" HOME="/home/$SERVICE_USER" "$CODE_BIN" \
                --install-extension "$ext" \
                --extensions-dir="$EXT_DIR" \
                --user-data-dir="$DATA_DIR" --force 2>/dev/null; then
                installed=true
            else
                echo "⚠️ Attempt $attempt failed for $ext"
                attempt=$((attempt + 1))
                sleep 2
            fi
        done

        # Marketplace fallback
        if [ "$installed" = false ]; then
            local publisher=$(echo "$ext" | cut -d. -f1)
            local extension_name=$(echo "$ext" | cut -d. -f2)
            local url="https://marketplace.visualstudio.com/_apis/public/gallery/publishers/$publisher/vsextensions/$extension_name/latest/vspackage"
            local tmpfile=$(mktemp /tmp/extension.XXXXXX.vsix)
            if curl -fsSL -o "$tmpfile" "$url" && [ -s "$tmpfile" ]; then
                sudo -u "$SERVICE_USER" HOME="/home/$SERVICE_USER" "$CODE_BIN" \
                    --install-extension "$tmpfile" \
                    --extensions-dir="$EXT_DIR" \
                    --user-data-dir="$DATA_DIR" --force && installed=true
            fi
            rm -f "$tmpfile"
        fi

        # Verify
        if is_installed; then
            echo "✅ Verified $ext installation"
            notify_webhook "provisioning" "extension_verified" "$ext is installed"
        else
            echo "❌ Failed to install $ext, skipping"
            notify_webhook "warning" "extension_failed" "$ext installation failed"
        fi
    }

    for ext in "${extensions[@]}"; do
        install_extension "$ext"
    done

    # List installed extensions
    echo "📂 Installed extensions:"
    sudo -u "$SERVICE_USER" HOME="/home/$SERVICE_USER" "$CODE_BIN" --list-extensions

    # Ensure 'code' CLI symlink
    echo "[17/20] Ensuring 'code' symlink"
    notify_webhook "provisioning" "code_cli" "Configuring 'code' binary"
    if [ ! -L /usr/local/bin/code ] && [ ! -f /usr/local/bin/code ]; then
        ln -s "$CODE_BIN" /usr/local/bin/code
    fi

    echo "✅ code-server setup complete"
    notify_webhook "provisioning" "provisioning" "✅ code-server installed and ready"

    # ========== FIREWALL ==========
    echo "[17/20] Configuring UFW firewall (opens SSH/HTTP/HTTPS and code-server port)"
    notify_webhook "provisioning" "firewall" "Configuring UFW"
    if ! ufw status | grep -q inactive; then
        echo "UFW already active; adding rules"
    fi
    ufw allow 22/tcp 
    ufw allow 80/tcp 
    ufw allow 443/tcp
    ufw allow "$PORT"/tcp
    ufw --force enable

   # ========== NGINX CONFIG + SSL (merged from GPT Docker script) ==========
    echo "[18/20] Configuring nginx reverse proxy with SSL..."
    rm -f /etc/nginx/sites-enabled/default
    rm -f /etc/nginx/sites-available/code-server

    # Download Let's Encrypt recommended configs
    mkdir -p /etc/letsencrypt
    curl -s "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf" -o /etc/letsencrypt/options-ssl-nginx.conf
    curl -s "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem" -o /etc/letsencrypt/ssl-dhparams.pem

    # Initial temporary HTTP server for certbot
    cat > /etc/nginx/sites-available/code-server <<'EOF_TEMP'
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
                                      
    ln -sf /etc/nginx/sites-available/code-server /etc/nginx/sites-enabled/code-server
    nginx -t && systemctl restart nginx

    # Create webroot for certbot
    mkdir -p /var/www/html
    chown www-data:www-data /var/www/html

    # Obtain SSL certificate using certbot
    if ! certbot --nginx -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__"; then
        echo "⚠️ Certbot nginx plugin failed; trying webroot fallback"
        systemctl start nginx || true
        certbot certonly --webroot -w /var/www/html -d "__DOMAIN__" --non-interactive --agree-tos -m "__ADMIN_EMAIL__"
    fi

    # Verify certificate existence
    if [ ! -f "/etc/letsencrypt/live/__DOMAIN__/fullchain.pem" ]; then
        echo "❌ SSL certificate not found!"
        exit 1
    fi

    # Replace Nginx config with full HTTPS proxy for code-server
    cat > /etc/nginx/sites-available/code-server <<'EOF_SSL'
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
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF_SSL

    ln -sf /etc/nginx/sites-available/code-server /etc/nginx/sites-enabled/code-server
    nginx -t && systemctl reload nginx

    echo "[19/19] Setup Cron for renewal..."
    notify_webhook "provisioning" "provisioning" "Setup Cron for renewal..."
         
    # Setup cron for renewal (runs daily and reloads nginx on change)
    (crontab -l 2>/dev/null | grep -v -F "__CERTBOT_CRON__" || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
    
    # ========== FINAL CHECKS ==========
    echo "[20/20] Final verification..."
    notify_webhook "provisioning" "verification" "Performing verification checks"

    if ! nginx -t; then
        echo "ERROR: nginx config test failed"
        notify_webhook "failed" "verification" "Nginx config test failed"
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
                                      
    cat <<EOF_FINAL
=============================================
✅ Code Server Setup Complete!
---------------------------------------------
🔗 Access URL     : https://__DOMAIN__
👤 Admin password : __ADMIN_PASSWORD__
---------------------------------------------
⚙️ Useful commands
- Check status: systemctl status code-server@__SERVICE_USER__
- View logs   : journalctl -u code-server@__SERVICE_USER__ -f
- Restart     : systemctl restart code-server@__SERVICE_USER__
- Nginx status: systemctl status nginx
---------------------------------------------
⚠️ Post-install notes
1️⃣  First visit https://__DOMAIN__ to access your code server
2️⃣  To renew SSL certificates: certbot renew --quiet
3️⃣  Extensions installed in: __VOLUME_DIR__/data/extensions
---------------------------------------------
Enjoy your new code server!
=============================================
EOF_FINAL
    """)

    # Build webhook function snippet (inlined) or a stub
    if tokens["__WEBHOOK_URL__"]:
        # escape double quotes for JSON heredoc safe insertion
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

          # Send POST (show HTTP code)
          curl -s -X POST "__WEBHOOK_URL__" \
            -H "Content-Type: application/json" \
            -d "$JSON_PAYLOAD" \
            --connect-timeout 10 \
            --max-time 30 \
            --retry 2 \
            --retry-delay 5 \
            --write-out "Webhook result: %{http_code}\n" \
            --output /dev/null || true
        }
        """)
    else:
        webhook_fn = textwrap.dedent(r"""
        notify_webhook() {
          # Webhook disabled/stub
          return 0
        }
        """)

    # Now replace tokens inside script_template
    final = script_template.replace("__WEBHOOK_FUNCTION__", webhook_fn)

    # Replace the rest of simple tokens
    for tk, val in tokens.items():
        # Skip webhook_url token here because webhook_fn included it as placeholders
        if tk == "__WEBHOOK_URL__":
            continue
        final = final.replace(tk, val)

    # Replace webhook placeholders in webhook_fn portion (location/resource_group/webhook_url)
    final = final.replace("__LOCATION__", tokens["__LOCATION__"])
    final = final.replace("__RESOURCE_GROUP__", tokens["__RESOURCE_GROUP__"])
    final = final.replace("__WEBHOOK_URL__", tokens["__WEBHOOK_URL__"])
    final = final.replace("__LET_OPTIONS_URL__", tokens["__LET_OPTIONS_URL__"])
    final = final.replace("__SSL_DHPARAMS_URL__", tokens["__SSL_DHPARAMS_URL__"])

    # Replace CERTBOT_CRON token
    certbot_cron = "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
    final = final.replace("__CERTBOT_CRON__", certbot_cron)

    # Small safety: ensure files under VOLUME_DIR exist and are substituted
    final = final.replace("__VOLUME_DIR__", tokens["__VOLUME_DIR__"])

    # Replace extensions
    final = final.replace("__EXTENSIONS__", ext_block)
    # Replace remaining tokens for service user, password, admin email, domain, port
    final = final.replace("__SERVICE_USER__", tokens["__SERVICE_USER__"])
    final = final.replace("__ADMIN_PASSWORD__", tokens["__ADMIN_PASSWORD__"])
    final = final.replace("__ADMIN_EMAIL__", tokens["__ADMIN_EMAIL__"])
    final = final.replace("__DOMAIN__", tokens["__DOMAIN__"])
    final = final.replace("__PORT__", tokens["__PORT__"])

    # Return the final script string
    return final
