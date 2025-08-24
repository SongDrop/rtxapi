import sys
import json
import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
import asyncio
from azure.identity import ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
import azure.functions as func

# Use relative imports to load local modules from the same function folder.
# This ensures Python finds these files (generate_setup.py, html_email.py, html_email_send.py)
# in the current package instead of searching in global site-packages,
# which prevents ModuleNotFoundError in Azure Functions environment.
from . import html_email
from . import html_email_send

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Console colors for logs
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKORANGE = '\033[38;5;214m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

#####
def print_info(msg):
    logging.info(f"{bcolors.OKBLUE}[INFO]{bcolors.ENDC} {msg}")

def print_build(msg):
    logging.info(f"{bcolors.OKORANGE}[BUILD]{bcolors.ENDC} {msg}")

def print_success(msg):
    logging.info(f"{bcolors.OKGREEN}[SUCCESS]{bcolors.ENDC} {msg}")

def print_warn(msg):
    logging.info(f"{bcolors.WARNING}[WARNING]{bcolors.ENDC} {msg}")

def print_error(msg):
    logging.info(f"{bcolors.FAIL}[ERROR]{bcolors.ENDC} {msg}")


smtp_host = os.environ.get('SMTP_HOST')
smtp_port = os.environ.get('SMTP_PORT')
smtp_user = os.environ.get('SMTP_USER')
smtp_password = os.environ.get('SMTP_PASS')
sender_email = os.environ.get('SENDER_EMAIL')

def get_public_ip(network_client, resource_group, nic_name):
    nic = network_client.network_interfaces.get(resource_group, nic_name)
    if nic.ip_configurations and nic.ip_configurations[0].public_ip_address:
        public_ip_id = nic.ip_configurations[0].public_ip_address.id
        parts = public_ip_id.split('/')
        pubip_rg = parts[4]
        pubip_name = parts[-1]
        public_ip_resource = network_client.public_ip_addresses.get(pubip_rg, pubip_name)
        return public_ip_resource.ip_address
    return None

async def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        recipients = req_body.get("recipients") or req.params.get("recipients")
        vm_name = req_body.get("vm_name") or req.params.get("vm_name")
        resource_group = req_body.get("resource_group") or req.params.get("resource_group")

        missing = [param for param in ["recipients", "vm_name", "resource_group"] if not locals()[param]]
        if missing:
            return func.HttpResponse(
                json.dumps({"error": f"Missing parameters: {', '.join(missing)}"}),
                status_code=400,
                mimetype="application/json"
            )

        recipient_emails = [e.strip() for e in recipients.split(',')]

        # Authenticate with Azure
        credential = ClientSecretCredential(
            client_id=os.environ['AZURE_APP_CLIENT_ID'],
            client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
            tenant_id=os.environ['AZURE_APP_TENANT_ID']
        )
        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        network_client = NetworkManagementClient(credential, subscription_id)

        nic_name = f"{vm_name}-nic"
        public_ip = get_public_ip(network_client, resource_group, nic_name)
        if not public_ip:
            logger.warning(f"No public IP found for VM '{vm_name}'")
            public_ip = ""

        html_content = html_email.HTMLEmail(
            ip_address=public_ip,
            background_image_url="https://modwiki.dhewm3.org/images/c/cd/Bump2spec_1_local.png",
            title=f"{vm_name} - Idtech RemoteRTX",
            main_heading=f"{vm_name} - Idtech RemoteRTX",
            main_description="Your virtual machine is ready to play games.",
            youtube_embed_src="https://youtu.be/PeVxO56lCBs",
            image_left_src="",
            image_right_src="",
            logo_src="https://i.postimg.cc/BnsDT6sQ/mohradiant.png",
            company_src="https://i.postimg.cc/25pxqcWZ/powered-by-idtech.png",
            discord_widget_src="https://discord.com/widget?id=1363815250742480927&theme=dark",
            windows_password="*******",
            credentials_sunshine="Username: <strong>sunshine</strong><br>Password: <strong>sunshine</strong>",
            form_description="Fill our form, so we can match your team with investors/publishers",
            form_link="https://forms.gle/QgFZQhaehZLs9sySA"
        )

        # Send email in background
        asyncio.create_task(
            html_email_send.send_html_email_smtp(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                sender_email=sender_email,
                recipient_emails=recipient_emails,
                subject=f"Azure VM '{vm_name}' Completed",
                html_content=html_content,
                use_tls=True
            )
        )

        return func.HttpResponse(
            json.dumps({"status": "success", "public_ip": public_ip}),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logger.exception("Error sending email:")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )