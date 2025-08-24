import os
import json
import logging
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.dns import DnsManagementClient
import asyncio
import concurrent.futures
import aiohttp
from datetime import datetime
# Use relative imports to load local modules from the same function folder.
# This ensures Python finds these files (generate_setup.py, html_email.py, html_email_send.py)
# in the current package instead of searching in global site-packages,
# which prevents ModuleNotFoundError in Azure Functions environment.
from . import html_email
from . import html_email_send

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

executor = concurrent.futures.ThreadPoolExecutor()

async def run_blocking(func, *args, **kwargs):
    """
    Helper to run blocking function in thread pool asynchronously.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

# Console colors for logs (copied from create_vm.py)
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



async def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to delete VM and related resources.")

    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        domain = req_body.get('domain') or req.params.get('domain')
        location = req_body.get('location') or req.params.get('location')
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''
        ##
        a_records = req_body.get('a_records') or req.params.get('a_records') or [vm_name, f"drop.{vm_name}", f"pin.{vm_name}", f"web.{vm_name}"]

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
        if not RECIPIENT_EMAILS:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'recipient_emails' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # a_records can be comma separated string or list
        if isinstance(a_records, str):
            a_records_list = [r.strip() for r in a_records.split(",") if r.strip()]
        elif isinstance(a_records, list):
            a_records_list = a_records
        else:
            a_records_list = []

        # Initial status update
        hook_response = await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "deleting",
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

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            err = "AZURE_SUBSCRIPTION_ID environment variable is not set."
            logger.error(err)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "authentication_error",
                        "error": err,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        try:
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
        except KeyError as e:
            err = f"Missing environment variable: {e}"
            logger.error(err)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "authentication_error",
                        "error": err,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        compute_client = ComputeManagementClient(credentials, subscription_id)
        network_client = NetworkManagementClient(credentials, subscription_id)
        dns_client = DnsManagementClient(credentials, subscription_id)

        response_log = []

        # Start background deletion
        asyncio.create_task(
            delete_vm_and_resources(
                compute_client, network_client, dns_client,
                resource_group, location, vm_name, RECIPIENT_EMAILS, domain, a_records_list, 
                response_log, hook_url
            )
        )

        # Return immediately with status URL
        return func.HttpResponse(
            json.dumps({
                "message": "VM deletion started",
                "status_url": status_url,
                "vm_name": vm_name
            }),
            status_code=202,
            mimetype="application/json"
        )

    except Exception as ex:
        logger.exception("Unhandled error:")
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "failed",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "unhandled_error",
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

async def delete_vm_and_resources(compute_client, network_client, dns_client, resource_group, location, vm_name, RECIPIENT_EMAILS, domain, a_records_list, response_log, hook_url):
    # Initial status update
    if hook_url:
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "deleting",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "starting_deletion",
                    "message": "Beginning VM deletion process",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
    
    try:
        # Get VM details
        vm = await run_blocking(compute_client.virtual_machines.get, resource_group, vm_name)
        os_disk_name = None
        if vm.storage_profile and vm.storage_profile.os_disk:
            os_disk_name = vm.storage_profile.os_disk.name
    except Exception as e:
        response_log.append({"warning": f"Failed to get VM '{vm_name}': {str(e)}"})
        os_disk_name = None

    # Define deletion coroutines
    async def delete_vm():
        try:
            await run_blocking(compute_client.virtual_machines.begin_delete(resource_group, vm_name).result)
            response_log.append({"success": f"Deleted VM '{vm_name}'."})
            
            # Status update
            if hook_url:
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "vm_name": vm_name,
                        "status": "deleting",
                        "resource_group": resource_group,
                        "location": location,
                        "details": {
                            "step": "vm_deleted",
                            "message": f"VM {vm_name} deleted successfully",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
        except Exception as e:
            response_log.append({"warning": f"Failed to delete VM '{vm_name}': {str(e)}"})

    async def delete_os_disk():
        if not os_disk_name:
            return
        try:
            await run_blocking(compute_client.disks.begin_delete(resource_group, os_disk_name).result)
            response_log.append({"success": f"Deleted OS disk '{os_disk_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete OS disk '{os_disk_name}': {str(e)}"})

    async def delete_nic():
        nic_name = f"{vm_name}-nic"
        try:
            await run_blocking(network_client.network_interfaces.begin_delete(resource_group, nic_name).result)
            response_log.append({"success": f"Deleted NIC '{nic_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete NIC '{nic_name}': {str(e)}"})

    async def delete_nsg():
        nsg_name = f"{vm_name}-nsg"
        try:
            await run_blocking(network_client.network_security_groups.begin_delete(resource_group, nsg_name).result)
            response_log.append({"success": f"Deleted NSG '{nsg_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete NSG '{nsg_name}': {str(e)}"})

    async def delete_public_ip():
        public_ip_name = f"{vm_name}-public-ip"
        try:
            await run_blocking(network_client.public_ip_addresses.begin_delete(resource_group, public_ip_name).result)
            response_log.append({"success": f"Deleted Public IP '{public_ip_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete Public IP '{public_ip_name}': {str(e)}"})

    async def delete_vnet():
        vnet_name = f"{vm_name}-vnet"
        try:
            await run_blocking(network_client.virtual_networks.begin_delete(resource_group, vnet_name).result)
            response_log.append({"success": f"Deleted VNet '{vnet_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete VNet '{vnet_name}': {str(e)}"})

    async def delete_dns_records():
        for record_name in a_records_list:
            record_to_delete = record_name if record_name else '@'
            try:
                await run_blocking(dns_client.record_sets.delete, resource_group, domain, record_to_delete, 'A')
                response_log.append({"success": f"Deleted DNS A record '{record_to_delete}' in zone '{domain}'."})
                
                # Status update for each DNS record
                if hook_url:
                    await post_status_update(
                        hook_url=hook_url,
                        status_data={
                            "vm_name": vm_name,
                            "status": "deleting",
                            "resource_group": resource_group,
                            "location": location,
                            "details": {
                                "step": "dns_record_deleted",
                                "message": f"DNS record {record_to_delete} deleted",
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        }
                    )
            except Exception as e:
                response_log.append({"warning": f"Failed to delete DNS A record '{record_to_delete}' in zone '{domain}': {str(e)}"})

    # Run deletions
    await delete_vm()
    await delete_os_disk()

    # Run network related deletes concurrently
    await asyncio.gather(
        delete_nic(),
        delete_nsg(),
        delete_public_ip(),
        delete_vnet(),
        delete_dns_records()
    )
    
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
            vm_name,
            datetime.utcnow().isoformat(),
            "Successfully deleted",
            "https://rtxdevstation.xyz/requestvm",
            "https://rtxdevstation.xyz"
        )

        await html_email_send.send_html_email_smtp(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                sender_email=sender_email,
                recipient_emails=recipient_emails,
                subject=f"'{vm_name}' deleted",
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
    if hook_url:
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": vm_name,
                "status": "completed",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "completed",
                    "message": "VM and all related resources deleted successfully",
                    "url": f"https://cdn.sdappnet.cloud/rtx/rtxvmdeleted.html?vm_name={vm_name}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

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
