import asyncio
import json
import os
import sys
import time
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

import generate_setup  # Your PowerShell setup generator module
import html_email
import html_email_send

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")

#WINDOWS-10 IMAGE
image_reference={
            'publisher': 'MicrosoftWindowsDesktop',
            'offer': 'Windows-10',
            'sku': 'win10-22h2-pro-g2',
            'version': 'latest'
        }

# Ports to open for application [without this app can't run on domain]
PORTS_TO_OPEN = [22,80,443,3389,5000,8000,47984,47989,47990,47998,47999,48000,48010,4531, 3475]

# GALLERY IMAGE
GALLERY_IMAGE_RESOURCE_GROUP = 'nvidiaRTX'
GALLERY_NAME = 'rtx2udk'
GALLERY_IMAGE_NAME = 'idtech4rtx'
GALLERY_IMAGE_VERSION = '1.0.2'
OS_DISK_SSD_GB = '256'
WINDOWS_IMAGE_PASSWORD = 'idtechDevKitRTX1!'
RECIPIENT_EMAILS = 'gabzlabs420@gmail.com'
DUMBDROP_PIN = '1234'

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
    print(f"{bcolors.OKBLUE}[INFO]{bcolors.ENDC} {msg}")

def print_build(msg):
    print(f"{bcolors.OKORANGE}[BUILD]{bcolors.ENDC} {msg}")

def print_success(msg):
    print(f"{bcolors.OKGREEN}[SUCCESS]{bcolors.ENDC} {msg}")

def print_warn(msg):
    print(f"{bcolors.WARNING}[WARNING]{bcolors.ENDC} {msg}")

def print_error(msg):
    print(f"{bcolors.FAIL}[ERROR]{bcolors.ENDC} {msg}")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing create_vm request...')
 
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        #Get paramenters
        pc_name = req_body.get('pc_name') or req.params.get('pc_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        domain = req_body.get('domain') or req.params.get('domain')
        subdomain = pc_name 
        fqdn = domain
        if subdomain:
            subdomain = subdomain.strip().strip('.')
            fqdn = f"{subdomain}.{domain}"
        else:
            fqdn = domain
        print_info(f"Full domain to configure: {fqdn}")

        location = req_body.get('location') or req.params.get('location') #uksouth
        vm_size = req_body.get('vm_size') or req.params.get('vm_size') #Standard_NV6ads_A10_v5

        # Image/Windows configuration as variables assigned similarly (use defaults as needed)
        GALLERY_IMAGE_RESOURCE_GROUP = req_body.get('gallery_image_resource_group') or req.params.get('gallery_image_resource_group')
        GALLERY_NAME = req_body.get('gallery_name') or req.params.get('gallery_name')
        GALLERY_IMAGE_NAME = req_body.get('gallery_image_name') or req.params.get('gallery_image_name')
        GALLERY_IMAGE_VERSION = req_body.get('gallery_image_version') or req.params.get('gallery_image_version')
        OS_DISK_SSD_GB = int(req_body.get('os_disk_ssd_gb') or req.params.get('os_disk_ssd_gb') or 256)
        WINDOWS_IMAGE_PASSWORD = req_body.get('windows_image_password') or req.params.get('windows_image_password')
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')
        DUMBDROP_PIN = req_body.get('dumbdrop_pin') or req.params.get('dumbdrop_pin') or '1234'
        #windows user is always 'source' to keep it simple

        ###Parameter checking to handle errors 
        if not pc_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'pc_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not resource_group:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'resource_group' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not domain:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'domain' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        # Simple regex to reject domains with subdomains (no dots before main domain)
        # This matches domains like example.com or example.co.uk but not sub.example.com
        if '.' not in domain or domain.startswith('.'):
            return func.HttpResponse(
                json.dumps({
                    "error": f"Domain '{domain}' is invalid or incomplete. Please enter a valid domain (e.g., 'example.com')."
                }),
                status_code=400,
                mimetype="application/json"
            )
        if len(domain.split('.')) > 2:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Domain '{domain}' should not contain subdomains. Please enter the root domain only (e.g., 'example.com')."
                }),
                status_code=400,
                mimetype="application/json"
            )
        if not location:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'location' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not vm_size:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'vm_size' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        else:
            if not check_vm_size_compatibility(vm_size):
                compatible_sizes = get_compatible_vm_sizes()
                return func.HttpResponse(
                    json.dumps({
                        "error": f"VmSize {vm_size} is incompatible. Please select a size from the list: {compatible_sizes}"
                    }),
                    status_code=400,
                    mimetype="application/json"
                )
        if not GALLERY_IMAGE_RESOURCE_GROUP:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'gallery_image_resource_group' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not GALLERY_NAME:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'gallery_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not GALLERY_IMAGE_NAME:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'gallery_image_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not GALLERY_IMAGE_VERSION:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'gallery_image_version' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not WINDOWS_IMAGE_PASSWORD:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'windows_image_password' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not RECIPIENT_EMAILS:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'recipient_emails' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        
        #Checks successful -> continue 
        tenant_id = os.environ.get("AZURE_TENANT_ID")
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
 

        method = req.method
        return func.HttpResponse(f"create_vm: Received a {method} request", status_code=200)
        return func.HttpResponse(f"Received a {method} request", status_code=200)

    except Exception as ex:
        logging.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )


async def create_storage_account(storage_client, resource_group_name, storage_name, location):
    print_info(f"Creating storage account '{storage_name}' in '{location}'...")
    try:
        try:
            storage_client.storage_accounts.get_properties(resource_group_name, storage_name)
            print_info(f"Storage account '{storage_name}' already exists.")
        except:
            poller = storage_client.storage_accounts.begin_create(
                resource_group_name,
                storage_name,
                {
                    "sku": {"name": "Standard_LRS"},
                    "kind": "StorageV2",
                    "location": location,
                    "enable_https_traffic_only": True
                }
            )
            poller.result()
            print_success(f"Storage account '{storage_name}' created.")

        keys = storage_client.storage_accounts.list_keys(resource_group_name, storage_name)
        storage_key = keys.keys[0].value
        storage_url = f"https://{storage_name}.blob.core.windows.net"

        return {
            "AZURE_STORAGE_URL": storage_url,
            "AZURE_STORAGE_NAME": storage_name,
            "AZURE_STORAGE_KEY": storage_key
        }
    except Exception as e:
        print_error(f"Failed to create storage account: {e}")
        raise

def ensure_container_exists(blob_service_client, container_name):
    print_info(f"Checking container '{container_name}'.")
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
        print_success(f"Created container '{container_name}'.")
    except Exception as e:
        print_info(f"Container '{container_name}' likely exists or could not be created: {e}")
    return container_client

async def upload_blob_and_generate_sas(blob_service_client, container_name, blob_name, data, sas_expiry_hours=1):
    print_info(f"Uploading blob '{blob_name}' to container '{container_name}'.")
    container_client = ensure_container_exists(blob_service_client, container_name)
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True)
    print_success(f"Uploaded blob '{blob_name}' to container '{container_name}'.")
    print_info(f"SAS URL generating for blob '{blob_name}'.")
    sas_token = generate_blob_sas(
        blob_service_client.account_name,
        container_name,
        blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=sas_expiry_hours),
        account_key=AZURE_STORAGE_ACCOUNT_KEY
    )
    blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"
    blob_url_with_sas = f"{blob_url}?{sas_token}"
    print_success(f"SAS URL generated for blob '{blob_name}'.")
    return blob_url_with_sas

    def get_compatible_vm_sizes():
        return [
            'Standard_NV4as_v4',
            'Standard_NV6ads_A10_v5',
            'Standard_NV8as_v4',
            'Standard_NV12ads_A10_v5',
            'Standard_NV12s_v3',
            'Standard_NV16as_v4',
            'Standard_NV18ads_A10_v5',
            'Standard_NV32as_v4',
            'Standard_NV36adms_A10_v5',
            'Standard_NV36ads_A10_v5'
        ]

    def check_vm_size_compatibility(vm_size):
        # List of VM sizes that support Gen 2 Hypervisor with proper 'Standard_' prefix
        return vm_size in get_compatible_vm_sizes()

def check_ns_delegation_with_retries(dns_client, resource_group, domain, retries=5, delay=10):
    for attempt in range(1, retries + 1):
        if check_ns_delegation(dns_client, resource_group, domain):
            return True
        print_warn(f"\n⚠️ Retrying NS delegation check in {delay} seconds... (Attempt {attempt}/{retries})")
        time.sleep(delay)
    return False

def check_ns_delegation(dns_client, resource_group, domain):
    print_warn(
        "\nIMPORTANT: You must update your domain registrar's nameserver (NS) records "
        "to exactly match the Azure DNS nameservers. Without this delegation, "
        "your domain will NOT resolve correctly, and your application will NOT work as expected.\n"
        "Please log into your domain registrar (e.g., Namecheap, GoDaddy) and set the NS records "
        "for your domain to the above nameservers.\n"
        "DNS changes may take up to 24–48 hours to propagate globally.\n"
    )

    try:
        print_info("\n----------------------------")
        print_info("🔍 Checking Azure DNS zone for NS servers...")
        dns_zone = dns_client.zones.get(resource_group, domain)
        azure_ns = sorted(ns.lower().rstrip('.') for ns in dns_zone.name_servers)
        print_info(f"✅ Azure DNS zone NS servers for '{domain}':")
        for ns in azure_ns:
            print(f"  - {ns}")
    except Exception as e:
        print_error(f"\n❌ Failed to get Azure DNS zone NS servers: {e}")
        return False

    try:
        print_info("\n🌐 Querying public DNS to verify delegation...")
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Google DNS
        answers = resolver.resolve(domain, 'NS')
        public_ns = sorted(str(rdata.target).lower().rstrip('.') for rdata in answers)
        print_info(f"🌍 Publicly visible NS servers for '{domain}':")
        for ns in public_ns:
            print(f"  - {ns}")
    except Exception as e:
        print_error(f"\n❌ Failed to resolve public NS records for domain '{domain}': {e}")
        return False

    if set(azure_ns).issubset(set(public_ns)):
        print_success("\n✅✅✅ NS delegation is correctly configured ✅✅✅")
        return True
    else:
        print_error("\n❌ NS delegation mismatch detected!")
        print_error("\nAzure DNS NS servers:")
        for ns in azure_ns:
            print_error(f"  - {ns}")
        print_error("\nPublicly visible NS servers:")
        for ns in public_ns:
            print_error(f"  - {ns}")

        print_warn(
            "\nACTION REQUIRED: Update your domain registrar's NS records to match the Azure DNS NS servers.\n"
            "Provisioning will stop until this is fixed.\n"
        )
        return False
    
async def cleanup_resources_on_failure(network_client, compute_client, storage_client, blob_service_client, container_name, blob_name, dns_client, resource_group, domain, a_records, vm_name, storage_account_name):
    print_warn("Starting cleanup of Azure resources due to failure...")

    # Delete VM
    try:
        vm = compute_client.virtual_machines.get(resource_group, vm_name)
        os_disk_name = vm.storage_profile.os_disk.name
        compute_client.virtual_machines.begin_delete(resource_group, vm_name).result()
        print_info(f"Deleted VM '{vm_name}'.")
    except Exception as e:
        print_warn(f"Could not delete VM '{vm_name}': {e}")
        os_disk_name = None

    # Delete OS disk if available
    if os_disk_name:
        try:
            compute_client.disks.begin_delete(resource_group, os_disk_name).result()
            print_info(f"Deleted OS disk '{os_disk_name}'.")
        except Exception as e:
            print_warn(f"Could not delete OS disk '{os_disk_name}': {e}")

    # Delete NIC
    try:
        network_client.network_interfaces.begin_delete(resource_group, f"{vm_name}-nic").result()
        print_info(f"Deleted NIC '{vm_name}-nic'.")
    except Exception as e:
        print_warn(f"Could not delete NIC '{vm_name}-nic': {e}")

    # Delete NSG
    try:
        network_client.network_security_groups.begin_delete(resource_group, f"{vm_name}-nsg").result()
        print_info(f"Deleted NSG '{vm_name}-nsg'.")
    except Exception as e:
        print_warn(f"Could not delete NSG '{vm_name}-nsg': {e}")

    # Delete Public IP
    try:
        network_client.public_ip_addresses.begin_delete(resource_group, f"{vm_name}-public-ip").result()
        print_info(f"Deleted Public IP '{vm_name}-public-ip'.")
    except Exception as e:
        print_warn(f"Could not delete Public IP '{vm_name}-public-ip': {e}")

    # Delete VNet
    try:
        network_client.virtual_networks.begin_delete(resource_group, f"{vm_name}-vnet").result()
        print_info(f"Deleted VNet '{vm_name}-vnet'.")
    except Exception as e:
        print_warn(f"Could not delete VNet '{vm_name}-vnet': {e}")

    # Delete Storage Account
    try:
        print_info(f"Deleting blob '{blob_name}' from container '{container_name}'.")
        container_client = blob_service_client.get_container_client(container_name)
        container_client.delete_blob(blob_name)
        print_success(f"Deleted blob '{blob_name}' from container '{container_name}'.")
        print_info(f"Deleting container '{container_name}'.")
        blob_service_client.delete_container(container_name)
        print_success(f"Deleted container '{container_name}'.")
        print_info(f"Deleting storage account '{storage_account_name}'.")
        storage_client.storage_accounts.delete(resource_group, storage_account_name)
        print_success(f"Deleted storage account '{storage_account_name}'.")
    except Exception as e:
        print_warn(f"Could not delete Storage Account '{storage_account_name}': {e}")

    # Delete DNS A record (keep DNS zone)
    for record_name in a_records:
        record_to_delete = record_name if record_name else '@'  # handle root domain with '@'
        try:
            dns_client.record_sets.delete(resource_group, domain, record_to_delete, 'A')
            print_info(f"Deleted DNS A record '{record_to_delete}' in zone '{domain}'.")
        except Exception as e:
            print_warn(f"Could not delete DNS A record '{record_to_delete}' in zone '{domain}': {e}")

    print_success("Cleanup completed.")

async def cleanup_temp_storage_on_success(resource_group, storage_client, storage_account_name, blob_service_client, container_name, blob_name):
    print_info("Starting cleanup of Azure resources on success...")

    # Delete Storage Account
    try:
        print_info(f"Deleting blob '{blob_name}' from container '{container_name}'.")
        container_client = blob_service_client.get_container_client(container_name)
        container_client.delete_blob(blob_name)
        print_success(f"Deleted blob '{blob_name}' from container '{container_name}'.")
        print_info(f"Deleting container '{container_name}'.")
        blob_service_client.delete_container(container_name)
        print_success(f"Deleted container '{container_name}'.")
        print_info(f"Deleting storage account '{storage_account_name}'.")
        storage_client.storage_accounts.delete(resource_group, storage_account_name)
        print_success(f"Deleted storage account '{storage_account_name}'.")
    except Exception as e:
        print_warn(f"Could not delete Storage Account '{storage_account_name}': {e}")

    print_success("Temp storage cleanup completed.")

