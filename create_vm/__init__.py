import asyncio
import json
import os
import sys
import time
import re
import aiohttp
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
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
    VirtualMachineExtension, WindowsConfiguration, SecurityProfile
)   
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import RecordSet
from azure.mgmt.storage import StorageManagementClient
import azure.functions as func

from . import generate_setup
from . import html_email
from . import html_email_send

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")

# WINDOWS-10 IMAGE
image_reference = {
    'publisher': 'MicrosoftWindowsDesktop',
    'offer': 'Windows-10',
    'sku': 'win10-22h2-pro-g2',
    'version': 'latest'
}

# Ports to open for application
PORTS_TO_OPEN = [22, 80, 443, 3389, 5000, 8000, 47984, 47989, 47990, 47998, 47999, 48000, 48010, 4531, 3475]

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

# Async helper function
async def run_azure_operation(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing create_vm request...')    
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Extract parameters with defaults
        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        domain = req_body.get('domain') or req.params.get('domain')
        location = req_body.get('location') or req.params.get('location')
        vm_size = req_body.get('vm_size') or req.params.get('vm_size')
        storage_account_base = vm_name

        # Image/Windows configuration
        GALLERY_IMAGE_RESOURCE_GROUP = req_body.get('gallery_image_resource_group') or req.params.get('gallery_image_resource_group')
        GALLERY_NAME = req_body.get('gallery_name') or req.params.get('gallery_name')
        GALLERY_IMAGE_NAME = req_body.get('gallery_image_name') or req.params.get('gallery_image_name')
        GALLERY_IMAGE_VERSION = req_body.get('gallery_image_version') or req.params.get('gallery_image_version') or 'latest'
        OS_DISK_SSD_GB = int(req_body.get('os_disk_ssd_gb') or req.params.get('os_disk_ssd_gb') or 256)
        WINDOWS_IMAGE_PASSWORD = req_body.get('windows_image_password') or req.params.get('windows_image_password')
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')
        DUMBDROP_PIN = req_body.get('dumbdrop_pin') or req.params.get('dumbdrop_pin') or '1234'
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''

        # Validate required parameters
        missing_params = [p for p in ["vm_name", 
                                      "resource_group", 
                                      "domain", 
                                      "location", 
                                      "vm_size", 
                                      "GALLERY_IMAGE_RESOURCE_GROUP", 
                                      "GALLERY_NAME", 
                                      "GALLERY_IMAGE_NAME",
                                      "WINDOWS_IMAGE_PASSWORD",
                                      "RECIPIENT_EMAILS"] if not locals()[p]]
        if missing_params:
            return func.HttpResponse(
                json.dumps({"error": f"Missing parameters: {', '.join(missing_params)}"}),
                status_code=400,
                mimetype="application/json",
            )
        
        # Domain validation
        if '.' not in domain or domain.startswith('.') or len(domain.split('.')) > 2:
            return func.HttpResponse(
                json.dumps({"error": "Invalid domain format"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # VM size validation
        if not check_vm_size_compatibility(vm_size):
            return func.HttpResponse(
                json.dumps({
                    "error": f"VM size {vm_size} is incompatible",
                    "compatible_sizes": get_compatible_vm_sizes()
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Initial status update
        hook_response = await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "init",
                    "vm_name": vm_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        if not hook_response.get("success") and hook_url:
            error_msg = hook_response.get("error", "Unknown error posting status")
            print_error(f"Initial status update failed: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": f"Status update failed: {error_msg}"}),
                status_code=500,
                mimetype="application/json"
            )

        status_url = hook_response.get("status_url", "")

        try:
            # Azure authentication
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "authenticating",
                        "message": "Authenticating with Azure"
                    }
                }
            )
            
            # Validate environment variables
            required_vars = ['AZURE_APP_CLIENT_ID', 'AZURE_APP_CLIENT_SECRET', 
                            'AZURE_APP_TENANT_ID', 'AZURE_SUBSCRIPTION_ID']
            missing = [var for var in required_vars if not os.environ.get(var)]
            if missing:
                raise Exception(f"Missing environment variables: {', '.join(missing)}")

            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )

            # Start background provisioning
            asyncio.create_task(
                provision_vm_background(
                    credentials,
                    vm_name, resource_group, domain, location, vm_size,
                    storage_account_base, GALLERY_IMAGE_RESOURCE_GROUP, GALLERY_NAME,
                    GALLERY_IMAGE_NAME, GALLERY_IMAGE_VERSION, OS_DISK_SSD_GB,
                    WINDOWS_IMAGE_PASSWORD, RECIPIENT_EMAILS, DUMBDROP_PIN, hook_url
                )
            )

            #✅background-task started, hook_vm will be notified during setup
            return func.HttpResponse(
                json.dumps({
                    "message": "VM provisioning started",
                    "status_url": status_url,
                    "vm_name": vm_name
                }),
                status_code=202,
                mimetype="application/json"
            )

        except Exception as ex:
            logging.exception("Authentication error:")
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "authentication_error",
                        "error": str(ex),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return func.HttpResponse(
                json.dumps({"error": str(ex)}),
                status_code=500,
                mimetype="application/json"
            )

    except Exception as ex:
        logging.exception("Unhandled error in main function:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )
    

async def provision_vm_background(
    credentials,
    vm_name, resource_group, domain, location, vm_size,
    storage_account_base, GALLERY_IMAGE_RESOURCE_GROUP, GALLERY_NAME,
    GALLERY_IMAGE_NAME, GALLERY_IMAGE_VERSION, OS_DISK_SSD_GB,
    WINDOWS_IMAGE_PASSWORD, RECIPIENT_EMAILS, DUMBDROP_PIN, hook_url
):
    try:
        # Initial status update
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "starting_provisioning", 
                    "message": "Beginning VM provisioning process",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        
        # Initialize Azure clients
        compute_client = ComputeManagementClient(credentials, subscription_id)
        storage_client = StorageManagementClient(credentials, subscription_id)
        network_client = NetworkManagementClient(credentials, subscription_id)
        dns_client = DnsManagementClient(credentials, subscription_id)
        
        # Handle subdomain
        subdomain = vm_name.strip().strip('.') if vm_name else None
        fqdn = f"{subdomain}.{domain}" if subdomain else domain
        print_info(f"Full domain to configure: {fqdn}")

        # Create storage account
        storage_account_name = f"{storage_account_base}{int(time.time()) % 10000}"
        try:            
            storage_config = await run_azure_operation(
                create_storage_account,
                storage_client,
                resource_group,
                storage_account_name,
                location
            )
            global AZURE_STORAGE_ACCOUNT_KEY
            AZURE_STORAGE_ACCOUNT_KEY = storage_config["AZURE_STORAGE_KEY"]
            AZURE_STORAGE_URL = storage_config["AZURE_STORAGE_URL"]
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "storage_created",
                        "message": "Storage account created successfully",
                        "storage_account_name": storage_account_name
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create storage account: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "storage_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Generate and upload setup script
        print_info("Generating PowerShell setup script...")
        ssl_email = os.environ.get('SENDER_EMAIL')
        ps_script = generate_setup.generate_setup(vm_name, fqdn, ssl_email, DUMBDROP_PIN, WINDOWS_IMAGE_PASSWORD)
        
        blob_service_client = BlobServiceClient(account_url=AZURE_STORAGE_URL, credential=credentials)
        container_name = 'vm-startup-scripts'
        blob_name = f"{vm_name}-setup.ps1"

        try:
            blob_url_with_sas = await run_azure_operation(
                upload_blob_and_generate_sas,
                blob_service_client, 
                container_name, 
                blob_name, 
                ps_script, 
                2
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "script_uploaded",
                        "message": "Setup script uploaded successfully"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to generate or upload setup script: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "script_upload_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Network infrastructure setup
        vnet_name = f'{vm_name}-vnet'
        subnet_name = f'{vm_name}-subnet'
        public_ip_name = f'{vm_name}-public-ip'
        nsg_name = f'{vm_name}-nsg'
        
        # Create virtual network
        try:            
            vnet_operation = network_client.virtual_networks.begin_create_or_update(
                resource_group,
                vnet_name,
                {
                    'location': location,
                    'address_space': {'address_prefixes': ['10.1.0.0/16']},
                    'subnets': [{'name': subnet_name, 'address_prefix': '10.1.0.0/24'}]
                }
            )
            await run_azure_operation(vnet_operation.result)
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "vnet_created",
                        "message": f"Virtual network {vnet_name} created"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create virtual network: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "vnet_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create public IP
        try:            
            public_ip_params = {
                'location': location,
                'public_ip_allocation_method': 'Dynamic'
            }
            ip_operation = network_client.public_ip_addresses.begin_create_or_update(
                resource_group,
                public_ip_name,
                public_ip_params
            )
            public_ip = await run_azure_operation(ip_operation.result)
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "public_ip_created",
                        "message": f"Public IP {public_ip_name} created"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create public IP: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "public_ip_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        subnet_id = f'/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}'
        public_ip_id = f'/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/publicIPAddresses/{public_ip_name}'

        # Create or update NSG
        try:
            nsg = None
            try:
                nsg = await run_azure_operation(
                    network_client.network_security_groups.get,
                    resource_group,
                    nsg_name
                )
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "provisioning",
                        "resource_group": resource_group,
                        "location": location,
                        "details": {
                            "step": "nsg_found",
                            "message": f"Using existing NSG {nsg_name}"
                        }
                    }
                )
            except Exception:
                nsg_params = NetworkSecurityGroup(location=location, security_rules=[])
                nsg_operation = network_client.network_security_groups.begin_create_or_update(
                    resource_group, 
                    nsg_name, 
                    nsg_params
                )
                nsg = await run_azure_operation(nsg_operation.result)
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "provisioning",
                        "resource_group": resource_group,
                        "location": location,
                        "details": {
                            "step": "nsg_created",
                            "message": f"Created new NSG {nsg_name}"
                        }
                    }
                )

            # Add NSG rules
            existing_rules = {rule.name for rule in nsg.security_rules} if nsg.security_rules else set()
            existing_priorities = {rule.priority for rule in nsg.security_rules if rule.direction == 'Inbound'} if nsg.security_rules else set()
            priority = max(existing_priorities) + 1 if existing_priorities else 100

            for port in PORTS_TO_OPEN:
                rule_name = f'AllowAnyCustom{port}Inbound'
                if rule_name not in existing_rules:
                    while priority in existing_priorities or priority < 100 or priority > 4096:
                        priority += 1
                        if priority > 4096:
                            error_msg = "Exceeded max NSG priority limit of 4096"
                            await post_status_update(
                                hook_url=hook_url,
                                status_data={
                                    "vm_name": vm_name,
                                    "status": "failed",
                                    "resource_group": resource_group,
                                    "location": location,
                                    "details": {
                                        "step": "nsg_rule_failed",
                                        "error": error_msg,
                                        "timestamp": datetime.utcnow().isoformat()
                                    }
                                }
                            )
                            return

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
                    existing_priorities.add(priority)
                    priority += 1

            nsg_operation = network_client.network_security_groups.begin_create_or_update(
                resource_group,
                nsg_name,
                nsg
            )
            await run_azure_operation(nsg_operation.result)
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "nsg_rules_added",
                        "message": f"Added {len(PORTS_TO_OPEN)} security rules"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to configure NSG: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "nsg_configuration_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create NIC
        try:
            nic_params = {
                'location': location,
                'ip_configurations': [{
                    'name': f'{vm_name}-ip-config',
                    'subnet': {'id': subnet_id},
                    'public_ip_address': {'id': public_ip_id}
                }],
                'network_security_group': {'id': nsg.id}
            }
            nic_operation = network_client.network_interfaces.begin_create_or_update(
                resource_group, 
                f'{vm_name}-nic', 
                nic_params
            )
            nic = await run_azure_operation(nic_operation.result)
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "nic_created",
                        "message": "Network interface created successfully"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create network interface: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "nic_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create VM
        try:            
            # Get gallery image version
            versions = await run_azure_operation(
                compute_client.gallery_image_versions.list_by_gallery_image,
                GALLERY_IMAGE_RESOURCE_GROUP,
                GALLERY_NAME,
                GALLERY_IMAGE_NAME
            )
            
            if not versions:
                error_msg = f"No image versions found in gallery '{GALLERY_NAME}' for image '{GALLERY_IMAGE_NAME}'."
                print_error(error_msg)
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "failed",
                        "resource_group": resource_group,
                        "location": location,
                        "details": {
                            "step": "vm_creation_failed",
                            "error": error_msg,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                return
            
            # Pick the latest version
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

            # Use the appropriate image version
            image_version_to_use = image_version_id
            if GALLERY_IMAGE_VERSION == 'latest':
                image_version_to_use = image_latest_version_id

            print_info(f"VM_Image: '{GALLERY_IMAGE_NAME}'.")
            print_info(f"VM_Image_Version: '{image_version_to_use}'.")

            # Create VM configuration
            os_disk = {
                'name': f'{vm_name}-os-disk',
                'managed_disk': {'storage_account_type': 'Standard_LRS'},
                'create_option': 'FromImage',
                'disk_size_gb': OS_DISK_SSD_GB
            }

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
            
            vm_operation = compute_client.virtual_machines.begin_create_or_update(
                resource_group, 
                vm_name, 
                vm_parameters
            )
            vm = await run_azure_operation(vm_operation.result)
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "vm_created",
                        "message": "Virtual machine created successfully",
                        "vm_size": vm_size,
                        "os_disk_size_gb": OS_DISK_SSD_GB
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create virtual machine: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "vm_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Wait for VM initialization
        await asyncio.sleep(30)

        a_records = [f'pin.{subdomain}',f'drop.{subdomain}',f'web.{subdomain}']
        # Verify public IP assignment
        try:            
            nic_client = await run_azure_operation(
                network_client.network_interfaces.get,
                resource_group,
                f'{vm_name}-nic'
            )
            if not nic_client.ip_configurations or not nic_client.ip_configurations[0].public_ip_address:
                error_msg = "No public IP found on NIC"
                print_error(error_msg)
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
                    vm_name,
                    storage_account_name
                )
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "failed",
                        "resource_group": resource_group,
                        "location": location,
                        "details": {
                            "step": "public_ip_verification_failed",
                            "error": error_msg,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                return

            public_ip_name = nic_client.ip_configurations[0].public_ip_address.id.split('/')[-1]
            public_ip_info = await run_azure_operation(
                network_client.public_ip_addresses.get,
                resource_group,
                public_ip_name
            )
            public_ip = public_ip_info.ip_address
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "public_ip_confirmed",
                        "message": f"VM public IP: {public_ip}"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to verify public IP: {str(e)}"
            print_error(error_msg)
            
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
                vm_name,
                storage_account_name
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "public_ip_verification_error",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # DNS Configuration
        try:            
            # Create DNS Zone
            try:
                dns_zone = await run_azure_operation(
                    dns_client.zones.get,
                    resource_group,
                    domain
                )
            except Exception:
                zone_operation = await run_azure_operation(
                    dns_client.zones.create_or_update,
                    resource_group, 
                    domain, 
                    {'location': 'global'}
                )
                dns_zone = await run_azure_operation(zone_operation.result)
                await asyncio.sleep(5)  # Wait for DNS zone initialization
                
            # Verify NS delegation
            if not await check_ns_delegation_with_retries(dns_client, resource_group, domain):
                error_msg = "Incorrect NS delegation for DNS zone"
                print_error(error_msg)
                
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
                    vm_name,
                    storage_account_name
                )
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "failed",
                        "resource_group": resource_group,
                        "location": location,
                        "details": {
                            "step": "ns_delegation_failed",
                            "error": error_msg,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                return

            # Create DNS A records
            for a_record in a_records:
                a_record_set = RecordSet(
                    ttl=3600, 
                    a_records=[{'ipv4_address': public_ip}]
                )
                await run_azure_operation(
                    dns_client.record_sets.create_or_update,
                    resource_group, 
                    domain, 
                    a_record, 
                    'A', 
                    a_record_set
                )
                
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "dns_records_created",
                        "message": "DNS records configured successfully"
                    }
                }
            )
        except Exception as e:
            error_msg = f"DNS configuration failed: {str(e)}"
            print_error(error_msg)
            
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
                vm_name,
                storage_account_name
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "dns_configuration_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Install Custom Script Extension
        try:
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
            extension_operation = compute_client.virtual_machine_extensions.begin_create_or_update(
                resource_group,
                vm_name,
                'customScriptExtension',
                ext_params
            )
            extension = await run_azure_operation(extension_operation.result, timeout=600)
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "extension_installed",
                        "message": "Custom script extension installed"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to install custom script extension: {str(e)}"
            print_error(error_msg)
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
                vm_name,
                storage_account_name
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "extension_installation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Cleanup temporary storage
        try:            
            await cleanup_temp_storage_on_success(
                resource_group, 
                storage_client, 
                storage_account_name, 
                blob_service_client, 
                container_name, 
                blob_name
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "cleanup_complete",
                        "message": "Temporary resources cleaned up"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Cleanup failed (non-critical): {str(e)}"
            print_warn(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "cleanup_warning",
                        "warning": error_msg
                    }
                }
            )

        # Final wait
        await asyncio.sleep(30)

        # Send completion email
        try:
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "sending_email",
                        "message": "Sending completion email"
                    }
                }
            )
            
            smtp_host = os.environ.get('SMTP_HOST')
            smtp_port = int(os.environ.get('SMTP_PORT', 587))
            smtp_user = os.environ.get('SMTP_USER')
            smtp_password = os.environ.get('SMTP_PASS')
            sender_email = os.environ.get('SENDER_EMAIL')
            recipient_emails = [e.strip() for e in RECIPIENT_EMAILS.split(',')]
            
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

            await run_azure_operation(
                html_email_send.send_html_email_smtp,
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
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "email_sent",
                        "message": "Completion email sent"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            print_warn(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "email_failed",
                        "warning": error_msg
                    }
                }
            )

        # Final success update
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "completed",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "completed",
                    "message": "VM provisioning successful",
                    "public_ip": public_ip,
                    "url": f"https://cdn.sdappnet.cloud/rtx/rtxidtech.html?url={public_ip}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        print_success(f"Azure Windows VM provisioning completed successfully!")
        print_success(f"Pin moonlight service at: https://pin.{subdomain}.{domain}")
        print_success(f"Drop files service at: https://drop.{subdomain}.{domain}")
        print_success(f"Pin: {DUMBDROP_PIN}")
        
    except Exception as e:
        # Top-level error handler for background task
        error_msg = f"Unhandled exception in background task: {str(e)}"
        print_error(error_msg)
        
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "failed",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "background_task_failed",
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
        
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
            vm_name,
            storage_account_name
        )


async def create_storage_account(storage_client, resource_group_name, storage_name, location):
    print_info(f"Creating storage account '{storage_name}' in '{location}'...")
    try:
        try:
            await run_azure_operation(
                storage_client.storage_accounts.get_properties,
                resource_group_name,
                storage_name
            )
            print_info(f"Storage account '{storage_name}' already exists.")
        except:
            poller = await run_azure_operation(
                storage_client.storage_accounts.begin_create,
                resource_group_name,
                storage_name,
                {
                    "sku": {"name": "Standard_LRS"},
                    "kind": "StorageV2",
                    "location": location,
                    "enable_https_traffic_only": True
                }
            )
            await run_azure_operation(poller.result)
            print_success(f"Storage account '{storage_name}' created.")

        keys = await run_azure_operation(
            storage_client.storage_accounts.list_keys,
            resource_group_name,
            storage_name
        )
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
    await run_azure_operation(blob_client.upload_blob, data, overwrite=True)
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
    return vm_size in get_compatible_vm_sizes()

async def check_ns_delegation_with_retries(dns_client, resource_group, domain, retries=5, delay=10):
    for attempt in range(1, retries + 1):
        if await check_ns_delegation(dns_client, resource_group, domain):
            return True
        print_warn(f"\n⚠️ Retrying NS delegation check in {delay} seconds... (Attempt {attempt}/{retries})")
        await asyncio.sleep(delay)
    return False

async def check_ns_delegation(dns_client, resource_group, domain):
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
        dns_zone = await run_azure_operation(dns_client.zones.get, resource_group, domain)
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

async def cleanup_resources_on_failure(
    network_client, compute_client, storage_client, blob_service_client, 
    container_name, blob_name, dns_client, resource_group, domain, 
    a_records, vm_name, storage_account_name
):
    print_warn("Starting cleanup of Azure resources due to failure...")

    # Delete VM
    try:
        vm = await run_azure_operation(compute_client.virtual_machines.get, resource_group, vm_name)
        os_disk_name = vm.storage_profile.os_disk.name
        await run_azure_operation(
            compute_client.virtual_machines.begin_delete(resource_group, vm_name).result
        )
        print_info(f"Deleted VM '{vm_name}'.")
    except Exception as e:
        print_warn(f"Could not delete VM '{vm_name}': {e}")
        os_disk_name = None

    # Delete OS disk if available
    if os_disk_name:
        try:
            await run_azure_operation(
                compute_client.disks.begin_delete(resource_group, os_disk_name).result
            )
            print_info(f"Deleted OS disk '{os_disk_name}'.")
        except Exception as e:
            print_warn(f"Could not delete OS disk '{os_disk_name}': {e}")

    # Delete NIC
    try:
        await run_azure_operation(
            network_client.network_interfaces.begin_delete(resource_group, f"{vm_name}-nic").result
        )
        print_info(f"Deleted NIC '{vm_name}-nic'.")
    except Exception as e:
        print_warn(f"Could not delete NIC '{vm_name}-nic': {e}")

    # Delete NSG
    try:
        await run_azure_operation(
            network_client.network_security_groups.begin_delete(resource_group, f"{vm_name}-nsg").result
        )
        print_info(f"Deleted NSG '{vm_name}-nsg'.")
    except Exception as e:
        print_warn(f"Could not delete NSG '{vm_name}-nsg': {e}")

    # Delete Public IP
    try:
        await run_azure_operation(
            network_client.public_ip_addresses.begin_delete(resource_group, f"{vm_name}-public-ip").result
        )
        print_info(f"Deleted Public IP '{vm_name}-public-ip'.")
    except Exception as e:
        print_warn(f"Could not delete Public IP '{vm_name}-public-ip': {e}")

    # Delete VNet
    try:
        await run_azure_operation(
            network_client.virtual_networks.begin_delete(resource_group, f"{vm_name}-vnet").result
        )
        print_info(f"Deleted VNet '{vm_name}-vnet'.")
    except Exception as e:
        print_warn(f"Could not delete VNet '{vm_name}-vnet': {e}")

    # Delete Storage Account
    try:
        print_info(f"Deleting blob '{blob_name}' from container '{container_name}'.")
        container_client = blob_service_client.get_container_client(container_name)
        await run_azure_operation(container_client.delete_blob, blob_name)
        print_success(f"Deleted blob '{blob_name}' from container '{container_name}'.")
        
        print_info(f"Deleting container '{container_name}'.")
        await run_azure_operation(blob_service_client.delete_container, container_name)
        print_success(f"Deleted container '{container_name}'.")
        
        print_info(f"Deleting storage account '{storage_account_name}'.")
        await run_azure_operation(
            storage_client.storage_accounts.delete, resource_group, storage_account_name
        )
        print_success(f"Deleted storage account '{storage_account_name}'.")
    except Exception as e:
        print_warn(f"Could not delete Storage Account '{storage_account_name}': {e}")

    # Delete DNS A record (keep DNS zone)
    for record_name in a_records:
        record_to_delete = record_name if record_name else '@'  # handle root domain with '@'
        try:
            await run_azure_operation(
                dns_client.record_sets.delete, resource_group, domain, record_to_delete, 'A'
            )
            print_info(f"Deleted DNS A record '{record_to_delete}' in zone '{domain}'.")
        except Exception as e:
            print_warn(f"Could not delete DNS A record '{record_to_delete}' in zone '{domain}': {e}")

    print_success("Cleanup completed.")

async def cleanup_temp_storage_on_success(
    resource_group, storage_client, storage_account_name, 
    blob_service_client, container_name, blob_name
):
    print_info("Starting cleanup of Azure resources on success...")

    # Delete Storage Account
    try:
        print_info(f"Deleting blob '{blob_name}' from container '{container_name}'.")
        container_client = blob_service_client.get_container_client(container_name)
        await run_azure_operation(container_client.delete_blob, blob_name)
        print_success(f"Deleted blob '{blob_name}' from container '{container_name}'.")
        
        print_info(f"Deleting container '{container_name}'.")
        await run_azure_operation(blob_service_client.delete_container, container_name)
        print_success(f"Deleted container '{container_name}'.")
        
        print_info(f"Deleting storage account '{storage_account_name}'.")
        await run_azure_operation(
            storage_client.storage_accounts.delete, resource_group, storage_account_name
        )
        print_success(f"Deleted storage account '{storage_account_name}'.")
    except Exception as e:
        print_warn(f"Could not delete Storage Account '{storage_account_name}': {e}")

    print_success("Temp storage cleanup completed.")

 


# ====================== STATUS UPDATE FUNCTION ======================
async def post_status_update(hook_url: str, status_data: dict) -> dict:
    """Send status update to webhook with retry logic"""
    if not hook_url:
        return {"success": True, "status_url": ""}
    
    step = status_data.get("details", {}).get("step", "unknown")
    print_info(f"Sending status update for step: {step}")
    
    # Retry configuration
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    hook_url,
                    json=status_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "status_url": data.get("status_url", ""),
                            "response": data
                        }
                    else:
                        error_msg = f"HTTP {response.status}"
        except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
            error_msg = str(e)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
        
        # Log failure and retry
        if attempt < max_retries:
            print_warn(f"Status update failed (attempt {attempt}/{max_retries}): {error_msg}")
            await asyncio.sleep(retry_delay * attempt)  # Exponential backoff
        else:
            print_error(f"Status update failed after {max_retries} attempts: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_url": ""
            }
    
    return {"success": False, "error": "Unknown error", "status_url": ""}