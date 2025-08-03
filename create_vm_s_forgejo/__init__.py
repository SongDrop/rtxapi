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
import requests
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
    VirtualMachineExtension, WindowsConfiguration,SecurityProfile,
    LinuxConfiguration
)   
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import RecordSet
from azure.mgmt.storage import StorageManagementClient
import azure.functions as func
import aiohttp
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

image_reference = {
    'publisher': 'canonical',
    'offer': 'ubuntu-24_04-lts',
    'sku': 'server',
    'version': 'latest',
    'exactVersion': '24.04.202409120'
}

# Ports to open for application [without this app can't run on domain]
PORTS_TO_OPEN = [
    22,     # SSH
    80,     # HTTP
    443,    # HTTPS
    8000,   # Optional app port (if used)
    3000,   # Optional app port (if used)
    8889,
    8890,
    7088,
    8088
]

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


async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing create_vm request...')
 
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        #Get paramenters
        username = req_body.get('username') or req.params.get('username') or 'azureuser'
        password = req_body.get('password') or req.params.get('password') or 'azurepassword1234!'
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
        vm_size = req_body.get('vm_size') or req.params.get('vm_size') or 'Standard_D2s_v3' #Standard_D2s_v3
        storage_account_base = vm_name

        OS_DISK_SSD_GB = int(req_body.get('os_disk_ssd_gb') or req.params.get('os_disk_ssd_gb') or 256)
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')
        #windows user is always 'source' to keep it simple
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''

        ADMIN_EMAIL = f"admin@{domain}"
        ADMIN_PASSWORD = "MyPass1234!"
        FRONTEND_PORT = 3000
        BACKEND_PORT = 8000

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
        if not RECIPIENT_EMAILS:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'recipient_emails' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
    
        hook_response = await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "init", 
                    "vm_name": vm_name
                }
            }
        )
        # Handle hook response
        if not hook_response.get("success"):
            error_msg = hook_response.get("error", "Unknown error posting status")
            print_error(f"Initial status update failed: {error_msg}")
            if not hook_url:
                print_info("Proceeding without status updates (no hook_url provided)")
            else:
                return func.HttpResponse(
                    json.dumps({"error": f"Status update failed: {error_msg}"}),
                    status_code=500,
                    mimetype="application/json"
                )

        status_url = hook_response.get("status_url", "")

        # Start the long-running operation in the background
        # Using asyncio.create_task to run it in parallel
        asyncio.create_task(
            provision_vm_background(
                username, password, vm_name, resource_group, 
                domain, subdomain, fqdn, location, vm_size,
                storage_account_base, OS_DISK_SSD_GB, RECIPIENT_EMAILS, 
                hook_url, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT
            )
        )

        # Return immediate response with status URL
        return func.HttpResponse(
            json.dumps({
                "message": "VM provisioning started",
                "status_url": status_url,
                "vm_name": vm_name
            }),
            status_code=202,  # Accepted
            mimetype="application/json"
        )
 

    except Exception as ex:
        logging.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )

async def provision_vm_background(
    username, password, vm_name, resource_group, 
    domain, subdomain, fqdn, location, vm_size,
    storage_account_base, OS_DISK_SSD_GB, RECIPIENT_EMAILS, 
    hook_url, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT
):
    try:
        # Initial status update - Starting provisioning
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

        # Authenticate with Azure
        try:
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "authenticating",
                        "message": "Authenticating with Azure"
                    }
                }
            )
            
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
        except KeyError as e:
            err = f"Missing environment variable: {e}"
            print_error(err)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "authentication_failed",
                        "error": err,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            error_msg = "AZURE_SUBSCRIPTION_ID environment variable not set"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "configuration_error",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Initialize Azure clients
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "initializing_clients",
                    "message": "Setting up Azure service clients"
                }
            }
        )
        
        compute_client = ComputeManagementClient(credentials, subscription_id)
        storage_client = StorageManagementClient(credentials, subscription_id)
        network_client = NetworkManagementClient(credentials, subscription_id)
        resource_client = ResourceManagementClient(credentials, subscription_id)
        dns_client = DnsManagementClient(credentials, subscription_id)

        # Create storage account
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "creating_storage",
                    "message": "Setting up storage account",
                    "storage_account_name": f"{storage_account_base}{int(time.time()) % 10000}"
                }
            }
        )

        storage_account_name = f"{storage_account_base}{int(time.time()) % 10000}"
        try:
            storage_config = await create_storage_account(storage_client, resource_group, storage_account_name, location)
            global AZURE_STORAGE_ACCOUNT_KEY
            AZURE_STORAGE_ACCOUNT_KEY = storage_config["AZURE_STORAGE_KEY"]
            AZURE_STORAGE_URL = storage_config["AZURE_STORAGE_URL"]
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
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
                    "details": {
                        "step": "storage_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return
        
        # Generate setup script
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "generating_setup_script",
                    "message": "Generating VM setup script"
                }
            }
        )

        sh_script = generate_setup.generate_setup(
            fqdn, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT
        )
        record_name = subdomain.rstrip('.') if subdomain else '@'
        a_records = [record_name]

        # Upload script to blob storage
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "uploading_script",
                    "message": "Uploading setup script to blob storage"
                }
            }
        )

        blob_service_client = BlobServiceClient(account_url=AZURE_STORAGE_URL, credential=credentials)
        container_name = 'vm-startup-scripts'
        blob_name = f"{vm_name}-setup.sh"

        try:
            blob_url_with_sas = await upload_blob_and_generate_sas(
                blob_service_client, 
                container_name, 
                blob_name, 
                sh_script, 
                sas_expiry_hours=2
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "script_uploaded",
                        "message": "Setup script uploaded successfully",
                        "blob_url": blob_url_with_sas
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to upload setup script: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "details": {
                        "step": "script_upload_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Network infrastructure setup
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "network_setup",
                    "message": "Configuring network infrastructure"
                }
            }
        )

        # Create VNet and subnet
        vnet_name = f'{vm_name}-vnet'
        subnet_name = f'{vm_name}-subnet'
        
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "creating_vnet",
                    "message": f"Creating virtual network {vnet_name} with subnet {subnet_name}"
                }
            }
        )

        try:
            async_vnet_creation = network_client.virtual_networks.begin_create_or_update(
                resource_group,
                vnet_name,
                {
                    'location': location,
                    'address_space': {'address_prefixes': ['10.1.0.0/16']},
                    'subnets': [{'name': subnet_name, 'address_prefix': '10.1.0.0/24'}]
                }
            )
            await async_vnet_creation.result()
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "vnet_created",
                        "message": f"Virtual network {vnet_name} created successfully"
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
                    "details": {
                        "step": "vnet_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create Public IP
        public_ip_name = f'{vm_name}-public-ip'
        
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "creating_public_ip",
                    "message": f"Creating public IP {public_ip_name}"
                }
            }
        )

        try:
            public_ip_params = {
                'location': location,
                'public_ip_allocation_method': 'Dynamic'
            }
            async_public_ip = network_client.public_ip_addresses.begin_create_or_update(
                resource_group,
                public_ip_name,
                public_ip_params
            )
            public_ip = await async_public_ip.result()
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "public_ip_created",
                        "message": f"Public IP {public_ip_name} created successfully"
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

        # Create or get NSG
        nsg_name = f'{vm_name}-nsg'
        
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "configuring_nsg",
                    "message": f"Configuring network security group {nsg_name}"
                }
            }
        )

        try:
            nsg = None
            try:
                nsg = await network_client.network_security_groups.get(resource_group, nsg_name)
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "provisioning",
                        "details": {
                            "step": "nsg_found",
                            "message": f"Using existing NSG {nsg_name}"
                        }
                    }
                )
            except Exception:
                nsg_params = NetworkSecurityGroup(location=location, security_rules=[])
                async_nsg_creation = network_client.network_security_groups.begin_create_or_update(
                    resource_group, 
                    nsg_name, 
                    nsg_params
                )
                nsg = await async_nsg_creation.result()
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "provisioning",
                        "details": {
                            "step": "nsg_created",
                            "message": f"Created new NSG {nsg_name}"
                        }
                    }
                )

            # Add NSG rules
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "adding_nsg_rules",
                        "message": f"Adding security rules to NSG {nsg_name}"
                    }
                }
            )

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

            async_nsg_update = network_client.network_security_groups.begin_create_or_update(resource_group, nsg_name, nsg)
            await async_nsg_update.result()
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "nsg_rules_added",
                        "message": f"Added {len(PORTS_TO_OPEN)} security rules to NSG {nsg_name}"
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
                    "details": {
                        "step": "nsg_configuration_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create NIC
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "creating_nic",
                    "message": f"Creating network interface for {vm_name}"
                }
            }
        )

        try:
            nic_params = NetworkInterface(
                location=location,
                ip_configurations=[{
                    'name': f'{vm_name}-ip-config',
                    'subnet': {'id': subnet_id},
                    'public_ip_address': {'id': public_ip_id}
                }],
                network_security_group={'id': nsg.id}
            )
            async_nic_creation = network_client.network_interfaces.begin_create_or_update(
                resource_group, 
                f'{vm_name}-nic', 
                nic_params
            )
            nic = await async_nic_creation.result()
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "nic_created",
                        "message": f"Network interface {vm_name}-nic created successfully"
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
                    "details": {
                        "step": "nic_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create VM
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "creating_vm",
                    "message": f"Creating virtual machine {vm_name}"
                }
            }
        )

        try:
            os_disk = {
                'name': f'{vm_name}-os-disk',
                'managed_disk': {
                    'storage_account_type': 'Standard_LRS'
                    },
                'create_option': 'FromImage',
                'disk_size_gb': f"{int(OS_DISK_SSD_GB)}"
            }
            os_profile = OSProfile(
                computer_name=vm_name,
                admin_username=username,
                admin_password=password,
                linux_configuration=LinuxConfiguration(
                    disable_password_authentication=False
                )
            )
            vm_parameters = VirtualMachine(
                location=location,
                hardware_profile=HardwareProfile(vm_size=vm_size),
                storage_profile=StorageProfile(os_disk=os_disk, image_reference=image_reference),
                os_profile=os_profile,
                network_profile=NetworkProfile(network_interfaces=[NetworkInterfaceReference(id=nic.id)]),
                zones=None
            )
            async_vm_creation = compute_client.virtual_machines.begin_create_or_update(
                resource_group, 
                vm_name, 
                vm_parameters
            )
            vm = await async_vm_creation.result()
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "vm_created",
                        "message": f"Virtual machine {vm_name} created successfully",
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
                    "details": {
                        "step": "vm_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Wait for VM to initialize
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "vm_initializing",
                    "message": "Waiting for VM to initialize (30 seconds)"
                }
            }
        )
        await asyncio.sleep(30)

        # Verify public IP assignment
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "verifying_public_ip",
                    "message": "Verifying public IP assignment"
                }
            }
        )

        try:
            nic_client = await network_client.network_interfaces.get(resource_group, f'{vm_name}-nic')
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
                    vm_name=vm_name,
                    storage_account_name=storage_account_name
                )
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "failed",
                        "details": {
                            "step": "public_ip_verification_failed",
                            "error": error_msg,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                return

            public_ip_name = nic_client.ip_configurations[0].public_ip_address.id.split('/')[-1]
            public_ip_info = await network_client.public_ip_addresses.get(resource_group, public_ip_name)
            public_ip = public_ip_info.ip_address
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "public_ip_confirmed",
                        "message": f"VM public IP confirmed: {public_ip}"
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
                vm_name=vm_name,
                storage_account_name=storage_account_name
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "details": {
                        "step": "public_ip_verification_error",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # DNS Configuration
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "dns_configuration",
                    "message": f"Configuring DNS for domain {domain}"
                }
            }
        )

        # Create DNS Zone
        try:
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "creating_dns_zone",
                        "message": f"Creating DNS zone for {domain}"
                    }
                }
            )

            try:
                dns_zone = await dns_client.zones.get(resource_group, domain)
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "provisioning",
                        "details": {
                            "step": "dns_zone_exists",
                            "message": f"DNS zone {domain} already exists"
                        }
                    }
                )
            except Exception:
                async_dns_zone = dns_client.zones.create_or_update(
                    resource_group, 
                    domain, 
                    {'location': 'global'}
                )
                dns_zone = await async_dns_zone.result()
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "provisioning",
                        "details": {
                            "step": "dns_zone_created",
                            "message": f"DNS zone {domain} created successfully"
                        }
                    }
                )

            # Wait for DNS Zone to initialize
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "dns_zone_initializing",
                        "message": "Waiting for DNS zone to initialize (5 seconds)"
                    }
                }
            )
            await asyncio.sleep(5)

            # Verify NS delegation
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "verifying_ns_delegation",
                        "message": "Verifying NS delegation for DNS zone"
                    }
                }
            )

            if not check_ns_delegation_with_retries(dns_client, resource_group, domain):
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
                    vm_name=vm_name,
                    storage_account_name=storage_account_name
                )
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "failed",
                        "details": {
                            "step": "ns_delegation_failed",
                            "error": error_msg,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                return

            # Create DNS A records
            record_name = subdomain.rstrip('.') if subdomain else '@' 
            a_records = [record_name]
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "creating_dns_records",
                        "message": f"Creating DNS A records: {a_records}",
                        "records": a_records,
                        "ip_address": public_ip
                    }
                }
            )

            for a_record in a_records:
                try:
                    a_record_set = RecordSet(
                        ttl=3600, 
                        a_records=[{'ipv4_address': public_ip}]
                    )
                    await dns_client.record_sets.create_or_update(
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
                            "details": {
                                "step": "dns_record_created",
                                "message": f"Created DNS A record for {a_record}",
                                "record": a_record,
                                "ip_address": public_ip
                            }
                        }
                    )
                except Exception as e:
                    error_msg = f"Failed to create DNS A record for {a_record}: {str(e)}"
                    print_error(error_msg)
                    await post_status_update(
                        hook_url=hook_url,
                        status_data={
                            "vm_name": vm_name,
                            "status": "failed",
                            "details": {
                                "step": "dns_record_failed",
                                "error": error_msg,
                                "record": a_record
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
                vm_name=vm_name,
                storage_account_name=storage_account_name
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "details": {
                        "step": "dns_configuration_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Install Custom Script Extension
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "installing_extension",
                    "message": "Installing custom script extension"
                }
            }
        )

        try:
            ext_params = {
                'location': location,
                'publisher': 'Microsoft.Azure.Extensions',
                'type': 'CustomScript',
                'type_handler_version': '2.0',
                'settings': {
                    'fileUris': [blob_url_with_sas],
                    'commandToExecute': f'bash {blob_name}',
                },
            }
            async_extension = compute_client.virtual_machine_extensions.begin_create_or_update(
                resource_group,
                vm_name,
                'customScriptExtension',
                ext_params
            )
            extension = await async_extension.result()
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "extension_installed",
                        "message": "Custom script extension installed successfully"
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
                vm_name=vm_name,
                storage_account_name=storage_account_name
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "details": {
                        "step": "extension_installation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Cleanup temporary storage
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "cleaning_up",
                    "message": "Cleaning up temporary resources"
                }
            }
        )

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
                    "details": {
                        "step": "cleanup_complete",
                        "message": "Temporary resources cleaned up successfully"
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
                    "status": "cleanup_failed",
                    "details": {
                        "step": "cleanup_warning",
                        "warning": error_msg
                    }
                }
            )

        # Final wait for system to stabilize
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "finalizing",
                    "message": "Finalizing setup (30 seconds)"
                }
            }
        )
        await asyncio.sleep(30)

        # Send completion email
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "provisioning",
                "details": {
                    "step": "sending_email",
                    "message": "Sending completion notification"
                }
            }
        )

        try:
            smtp_host = os.environ.get('SMTP_HOST')
            smtp_port_str = os.environ.get('SMTP_PORT')
            smtp_user = os.environ.get('SMTP_USER')
            smtp_password = os.environ.get('SMTP_PASS')
            sender_email = os.environ.get('SENDER_EMAIL')
            recipient_emails = [e.strip() for e in RECIPIENT_EMAILS.split(',')]

            smtp_port = int(smtp_port_str) if smtp_port_str else 587
            
            html_content = html_email.HTMLEmail(
                ip_address=public_ip,
                link1="",
                link2="",
                link3=""
            )

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
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "email_sent",
                        "message": "Completion email sent successfully"
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
                    "details": {
                        "step": "email_failed",
                        "warning": error_msg
                    }
                }
            )

        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "completed",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "completed",
                    "message": "VM provisioning completed successfully",
                    "public_ip": public_ip,
                    "url": fqdn,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        print_success("-----------------------------------------------------")
        print_success("Azure Windows VM provisioning completed successfully!")
        print_success("-----------------------------------------------------")
        print_success(f"Access URL: {fqdn}")
        print_success("-----------------------------------------------------")

    except Exception as e:
        print_error(f"Unexpected error in background task: {str(e)}")
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "failed",
                "details": {
                    "step": "unexpected_error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
        raise

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
        'Standard_B2s',
        'Standard_B4ms',
        'Standard_D2s_v3',
        'Standard_D4s_v3',
        'Standard_D8s_v3',
        'Standard_D16s_v3',
        'Standard_DS1_v2',
        'Standard_DS2_v2',
        'Standard_DS3_v2',
        'Standard_DS4_v2',
        'Standard_F2s_v2',
        'Standard_F4s_v2',
        'Standard_F8s_v2',
        'Standard_F16s_v2',
        'Standard_E2s_v3',
        'Standard_E4s_v3',
        'Standard_E8s_v3',
        'Standard_E16s_v3'
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


async def post_status_update(hook_url: str, status_data: dict) -> dict:
    """Proper async version"""
    if not hook_url:
        return {"success": True, "status_url": ""}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                hook_url,
                json=status_data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "status_url": data.get("status_url", ""),
                        "response": data
                    }
                return {
                    "success": False,
                    "error": f"HTTP {response.status}",
                    "status_url": ""
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status_url": ""
        }