import sys
import json
import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
import random
import string
import subprocess
import shutil
import platform
import webbrowser
import dns.resolver
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkSecurityGroup, SecurityRule, NetworkInterface
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import (
    VirtualMachine, HardwareProfile, StorageProfile,
    OSProfile, NetworkProfile, NetworkInterfaceReference,
    VirtualMachineExtension, WindowsConfiguration,SecurityProfile
)
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import RecordSet
from azure.mgmt.storage import StorageManagementClient
import azure.functions as func

import html_email
import html_email_send

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
smtp_port_str = os.environ.get('SMTP_PORT')
smtp_user = os.environ.get('SMTP_USER')
smtp_password = os.environ.get('SMTP_PASS')
sender_email = os.environ.get('SENDER_EMAIL')


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing create_vm request...')
 
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}
            #EMAIL SENDING
            # Required parameters
            recipients = req_body.get("recipients") or req.params.get("recipients")
            vm_name = req_body.get("vm_name") or req.params.get("vm_name")
            resource_group = req_body.get("resource_group") or req.params.get("resource_group")
            WINDOWS_IMAGE_PASSWORD = '*******'
            DOMAIN = ''
            PUBLIC_IP = ''

            missing = []
            for param in ["recipients", "vm_name", "resource_group"]:
                if not locals()[param]:
                    missing.append(param)
            if missing:
                return func.HttpResponse(
                    json.dumps({"error": f"Missing parameters: {', '.join(missing)}"}),
                    status_code=400,
                    mimetype="application/json"
                )


            if not recipients:
                print_error("RECIPIENT_EMAILS environment variable is not set.")
                #sys.exit(1)
            recipient_emails = [e.strip() for e in recipients.split(',')]

            # Authenticate with Azure
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
            subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')

            network_client = NetworkManagementClient(credentials, subscription_id)
            
            nic_name = f"{vm_name}-nic"

            nic = network_client.network_interfaces.get(resource_group, nic_name)

            public_ip = None
            if nic.ip_configurations and nic.ip_configurations[0].public_ip_address:
                public_ip_id = nic.ip_configurations[0].public_ip_address.id
                # Extract resource group and name for public ip
                parts = public_ip_id.split('/')
                pubip_rg = parts[4]
                pubip_name = parts[-1]
                public_ip_resource = network_client.public_ip_addresses.get(pubip_rg, pubip_name)
                public_ip = public_ip_resource.ip_address

            if not public_ip:
                logging.warning(f"No public IP found for VM '{vm_name}'")
                public_ip = ""

            # Validate and convert smtp_port safely
            try:
                smtp_port = int(smtp_port_str)
            except (ValueError, TypeError):
                print_error(f"Invalid SMTP_PORT value: {smtp_port_str}")


            # Build the HTML content correctly using keyword arguments (assuming html.HTMLEmail is a function/class)
            html_content = html_email.HTMLEmail(
                ip_address=PUBLIC_IP,
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
                windows_password=WINDOWS_IMAGE_PASSWORD,
                credentials_sunshine="Username: <strong>sunshine</strong><br>Password: <strong>sunshine</strong>",
                form_description="Fill our form, so we can match your team with investors/publishers",
                form_link="https://forms.gle/QgFZQhaehZLs9sySA"
            )

            try:
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
            except Exception as e:
                print_error(f"Failed to send email: {e}")

    except Exception as e:
        logger.exception("Error in create_clone_vm:")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")