def generate_setup(DOMAIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT, PC_HOST, PIN_URL, VOLUME_DIR="/opt/ubuntu", WEBHOOK_URL=""):
    SERVICE_USER = "ubuntu"
    letsencrypt_options_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
    ssl_dhparams_url = "https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"

    script_template = f'''#!/bin/bash

 
echo "============================================"
echo "✅ Setup Complete!"
echo ""
echo "🔗 Access your app at: https://{DOMAIN_NAME}"
echo ""
echo "============================================"
'''
    return script_template