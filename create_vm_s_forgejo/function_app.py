import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
import dns.resolver
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import logging
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkSecurityGroup, SecurityRule
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import (
    VirtualMachine, HardwareProfile, StorageProfile,
    OSProfile, NetworkProfile, NetworkInterfaceReference,
    LinuxConfiguration
)   
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import RecordSet
from azure.mgmt.storage import StorageManagementClient
import azure.functions as func
import aiohttp
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

app = func.FunctionApp()

image_reference = {
    'publisher': 'canonical',
    'offer': 'ubuntu-24_04-lts',
    'sku': 'server',
    'version': 'latest',
    'exactVersion': '24.04.202409120'
}

PORTS_TO_OPEN = [22, 80, 443, 8000, 3000, 8889, 8890, 7088, 8088]

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

async def run_azure_operation(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

@app.route(route="create_vm", methods=["POST", "GET"], auth_level=func.AuthLevel.FUNCTION)
async def create_vm(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing create_vm request...')
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Extract parameters with defaults
        username = req_body.get('username') or req.params.get('username') or 'azureuser'
        password = req_body.get('password') or req.params.get('password') or 'azurepassword1234!'
        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        domain = req_body.get('domain') or req.params.get('domain')
        location = req_body.get('location') or req.params.get('location')
        vm_size = req_body.get('vm_size') or req.params.get('vm_size') or 'Standard_D2s_v3'
        OS_DISK_SSD_GB = int(req_body.get('os_disk_ssd_gb') or req.params.get('os_disk_ssd_gb') or 256)
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''
        
        # Validate required parameters
        if not all([vm_name, resource_group, domain, location, RECIPIENT_EMAILS]):
            return func.HttpResponse(
                json.dumps({"error": "Missing required parameters"}),
                status_code=400,
                mimetype="application/json"
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
        
        # Handle subdomain
        subdomain = vm_name.strip().strip('.') if vm_name else None
        fqdn = f"{subdomain}.{domain}" if subdomain else domain
        print_info(f"Full domain to configure: {fqdn}")

        # App constants
        ADMIN_EMAIL = f"admin@{domain}"
        ADMIN_PASSWORD = "MyPass1234!"
        FRONTEND_PORT = 3000
        BACKEND_PORT = 8000
        storage_account_base = vm_name

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
                    username, password, vm_name, resource_group, 
                    domain, subdomain, fqdn, location, vm_size,
                    storage_account_base, OS_DISK_SSD_GB, RECIPIENT_EMAILS, 
                    hook_url, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT
                )
            )

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
    username, password, vm_name, resource_group, 
    domain, subdomain, fqdn, location, vm_size,
    storage_account_base, OS_DISK_SSD_GB, RECIPIENT_EMAILS, 
    hook_url, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT, BACKEND_PORT
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
        
        # Generate and upload setup script
        print_info("Generating installation setup script...")
        sh_script = generate_setup.generate_setup(
            fqdn, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_PORT
        )
        record_name = subdomain.rstrip('.') if subdomain else '@'
        a_records = [record_name]
        
        blob_service_client = BlobServiceClient(account_url=AZURE_STORAGE_URL, credential=credentials)
        container_name = 'vm-startup-scripts'
        blob_name = f"{vm_name}-setup.sh"

        try:
            blob_url_with_sas = await run_azure_operation(
                upload_blob_and_generate_sas,
                blob_service_client, 
                container_name, 
                blob_name, 
                sh_script, 
                2
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
                    "details": {
                        "step": "script_uploaded",
                        "message": "Setup script uploaded successfully"
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
            nic = await run_azure_operation(nsg_operation.result)
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "provisioning",
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
            os_disk = {
                'name': f'{vm_name}-os-disk',
                'managed_disk': {'storage_account_type': 'Standard_LRS'},
                'create_option': 'FromImage',
                'disk_size_gb': OS_DISK_SSD_GB
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
                await cleanup_resources(
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
                    "details": {
                        "step": "public_ip_confirmed",
                        "message": f"VM public IP: {public_ip}"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to verify public IP: {str(e)}"
            print_error(error_msg)
            await cleanup_resources(
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
                zone_operation = dns_client.zones.create_or_update(
                    resource_group, 
                    domain, 
                    {'location': 'global'}
                )
                dns_zone = await run_azure_operation(zone_operation.result)
                await asyncio.sleep(5)  # Wait for DNS zone initialization

            # Verify NS delegation
            if not await run_azure_operation(
                check_ns_delegation_with_retries,
                dns_client,
                resource_group,
                domain
            ):
                error_msg = "Incorrect NS delegation for DNS zone"
                print_error(error_msg)
                await cleanup_resources(
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
                    "details": {
                        "step": "dns_records_created",
                        "message": "DNS records configured successfully"
                    }
                }
            )
        except Exception as e:
            error_msg = f"DNS configuration failed: {str(e)}"
            print_error(error_msg)
            await cleanup_resources(
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
                'publisher': 'Microsoft.Azure.Extensions',
                'type': 'CustomScript',
                'type_handler_version': '2.0',
                'settings': {
                    'fileUris': [blob_url_with_sas],
                    'commandToExecute': f'bash {blob_name}',
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
                    "details": {
                        "step": "extension_installed",
                        "message": "Custom script extension installed"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to install custom script extension: {str(e)}"
            print_error(error_msg)
            await cleanup_resources(
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
            await run_azure_operation(
                cleanup_temp_storage,
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
            smtp_host = os.environ.get('SMTP_HOST')
            smtp_port = int(os.environ.get('SMTP_PORT', 587))
            smtp_user = os.environ.get('SMTP_USER')
            smtp_password = os.environ.get('SMTP_PASS')
            sender_email = os.environ.get('SENDER_EMAIL')
            recipient_emails = [e.strip() for e in RECIPIENT_EMAILS.split(',')]
            
            html_content = html_email.HTMLEmail(
                ip_address=public_ip,
                link1=f"https://{fqdn}",
                link2=f"https://{fqdn}/admin",
                link3=f"https://{fqdn}/status"
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
                    "url": fqdn,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        print_success(f"Azure VM provisioning completed successfully! Access URL: {fqdn}")
        
    except Exception as e:
        # Top-level error handler for background task
        error_msg = f"Unhandled exception in background task: {str(e)}"
        print_error(error_msg)
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "failed",
                "details": {
                    "step": "background_task_failed",
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
        await cleanup_resources(
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

# ====================== HELPER FUNCTIONS ======================

def create_storage_account(storage_client, resource_group_name, storage_name, location):
    """Create or get storage account"""
    print_info(f"Creating storage account '{storage_name}'...")
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
    """Ensure blob container exists"""
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
        print_success(f"Created container '{container_name}'.")
    except Exception:
        print_info(f"Container '{container_name}' already exists.")
    return container_client

def upload_blob_and_generate_sas(blob_service_client, container_name, blob_name, data, sas_expiry_hours=1):
    """Upload blob and generate SAS URL"""
    container_client = ensure_container_exists(blob_service_client, container_name)
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True)
    
    sas_token = generate_blob_sas(
        blob_service_client.account_name,
        container_name,
        blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=sas_expiry_hours),
        account_key=AZURE_STORAGE_ACCOUNT_KEY
    )
    return f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

def get_compatible_vm_sizes():
    """Return list of compatible VM sizes"""
    return [
        'Standard_B2s', 'Standard_B4ms', 'Standard_D2s_v3', 'Standard_D4s_v3',
        'Standard_D8s_v3', 'Standard_D16s_v3', 'Standard_DS1_v2', 'Standard_DS2_v2',
        'Standard_DS3_v2', 'Standard_DS4_v2', 'Standard_F2s_v2', 'Standard_F4s_v2',
        'Standard_F8s_v2', 'Standard_F16s_v2', 'Standard_E2s_v3', 'Standard_E4s_v3',
        'Standard_E8s_v3', 'Standard_E16s_v3'
    ]

def check_vm_size_compatibility(vm_size):
    """Check if VM size is compatible"""
    return vm_size in get_compatible_vm_sizes()

def check_ns_delegation_with_retries(dns_client, resource_group, domain, retries=5, delay=10):
    """Check NS delegation with retries"""
    for attempt in range(1, retries + 1):
        if check_ns_delegation(dns_client, resource_group, domain):
            return True
        print_warn(f"Retrying NS delegation check in {delay} seconds... (Attempt {attempt}/{retries})")
        time.sleep(delay)
    return False

def check_ns_delegation(dns_client, resource_group, domain):
    """Verify correct NS delegation"""
    try:
        dns_zone = dns_client.zones.get(resource_group, domain)
        azure_ns = sorted(ns.lower().rstrip('.') for ns in dns_zone.name_servers)
        
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Google DNS
        answers = resolver.resolve(domain, 'NS')
        public_ns = sorted(str(rdata.target).lower().rstrip('.') for rdata in answers)
        
        return set(azure_ns).issubset(set(public_ns))
    except Exception as e:
        print_error(f"NS delegation check failed: {e}")
        return False

async def cleanup_resources(
    network_client, compute_client, storage_client, blob_service_client, 
    container_name, blob_name, dns_client, resource_group, 
    domain, a_records, vm_name, storage_account_name
):
    """Cleanup all resources on failure"""
    print_warn("Cleaning up Azure resources due to failure...")
    
    # Delete VM and associated resources
    try:
        vm = compute_client.virtual_machines.get(resource_group, vm_name)
        os_disk_name = vm.storage_profile.os_disk.name
        compute_client.virtual_machines.begin_delete(resource_group, vm_name).wait()
        compute_client.disks.begin_delete(resource_group, os_disk_name).wait()
    except Exception:
        pass
    
    # Delete networking resources
    for resource_type, name in [
        (network_client.network_interfaces, f"{vm_name}-nic"),
        (network_client.network_security_groups, f"{vm_name}-nsg"),
        (network_client.public_ip_addresses, f"{vm_name}-public-ip"),
        (network_client.virtual_networks, f"{vm_name}-vnet")
    ]:
        try:
            resource_type.begin_delete(resource_group, name).wait()
        except Exception:
            pass
    
    # Delete storage resources
    try:
        container_client = blob_service_client.get_container_client(container_name)
        container_client.delete_blob(blob_name)
        blob_service_client.delete_container(container_name)
        storage_client.storage_accounts.delete(resource_group, storage_account_name)
    except Exception:
        pass
    
    # Delete DNS records
    for record_name in a_records:
        record_to_delete = record_name if record_name else '@'
        try:
            dns_client.record_sets.delete(resource_group, domain, record_to_delete, 'A')
        except Exception:
            pass
    
    print_success("Cleanup completed.")

async def cleanup_temp_storage(
    resource_group, storage_client, storage_account_name, 
    blob_service_client, container_name, blob_name
):
    """Cleanup temporary storage on success"""
    try:
        container_client = blob_service_client.get_container_client(container_name)
        container_client.delete_blob(blob_name)
        blob_service_client.delete_container(container_name)
        storage_client.storage_accounts.delete(resource_group, storage_account_name)
    except Exception as e:
        print_warn(f"Temp storage cleanup failed: {str(e)}")
        raise

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