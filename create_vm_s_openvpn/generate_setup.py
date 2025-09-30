def generate_openvpn_ssl_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    VPN_PORT=443,
    VPN_PROTOCOL="tcp",
    VPN_USER="vpnuser",
    VPN_PASSWORD="vpnpassword",
    WEBHOOK_URL="",
    location="",
    resource_group=""
):
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"

    if WEBHOOK_URL:
        webhook_notification = f'''
notify_webhook() {{
    local status="$1"
    local step="$2"
    local message="$3"
    if [ -z "${{WEBHOOK_URL}}" ]; then return 0; fi
    JSON_PAYLOAD=$(cat <<EOF
{{
  "vm_name": "$(hostname)",
  "status": "$status",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "location": "{location}",
  "resource_group": "{resource_group}",
  "details": {{
    "step": "$step",
    "message": "$message"
  }}
}}
EOF
    )
    curl -s -X POST "${{WEBHOOK_URL}}" -H "Content-Type: application/json" -d "$JSON_PAYLOAD" --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 5 --output /dev/null
}}
'''
    else:
        webhook_notification = 'notify_webhook() { return 0; }'

    script_template = f"""#!/bin/bash
set -e
set -o pipefail
export HOME=/root
LOG_FILE="/var/log/openvpn_ssl_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

{webhook_notification}

trap 'notify_webhook "failed" "unexpected_error" "Script exited on line ${{LINENO}} with code ${{?}}."' ERR

# ---------------- VALIDATION ----------------
if ! [[ "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    notify_webhook "failed" "validation" "Invalid domain format"
    exit 1
fi

notify_webhook "provisioning" "starting" "Beginning OpenVPN SSL setup"

# ---------------- SYSTEM SETUP ----------------
notify_webhook "provisioning" "system_update" "Installing dependencies"
DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl wget ufw sudo nginx certbot python3-certbot-nginx openssl

# ---------------- SSL CERTIFICATE ----------------
notify_webhook "provisioning" "ssl_setup" "Setting up SSL certificate"
mkdir -p /etc/letsencrypt
curl -s "{letsencrypt_options_url}" > /etc/letsencrypt/options-ssl-nginx.conf
curl -s "{ssl_dhparams_url}" > /etc/letsencrypt/ssl-dhparams.pem

systemctl stop nginx || true

certbot certonly --standalone --preferred-challenges http \
    --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" --non-interactive || \
certbot certonly --standalone --preferred-challenges http \
    --staging --agree-tos --email "{ADMIN_EMAIL}" -d "{DOMAIN_NAME}" --non-interactive

systemctl start nginx || true

# ---------------- OPENVPN INSTALLATION ----------------
notify_webhook "provisioning" "openvpn_install" "Installing OpenVPN server"
OVPN_INSTALL_SCRIPT="/tmp/openvpn-install.sh"
curl -o $OVPN_INSTALL_SCRIPT -L https://raw.githubusercontent.com/angristan/openvpn-install/master/openvpn-install.sh
chmod +x $OVPN_INSTALL_SCRIPT

export AUTO_INSTALL=y
export PORT="{VPN_PORT}"
export PROTOCOL="{VPN_PROTOCOL}"
export DNS="1"
export CUSTOMIZE_CLIENT=false
export PASS="{VPN_PASSWORD}"
export USER="{VPN_USER}"

$OVPN_INSTALL_SCRIPT


# ---------------- FIREWALL ----------------
notify_webhook "provisioning" "firewall_setup" "Configuring firewall"
ufw allow 22/tcp
ufw allow {VPN_PORT}/{VPN_PROTOCOL}
ufw --force enable

# ---------------- USE SSL CERTS FOR OPENVPN ----------------
OVPN_DIR="/etc/openvpn"
mv $OVPN_DIR/server.crt $OVPN_DIR/server.crt.bak || true
mv $OVPN_DIR/server.key $OVPN_DIR/server.key.bak || true
ln -s /etc/letsencrypt/live/{DOMAIN_NAME}/fullchain.pem $OVPN_DIR/server.crt
ln -s /etc/letsencrypt/live/{DOMAIN_NAME}/privkey.pem $OVPN_DIR/server.key

# ---------------- NGINX TCP PROXY FOR OPENVPN ----------------
notify_webhook "provisioning" "nginx_tcp_proxy" "Configuring Nginx TCP proxy for OpenVPN"
mkdir -p /etc/nginx/stream.d
cat > /etc/nginx/stream.d/openvpn.conf <<EOF
stream {{
    map \$ssl_preread_alpn \$upstream {{
        default openvpn;
        h2 https_upstream;
        http/1.1 https_upstream;
    }}
    upstream openvpn {{
        server 127.0.0.1:1194;
    }}
    upstream https_upstream {{
        server 127.0.0.1:443;
    }}
    server {{
        listen {VPN_PORT} tcp;
        proxy_pass \$upstream;
        ssl_preread on;
    }}
}}
EOF

# Enable stream module include
if ! grep -q "include /etc/nginx/stream.d/*.conf;" /etc/nginx/nginx.conf; then
    echo -e "\nstream {{\n include /etc/nginx/stream.d/*.conf;\n}}\n" >> /etc/nginx/nginx.conf
fi

nginx -t && systemctl restart nginx

notify_webhook "provisioning" "openvpn_finished" "OpenVPN SSL setup completed successfully"
"""
    return script_template
