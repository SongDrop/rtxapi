import textwrap

def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VPN_PORT=1194,
    WEBHOOK_URL="",
    location="",
    resource_group="",
    PROTOCOL="udp",
    DATA_VOLUME="ovpn-data",
    DOCKER_IMAGE="kylemanna/openvpn",
    DATA_DIR="/opt/openvpn",
    DNS_HOOK_SCRIPT="/usr/local/bin/dns-hook-script.sh"
):
    """
    Returns a full bash provisioning script for OpenVPN on Docker, in Forgejo style.
    """

    # ========== TOKEN DEFINITIONS ==========
    tokens = {
        "__DOMAIN__": DOMAIN_NAME,
        "__ADMIN_EMAIL__": ADMIN_EMAIL,
        "__VPN_PORT__": str(VPN_PORT),
        "__PROTOCOL__": PROTOCOL,
        "__DATA_VOLUME__": DATA_VOLUME,
        "__DOCKER_IMAGE__": DOCKER_IMAGE,
        "__WEBHOOK_URL__": WEBHOOK_URL,
        "__LOCATION__": location,
        "__RESOURCE_GROUP__": resource_group,
        "__DATA_DIR__": DATA_DIR,
        "__DNS_HOOK_SCRIPT__": DNS_HOOK_SCRIPT,
    }

    # ========== BASE TEMPLATE ==========
    script_template = textwrap.dedent(r"""
    #!/bin/bash
    set -euo pipefail

    # ----------------------------------------------------------------------
    # OpenVPN Provisioning Script (Forgejo style)
    # ----------------------------------------------------------------------

    # --- Webhook Notification System ---
    __WEBHOOK_FUNCTION__

    trap 'notify_webhook "failed" "unexpected_error" "Script exited on line $LINENO with code $?"' ERR

    # --- Logging ---
    LOG_FILE="/var/log/openvpn_setup.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    # --- Environment Variables ---
    DOMAIN="__DOMAIN__"
    ADMIN_EMAIL="__ADMIN_EMAIL__"
    VPN_PORT="__VPN_PORT__"
    PROTOCOL="__PROTOCOL__"
    DATA_VOLUME="__DATA_VOLUME__"
    DOCKER_IMAGE="__DOCKER_IMAGE__"
    WEBHOOK_URL="__WEBHOOK_URL__"
    LOCATION="__LOCATION__"
    RESOURCE_GROUP="__RESOURCE_GROUP__"
    DATA_DIR="__DATA_DIR__"

    echo "[1/12] Starting OpenVPN provisioning..."
    notify_webhook "provisioning" "starting" "Beginning OpenVPN setup"

    # ========== INPUT VALIDATION ==========
    echo "[2/12] Validating inputs..."
    notify_webhook "provisioning" "validation" "Validating domain and port"

    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "ERROR: Invalid domain $DOMAIN"
        notify_webhook "failed" "validation" "Invalid domain format"
        exit 1
    fi

    if ! [[ "$VPN_PORT" =~ ^[0-9]+$ ]] || [ "$VPN_PORT" -lt 1 ] || [ "$VPN_PORT" -gt 65535 ]; then
        echo "ERROR: Invalid VPN port $VPN_PORT"
        notify_webhook "failed" "validation" "Invalid VPN port number"
        exit 1
    fi

    if [[ "$PROTOCOL" != "udp" && "$PROTOCOL" != "tcp" ]]; then
        echo "ERROR: Protocol must be 'udp' or 'tcp'"
        notify_webhook "failed" "validation" "Invalid protocol"
        exit 1
    fi

    # ========== SYSTEM DEPENDENCIES ==========
    echo "[3/12] Installing system dependencies..."
    notify_webhook "provisioning" "system_dependencies" "Installing base packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get upgrade -y -q
    apt-get install -y -q curl git jq net-tools openssl ufw

    # ========== DOCKER INSTALLATION ==========
    echo "[4/12] Installing Docker..."
    notify_webhook "provisioning" "docker_install" "Installing Docker engine"
    sleep 5

    # Ensure prerequisites exist
    apt-get install -y -q ca-certificates curl gnupg lsb-release || {
        notify_webhook "failed" "docker_prereq" "Failed to install Docker prerequisites"
        exit 1
    }

    # Remove old versions (ignore errors)
    apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true

    # Setup Docker's official GPG key
    mkdir -p /etc/apt/keyrings
    if ! curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; then
        echo "❌ Failed to download Docker GPG key"
        notify_webhook "failed" "docker_gpg" "Failed to download Docker GPG key"
        exit 1
    fi
    chmod a+r /etc/apt/keyrings/docker.gpg

    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs)
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list

    # Update and install Docker with retries
    for i in {1..3}; do
        if apt-get update -q && apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
            break
        fi
        echo "⚠️ Docker install attempt $i failed; retrying..."
        sleep 5
        [ $i -eq 3 ] && {
            echo "❌ Docker installation failed after 3 attempts"
            notify_webhook "failed" "docker_install" "Docker install failed after 3 attempts"
            exit 1
        }
    done

    # Enable and start Docker
    systemctl enable docker
    systemctl start docker

    # Verify Docker works
    if ! docker info >/dev/null 2>&1; then
        echo "❌ Docker daemon did not start correctly"
        notify_webhook "failed" "docker_daemon" "Docker daemon failed to start"
        journalctl -u docker --no-pager | tail -n 50 || true
        exit 1
    fi

    echo "✅ Docker installed and running"
    notify_webhook "provisioning" "docker_ready" "✅ Docker installed successfully"
    sleep 5

    # ========== OPENVPN DIRECTORY SETUP ==========
    echo "[5/12] Setting up OpenVPN directory..."
    notify_webhook "provisioning" "directory_setup" "Creating OpenVPN directory structure"
    sleep 5

    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Failed to create OpenVPN data directory"
        notify_webhook "failed" "directory_creation" "Failed to create OpenVPN directory"
        exit 1
    }
    cd "$DATA_DIR"
    echo "✅ OpenVPN directory ready"
    notify_webhook "provisioning" "directory_ready" "✅ OpenVPN directory created successfully"
    sleep 5

    # ========== CREATE DOCKER VOLUME ==========
    echo "[6/12] Creating Docker volume for OpenVPN..."
    notify_webhook "provisioning" "volume_creation" "Creating Docker volume $DATA_VOLUME"

    if ! docker volume create --name "$DATA_VOLUME"; then
        echo "❌ Failed to create Docker volume"
        notify_webhook "failed" "volume_creation" "Failed to create Docker volume"
        exit 1
    fi

    echo "✅ Docker volume created successfully"
    notify_webhook "provisioning" "volume_ready" "✅ Docker volume created successfully"
    sleep 3

    # ========== GENERATE OPENVPN CONFIGURATION ==========
    echo "[7/12] Generating OpenVPN configuration..."
    notify_webhook "provisioning" "ovpn_config" "Generating OpenVPN server configuration"

    # Generate initial configuration
    if ! docker run -v "$DATA_VOLUME:/etc/openvpn" --log-driver=none --rm "$DOCKER_IMAGE" ovpn_genconfig -u "$PROTOCOL://$DOMAIN:$VPN_PORT" -d -D -N; then
        echo "❌ Failed to generate OpenVPN configuration"
        notify_webhook "failed" "ovpn_config" "Failed to generate OpenVPN configuration"
        exit 1
    fi

    echo "✅ OpenVPN configuration generated"
    notify_webhook "provisioning" "ovpn_config_ready" "✅ OpenVPN configuration generated"
    sleep 3

    # ========== SETUP CERTIFICATES AND PKI ==========
    echo "[8/12] Setting up certificates and PKI..."
    notify_webhook "provisioning" "certificate_setup" "Setting up certificate authority and keys"

    echo "⚠️  You will be prompted to set a CA passphrase. Keep it secure!"
    echo "⚠️  You will need this passphrase for generating client certificates."

    if ! docker run -v "$DATA_VOLUME:/etc/openvpn" --log-driver=none --rm -it "$DOCKER_IMAGE" ovpn_initpki; then
        echo "❌ Failed to initialize PKI"
        notify_webhook "failed" "pki_init" "Failed to initialize PKI"
        exit 1
    fi

    echo "✅ PKI and certificates initialized successfully"
    notify_webhook "provisioning" "pki_ready" "✅ PKI and certificates initialized successfully"
    sleep 3

    # ========== START OPENVPN SERVER ==========
    echo "[9/12] Starting OpenVPN server..."
    notify_webhook "provisioning" "server_start" "Starting OpenVPN server container"

    # Start the OpenVPN server
    if ! docker run -v "$DATA_VOLUME:/etc/openvpn" -d --name openvpn-server -p "$VPN_PORT:$VPN_PORT/$PROTOCOL" --cap-add=NET_ADMIN --restart unless-stopped "$DOCKER_IMAGE"; then
        echo "❌ Failed to start OpenVPN server"
        notify_webhook "failed" "server_start" "Failed to start OpenVPN server"
        exit 1
    fi

    # Wait for server to start
    echo "⏳ Waiting for OpenVPN server to start..."
    sleep 10

    if ! docker ps | grep -q openvpn-server; then
        echo "❌ OpenVPN server container is not running"
        docker logs openvpn-server --tail=50 || true
        notify_webhook "failed" "server_health" "OpenVPN server container failed to start"
        exit 1
    fi

    echo "✅ OpenVPN server started successfully"
    notify_webhook "provisioning" "server_ready" "✅ OpenVPN server started successfully"
    sleep 5

    # ========== GENERATE CLIENT CERTIFICATE ==========
    echo "[10/12] Generating client certificate..."
    notify_webhook "provisioning" "client_cert" "Generating client certificate"

    CLIENT_NAME="client-$(date +%Y%m%d-%H%M%S)"
    
    # Generate client certificate without password for easier distribution
    if ! docker run -v "$DATA_VOLUME:/etc/openvpn" --log-driver=none --rm -it "$DOCKER_IMAGE" easyrsa build-client-full "$CLIENT_NAME" nopass; then
        echo "❌ Failed to generate client certificate"
        notify_webhook "failed" "client_cert" "Failed to generate client certificate"
        exit 1
    fi

    echo "✅ Client certificate generated: $CLIENT_NAME"
    notify_webhook "provisioning" "client_cert_ready" "✅ Client certificate generated: $CLIENT_NAME"
    sleep 3

    # ========== EXPORT CLIENT CONFIGURATION ==========
    echo "[11/12] Exporting client configuration..."
    notify_webhook "provisioning" "client_config" "Exporting client configuration file"

    # Export client configuration
    if ! docker run -v "$DATA_VOLUME:/etc/openvpn" --log-driver=none --rm "$DOCKER_IMAGE" ovpn_getclient "$CLIENT_NAME" > "$DATA_DIR/$CLIENT_NAME.ovpn"; then
        echo "❌ Failed to export client configuration"
        notify_webhook "failed" "client_config" "Failed to export client configuration"
        exit 1
    fi

    # Make the config file readable
    chmod 644 "$DATA_DIR/$CLIENT_NAME.ovpn"

    echo "✅ Client configuration exported: $DATA_DIR/$CLIENT_NAME.ovpn"
    notify_webhook "provisioning" "client_config_ready" "✅ Client configuration exported"
    sleep 3

    # ========== FIREWALL CONFIGURATION ==========
    echo "[12/12] Configuring firewall..."
    notify_webhook "provisioning" "firewall" "Setting up UFW firewall rules"

    ufw allow 22/tcp
    ufw allow 1194/tcp
    ufw allow "$VPN_PORT/$PROTOCOL"
    ufw --force enable

    echo "✅ Firewall configured"
    notify_webhook "provisioning" "firewall_ready" "✅ Firewall configured successfully"

    # ========== FINAL CHECKS ==========
    echo "🔍 Performing final verification..."
    notify_webhook "provisioning" "verification" "Performing final verification checks"

    # Check if OpenVPN container is running
    if docker ps | grep -q openvpn-server; then
        echo "✅ OpenVPN server container is running"
        
        # Check if port is listening
        if netstat -tuln | grep -q ":$VPN_PORT"; then
            echo "✅ OpenVPN server is listening on port $VPN_PORT/$PROTOCOL"
            notify_webhook "success" "verification" "OpenVPN server is fully operational"
        else
            echo "⚠️  OpenVPN server container running but port not detected"
            notify_webhook "warning" "verification" "OpenVPN container running but port check inconclusive"
        fi
    else
        echo "❌ OpenVPN server container is not running"
        notify_webhook "failed" "verification" "OpenVPN server container not running"
        exit 1
    fi

    echo "✅ OpenVPN setup complete!"
    notify_webhook "success" "complete" "OpenVPN deployment completed successfully"

    # Display summary
    cat <<EOF_SUMMARY

=============================================
🚀 OpenVPN Setup Complete!
=============================================

🔗 Server Information:
   - Domain: $DOMAIN
   - Port: $VPN_PORT/$PROTOCOL
   - Admin Email: $ADMIN_EMAIL

📁 Important Files:
   - Client Config: $DATA_DIR/$CLIENT_NAME.ovpn
   - Docker Volume: $DATA_VOLUME

⚙️ Management Commands:
   - Server Status: docker ps | grep openvpn
   - Server Logs: docker logs openvpn-server
   - Stop Server: docker stop openvpn-server
   - Start Server: docker start openvpn-server

👤 Generate Additional Clients:
   cd $DATA_DIR
   docker run -v $DATA_VOLUME:/etc/openvpn --log-driver=none --rm -it $DOCKER_IMAGE easyrsa build-client-full NEW_CLIENT_NAME nopass
   docker run -v $DATA_VOLUME:/etc/openvpn --log-driver=none --rm $DOCKER_IMAGE ovpn_getclient NEW_CLIENT_NAME > NEW_CLIENT_NAME.ovpn

🔧 Troubleshooting:
   - Check logs: docker logs openvpn-server -f
   - Test connectivity: nc -vzu $DOMAIN $VPN_PORT

=============================================
⚠️  IMPORTANT: Download and secure the client configuration file:
   $DATA_DIR/$CLIENT_NAME.ovpn
=============================================

EOF_SUMMARY

    # Display the client config file location prominently
    echo "📄 Client configuration file created: $DATA_DIR/$CLIENT_NAME.ovpn"
    echo "📋 To download this file, use: scp user@$DOMAIN:$DATA_DIR/$CLIENT_NAME.ovpn ./"
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
  "service": "openvpn",
  "details": {
    "step": "$step",
    "message": "$message",
    "domain": "__DOMAIN__",
    "port": "__VPN_PORT__",
    "protocol": "__PROTOCOL__"
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

    return final

 