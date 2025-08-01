import asyncio
import json
import os
import sys
import time
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
import random
import string
import shutil
import platform
import dns.resolver
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import logging
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

# Use relative imports to load local modules from the same function folder.
# This ensures Python finds these files (generate_setup.py, html_email.py, html_email_send.py)
# in the current package instead of searching in global site-packages,
# which prevents ModuleNotFoundError in Azure Functions environment.
from . import generate_setup  # Your PowerShell setup generator module
from . import html_email
from . import html_email_send

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


async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing create_vm request...')
 
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        #Get paramenters
        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        domain = req_body.get('domain') or req.params.get('domain')
        subdomain = vm_name 
        fqdn = domain
        if subdomain:
            subdomain = subdomain.strip().strip('.')
            fqdn = f"{subdomain}.{domain}"
        else:
            fqdn = domain
        print_info(f"Full domain to configure: {fqdn}")

        location = req_body.get('location') or req.params.get('location') #uksouth
        vm_size = req_body.get('vm_size') or req.params.get('vm_size') #Standard_NV6ads_A10_v5
        storage_account_base = vm_name

        # Image/Windows configuration as variables assigned similarly (use defaults as needed)
        GALLERY_IMAGE_RESOURCE_GROUP = req_body.get('gallery_image_resource_group') or req.params.get('gallery_image_resource_group')
        GALLERY_NAME = req_body.get('gallery_name') or req.params.get('gallery_name')
        GALLERY_IMAGE_NAME = req_body.get('gallery_image_name') or req.params.get('gallery_image_name')
        GALLERY_IMAGE_VERSION = req_body.get('gallery_image_version') or req.params.get('gallery_image_version') or 'latest'
        OS_DISK_SSD_GB = int(req_body.get('os_disk_ssd_gb') or req.params.get('os_disk_ssd_gb') or 256)
        WINDOWS_IMAGE_PASSWORD = req_body.get('windows_image_password') or req.params.get('windows_image_password')
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')
        DUMBDROP_PIN = req_body.get('dumbdrop_pin') or req.params.get('dumbdrop_pin') or '1234'
        #windows user is always 'source' to keep it simple
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''

        ###Parameter checking to handle errors 
        if not vm_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'vm_name' parameter"}),
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
        if GALLERY_IMAGE_VERSION.lower() != 'latest':
            # Regex to match semantic versioning: e.g. 1.0.0, 2.3.4, etc.
            semver_pattern = r'^\d+\.\d+\.\d+$'
            if not re.match(semver_pattern, GALLERY_IMAGE_VERSION):
                return func.HttpResponse(
                    json.dumps({
                        "error": f"Invalid 'gallery_image_version' format: '{GALLERY_IMAGE_VERSION}'. Must be 'latest' or semantic version 'X.Y.Z' like '1.0.0'."
                    }),
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
 
        # Authenticate with Azure
        try:
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
        except KeyError as e:
            err = f"Missing environment variable: {e}"
            print_error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )
        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            print_error("Set AZURE_SUBSCRIPTION_ID environment variable.")
            return func.HttpResponse(
                json.dumps({"error": f"Set AZURE_SUBSCRIPTION_ID environment variable."}),
                status_code=500,
                mimetype="application/json"
            )

        compute_client = ComputeManagementClient(credentials, subscription_id)
        storage_client = StorageManagementClient(credentials, subscription_id)
        network_client = NetworkManagementClient(credentials, subscription_id)
        resource_client = ResourceManagementClient(credentials, subscription_id)
        dns_client = DnsManagementClient(credentials, subscription_id)

        # Container storage
        storage_account_name = f"{storage_account_base}{int(time.time()) % 10000}"
        storage_config = await create_storage_account(storage_client, resource_group, storage_account_name, location)
        global AZURE_STORAGE_ACCOUNT_KEY
        AZURE_STORAGE_ACCOUNT_KEY = storage_config["AZURE_STORAGE_KEY"]
        AZURE_STORAGE_URL = storage_config["AZURE_STORAGE_URL"]
        
        # Autoinstall script generation
        print_info("Generating PowerShell setup script...")
        ssl_email = os.environ.get('SENDER_EMAIL')
        ps_script = generate_setup.generate_setup(vm_name, fqdn,ssl_email, DUMBDROP_PIN, WINDOWS_IMAGE_PASSWORD)

        blob_service_client = BlobServiceClient(account_url=AZURE_STORAGE_URL, credential=credentials)
        container_name = 'vm-startup-scripts'
        blob_name = f"{vm_name}-setup.ps1"

        # Uploading generated script to storage
        blob_url_with_sas = await upload_blob_and_generate_sas(blob_service_client, container_name, blob_name, ps_script, sas_expiry_hours=2)

        print_success(f"Uploaded setup script to Blob Storage: {blob_url_with_sas}")

        # Create VNet and subnet
        vnet_name = f'{vm_name}-vnet'
        subnet_name = f'{vm_name}-subnet'
        print_info(f"Creating VNet '{vnet_name}' with subnet '{subnet_name}'.")

        network_client.virtual_networks.begin_create_or_update(
            resource_group,
            vnet_name,
            {
                'location': location,
                'address_space': {'address_prefixes': ['10.1.0.0/16']},
                'subnets': [{'name': subnet_name, 'address_prefix': '10.1.0.0/24'}]
            }
        ).result()
        print_success(f"Created VNet '{vnet_name}' with subnet '{subnet_name}'.")

        # Create Public IP
        public_ip_name = f'{vm_name}-public-ip'
        print_info(f"Creating Public IP '{public_ip_name}'.")
        public_ip_params = {
            'location': location,
            'public_ip_allocation_method': 'Dynamic'
        }
        public_ip = network_client.public_ip_addresses.begin_create_or_update(
            resource_group,
            public_ip_name,
            public_ip_params
        ).result()
        print_success(f"Created Public IP '{public_ip_name}'.")

        subnet_id = f'/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}'
        public_ip_id = f'/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/publicIPAddresses/{public_ip_name}'

        # Create or get NSG
        nsg_name = f'{vm_name}-nsg'
        print_info(f"Creating NSG '{nsg_name}'.")
        try:
            nsg = network_client.network_security_groups.get(resource_group, nsg_name)
            print_info(f"Found existing NSG '{nsg_name}'.")
        except Exception:
            nsg_params = NetworkSecurityGroup(location=location, security_rules=[])
            nsg = network_client.network_security_groups.begin_create_or_update(resource_group, nsg_name, nsg_params).result()
            print_success(f"Created NSG '{nsg_name}'.")

        # Add NSG rules for required ports
        print_info(f"Updating NSG '{nsg_name}' with required port rules.")
        existing_rules = {rule.name for rule in nsg.security_rules} if nsg.security_rules else set()
        priority = 100
        for port in PORTS_TO_OPEN:
            rule_name = f'AllowAnyCustom{port}Inbound' 
            if rule_name not in existing_rules:
                rule = SecurityRule(
                    name=rule_name,
                    access='Allow',
                    direction='Inbound',
                    priority=priority,
                    protocol='*',
                    source_address_prefix='*',
                    destination_address_prefix='*',
                    destination_port_range=str(port),
                    source_port_range='*'
                )
                nsg.security_rules.append(rule)
                priority += 1
        network_client.network_security_groups.begin_create_or_update(resource_group, nsg_name, nsg).result()
        print_success(f"Updated NSG '{nsg_name}' with required port rules.")

        # Create NIC
        print_info(f"Creating Network Interface '{vm_name}-nic'.")
        nic_params = NetworkInterface(
            location=location,
            ip_configurations=[{
                'name': f'{vm_name}-ip-config',
                'subnet': {'id': subnet_id},
                'public_ip_address': {'id': public_ip_id}
            }],
            network_security_group={'id': nsg.id}
        )
        nic = network_client.network_interfaces.begin_create_or_update(resource_group, f'{vm_name}-nic', nic_params).result()
        print_success(f"Created Network Interface '{vm_name}-nic'.")

        versions = compute_client.gallery_image_versions.list_by_gallery_image(
            GALLERY_IMAGE_RESOURCE_GROUP,
            GALLERY_NAME,
            GALLERY_IMAGE_NAME
        )
        if not versions:
            print_error(f"No image versions found in gallery '{GALLERY_NAME}' for image '{GALLERY_IMAGE_NAME}'.")
            sys.exit(1)
        # Pick the latest version by sorting or filtering
        latest_version = sorted(versions, key=lambda v: v.name)[-1].name
        print_info(f"Latest gallery image version found: {latest_version}")

        image_version_id = (
            f"/subscriptions/{subscription_id}/resourceGroups/{GALLERY_IMAGE_RESOURCE_GROUP}"
            f"/providers/Microsoft.Compute/galleries/{GALLERY_NAME}"
            f"/images/{GALLERY_IMAGE_NAME}/versions/{GALLERY_IMAGE_VERSION}"
        )

        image_latest_version_id = (
            f"/subscriptions/{subscription_id}/resourceGroups/{GALLERY_IMAGE_RESOURCE_GROUP}"
            f"/providers/Microsoft.Compute/galleries/{GALLERY_NAME}"
            f"/images/{GALLERY_IMAGE_NAME}/versions/{latest_version}"
        )

        #user can rather set the image version or 'latest'
        image_version_to_use = image_version_id
        if GALLERY_IMAGE_VERSION == 'latest':
            image_version_to_use = image_latest_version_id

        # Create VM
        print_info(f"Creating VM '{vm_name}'.")
        os_disk = {
            'name': f'{vm_name}-os-disk',
            'managed_disk': {
                'storage_account_type': 'Standard_LRS'},
            'create_option': 'FromImage',
            'disk_size_gb': f"{int(OS_DISK_SSD_GB)}"
        }

        # Use the gallery image version ID as the image reference
        image_reference = {
            'id': image_version_to_use
        }

        # Define Trusted Launch security profile
        security_profile = SecurityProfile(
            security_type="TrustedLaunch"
        )

        vm_parameters = VirtualMachine(
            location=location,
            hardware_profile=HardwareProfile(vm_size=vm_size),
            storage_profile=StorageProfile(os_disk=os_disk, image_reference=image_reference),
            network_profile=NetworkProfile(network_interfaces=[NetworkInterfaceReference(id=nic.id)]),
            security_profile=security_profile,
            zones=None
        )
        vm = compute_client.virtual_machines.begin_create_or_update(resource_group, vm_name, vm_parameters).result()
        print_success(f"Created VM '{vm_name}'.")

        # Wait for VM to be ready before extension
        print_info("Waiting 30 seconds for VM to initialize...")
        time.sleep(30)
        # Get public IP
        print_info(f"Retrieving VM Public IP: {public_ip}")
        nic_client = network_client.network_interfaces.get(resource_group, f'{vm_name}-nic')
        if not nic_client.ip_configurations or not nic_client.ip_configurations[0].public_ip_address:
            print_error("No public IP found on NIC. - Internat Azure Error. Azure VM didn't get public IP")
            await cleanup_resources_on_failure(
                network_client,
                compute_client,
                storage_client,
                blob_service_client,
                container_name,
                blob_name,
                dns_client,
                resource_group,
                domain,
                a_records,
                vm_name=vm_name,
                storage_account_name=storage_account_name
            )

            print_warn("-----------------------------------------------------")
            print_warn("Azure Windows VM provisioning failed with error")
            print_warn("-----------------------------------------------------")
            return func.HttpResponse(
                json.dumps({"error": "Azure Windows VM provisioning failed with error"}),
                status_code=500,
                mimetype="application/json"
            )
        
        public_ip_name = nic_client.ip_configurations[0].public_ip_address.id.split('/')[-1]
        public_ip_info = network_client.public_ip_addresses.get(resource_group, public_ip_name)
        public_ip = public_ip_info.ip_address
        print_success(f"VM Public IP: {public_ip}")

        # Create DNS Zone
        print_info(f"Creating DNS zone '{domain}'.")
        try:
            dns_zone = dns_client.zones.get(resource_group, domain)
            print_info(f"Found DNS zone '{domain}'.")
        except Exception:
            dns_zone = dns_client.zones.create_or_update(resource_group, domain, {'location': 'global'})
            print_success(f"Created DNS zone '{domain}'.")

        # Wait for DNS Zone to be ready before extension
        print_info("Waiting 5 seconds for DNS Zone to initialize...")
        time.sleep(5)
        a_records = [f'pin.{subdomain}',f'drop.{subdomain}',f'web.{subdomain}']
        if not check_ns_delegation_with_retries(dns_client, resource_group, domain):
            print_error("Stopping provisioning due to incorrect NS delegation.")
            await cleanup_resources_on_failure(
                network_client,
                compute_client,
                storage_client,
                blob_service_client,
                container_name,
                blob_name,
                dns_client,
                resource_group,
                domain,
                a_records,
                vm_name=vm_name,
                storage_account_name=storage_account_name
            )

            print_warn("-----------------------------------------------------")
            print_warn("Azure Windows VM provisioning failed with error")
            print_warn("-----------------------------------------------------")
            return func.HttpResponse(
                json.dumps({"error": "Azure Windows VM provisioning failed with error"}),
                status_code=500,
                mimetype="application/json"
            )

        # Create DNS A record for 'pin.subdomain' 'drop.v' 'web.subdomain'
        a_records = [f'pin.{subdomain}',f'drop.{subdomain}',f'web.{subdomain}']
        for a_record in a_records:
            print_info(f"Creating DNS A record for {a_record} for DNS Zone {domain} -> {public_ip}")
            a_record_set = RecordSet(ttl=3600, a_records=[{'ipv4_address': public_ip}])
            dns_client.record_sets.create_or_update(resource_group, domain, a_record, 'A', a_record_set)
            print_success(f"Created DNS  A record for {a_record} for DNS Zone {domain} -> {public_ip}")
            
        # Deploy Custom Script Extension to run PowerShell setup script
        print_info(f"Deploying Custom Script Extension to install script on VM.")
        ext_params = {
            'location': location,
            'publisher': 'Microsoft.Compute',
            'type': 'CustomScriptExtension',
            'type_handler_version': '1.10',
            'settings': {
                'fileUris': [blob_url_with_sas],
                'commandToExecute': f'powershell -ExecutionPolicy Unrestricted -File {blob_name}'
            },
        }
        extension = None
        try:
            extension = compute_client.virtual_machine_extensions.begin_create_or_update(
                resource_group,
                vm_name,
                'customScriptExtension',
                ext_params
            ).result(timeout=600)
        except Exception as e:
            print_error(f"Failed to deploy Custom Script Extension: {e}")
            await cleanup_resources_on_failure(
                network_client,
                compute_client,
                storage_client,
                blob_service_client,
                container_name,
                blob_name,
                dns_client,
                resource_group,
                domain,
                a_records,
                vm_name=vm_name,
                storage_account_name=storage_account_name
            )

            print_warn("-----------------------------------------------------")
            print_warn("Azure Windows VM provisioning failed with error")
            print_warn("-----------------------------------------------------")
            return func.HttpResponse(
                json.dumps({"error": "Azure Windows VM provisioning failed with error"}),
                status_code=500,
                mimetype="application/json"
            )

        if extension:
            print_success(f"Deployed Custom Script Extension '{extension.name}'.")
            # Starting cleanup process on successfull script extension install
            await cleanup_temp_storage_on_success(resource_group, storage_client, storage_account_name, blob_service_client, container_name, blob_name)
            # Wait for PC to be ready
            print_info("Waiting 30 seconds for PC to start...")
            time.sleep(30)
            print_success("-----------------------------------------------------")
            print_success("Azure Windows VM provisioning completed successfully!")
            print_success("-----------------------------------------------------")
            print_success(f"Pin moonlight service at:-----------------------------")
            print_success(f"https://pin.{subdomain}.{domain}")
            print_success(f"Drop files service at:-----------------------------")
            print_success(f"https://drop.{subdomain}.{domain}")
            print_success(f"Pin: {DUMBDROP_PIN}")
            print_success("-----------------------------------------------------")
            print_success("============================================================")
            print_success("✅ Moonlight to Browser Streaming Setup Complete!")
            print_success("============================================================")
            print_success("")
            print_success("🌐 Connection Information:")
            print_success("------------------------------------------------------------")
            print_success(f"🔗 Moonlight PIN Service: https://pin.{fqdn}")
            print_success(f"📁 File Drop Service: https://drop.{fqdn}")
            print_success(f"📁🔑 PIN: {DUMBDROP_PIN}")
            print_success("------------------------------------------------------------")
            print_success("")
            print_success("🎥 Streaming Access:")
            print_success("------------------------------------------------------------")
            print_success(f"https://{fqdn}/janus/streaming/test.html")
            print_success("2. Use these settings:")
            print_success("   - Video: H.264")
            print_success("   - Audio: Opus")
            print_success("   - Port: 5004")
            print_success("   - Secret: moonlightstream")
            print_success("------------------------------------------------------------")
            print_success("")
            print_success("⚙️ Service Status Commands:")
            print_success("------------------------------------------------------------")
            print_success("Janus Gateway: systemctl status janus.service")
            print_success("Moonlight Stream: systemctl status moonlight-stream.service")
            print_success("Nginx: systemctl status nginx")
            print_success("------------------------------------------------------------")
            print_success("")
            print_success("🔧 IMPORTANT Setup Notes:")
            print_success("------------------------------------------------------------")
            print_success("1. On your Windows 10 machine:")
            print_success("   - Install Sunshine from https://github.com/LizardByte/Sunshine")
            print_success(f"   - Use PIN from moonlight-embed when pairing")
            print_success("2. The stream will be available at the Janus test page")
            print_success("============================================================")
            #EMAIL SENDING
            smtp_host = os.environ.get('SMTP_HOST')
            smtp_port_str = os.environ.get('SMTP_PORT')
            smtp_user = os.environ.get('SMTP_USER')
            smtp_password = os.environ.get('SMTP_PASS')
            sender_email = os.environ.get('SENDER_EMAIL')
            recipient_emails_str = RECIPIENT_EMAILS  # Ensure this is set in env
            if not recipient_emails_str:
                print_error("RECIPIENT_EMAILS environment variable is not set.")
                #sys.exit(1)
            recipient_emails = [e.strip() for e in recipient_emails_str.split(',')]

            # Validate and convert smtp_port safely
            try:
                smtp_port = int(smtp_port_str)
            except (ValueError, TypeError):
                print_error(f"Invalid SMTP_PORT value: {smtp_port_str}")

            ssl_ip_address = domain
            # Build the HTML content correctly using keyword arguments (assuming html.HTMLEmail is a function/class)
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

            ###This is a pre-made HTML similar what users gets in email    
            print_success(f"https://cdn.sdappnet.cloud/rtx/rtxidtech.html?url={public_ip}")
            print_success("-----------------------------------------------------")
            # Construct the URL
            url = f"https://cdn.sdappnet.cloud/rtx/rtxidtech.html?url={public_ip}"
     
            result = {
                "message": "Your VM is ready to use",
                "vm_name": vm_name,
                "url": url,
            }
            return func.HttpResponse(
                    json.dumps(result),
                    status_code=200,
                    mimetype="application/json"
                )

    except Exception as ex:
        logging.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )