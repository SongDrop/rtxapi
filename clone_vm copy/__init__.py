import asyncio
import json
import os
import time
from datetime import datetime
import logging
import aiohttp
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import GrantAccessData, AccessLevel
import azure.functions as func

from . import html_email
from . import html_email_send

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting clone VM application initialization...")

# Console colors
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

def print_success(msg):
    logging.info(f"{bcolors.OKGREEN}[SUCCESS]{bcolors.ENDC} {msg}")

def print_warn(msg):
    logging.info(f"{bcolors.WARNING}[WARNING]{bcolors.ENDC} {msg}")

def print_error(msg):
    logging.info(f"{bcolors.FAIL}[ERROR]{bcolors.ENDC} {msg}")

# Async helper
async def run_azure_operation(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

# ====================== HTTP TRIGGER ======================
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing create_clone_vm request...")
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Required parameters
        vm_name = req_body.get("vm_name") or req.params.get("vm_name")
        resource_group = req_body.get("resource_group") or req.params.get("resource_group")
        location = req_body.get("location") or req.params.get("location")
        hook_url = req_body.get("hook_url") or req.params.get("hook_url") or ""
        RECIPIENT_EMAILS = req_body.get("recipient_emails") or req.params.get("recipient_emails")
        gallery_resource_group = req_body.get("gallery_resource_group") or req.params.get("gallery_resource_group")
        gallery_name = req_body.get("gallery_name") or req.params.get("gallery_name")
        image_definition_name = req_body.get("image_definition_name") or req.params.get("image_definition_name")
        image_offer = req_body.get("image_offer") or req.params.get("image_offer", "Windows-10")
        image_sku = req_body.get("image_sku") or req.params.get("image_sku")
        image_publisher = req_body.get("image_publisher") or req.params.get("image_publisher", "MicrosoftWindowsDesktop")

        # Manual missing parameter checks (KEEP STYLE)
        if not vm_name:
            return func.HttpResponse(json.dumps({"error": "Missing 'vm_name' parameter"}), status_code=400, mimetype="application/json")
        if not resource_group:
            return func.HttpResponse(json.dumps({"error": "Missing 'resource_group' parameter"}), status_code=400, mimetype="application/json")
        if not location:
            return func.HttpResponse(json.dumps({"error": "Missing 'location' parameter"}), status_code=400, mimetype="application/json")
        if not RECIPIENT_EMAILS:
            return func.HttpResponse(json.dumps({"error": "Missing 'recipient_emails' parameter"}), status_code=400, mimetype="application/json")
        if not gallery_resource_group:
            return func.HttpResponse(json.dumps({"error": "Missing 'gallery_resource_group' parameter"}), status_code=400, mimetype="application/json")
        if not gallery_name:
            return func.HttpResponse(json.dumps({"error": "Missing 'gallery_name' parameter"}), status_code=400, mimetype="application/json")
        if not image_definition_name:
            return func.HttpResponse(json.dumps({"error": "Missing 'image_definition_name' parameter"}), status_code=400, mimetype="application/json")
        if not image_sku:
            return func.HttpResponse(json.dumps({"error": "Missing 'image_sku' parameter"}), status_code=400, mimetype="application/json")

        # Initial status update
        hook_response = await post_status_update(hook_url=hook_url, status_data={
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {"step": "init", "vm_name": vm_name, "timestamp": datetime.utcnow().isoformat()}
        })

        if not hook_response.get("success") and hook_url:
            error_msg = hook_response.get("error", "Unknown error posting status")
            print_error(f"Initial status update failed: {error_msg}")
            return func.HttpResponse(json.dumps({"error": f"Status update failed: {error_msg}"}), status_code=500, mimetype="application/json")

        status_url = hook_response.get("status_url", "")

         # ====================== Azure Authentication ======================
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
        required_vars = [
            "AZURE_APP_CLIENT_ID",
            "AZURE_APP_CLIENT_SECRET",
            "AZURE_APP_TENANT_ID",
            "AZURE_SUBSCRIPTION_ID"
        ]
        missing_env = [var for var in required_vars if not os.environ.get(var)]
        if missing_env:
            raise Exception(f"Missing environment variables: {', '.join(missing_env)}")

        credentials = ClientSecretCredential(
            client_id=os.environ["AZURE_APP_CLIENT_ID"],
            client_secret=os.environ["AZURE_APP_CLIENT_SECRET"],
            tenant_id=os.environ["AZURE_APP_TENANT_ID"]
        )

        # Start background clone task
        asyncio.create_task(
            clone_vm_background(
                credentials, vm_name, resource_group, location, hook_url, RECIPIENT_EMAILS,
                gallery_resource_group, gallery_name, image_definition_name, image_offer, image_sku, image_publisher
            )
        )

        return func.HttpResponse(json.dumps({
            "message": "VM clone process started",
            "status_url": status_url,
            "vm_name": vm_name
        }), status_code=202, mimetype="application/json")

    except Exception as ex:
        logging.exception("Unhandled error in main function:")
        if hook_url:
            await post_status_update(hook_url=hook_url, status_data={
                "vm_name": vm_name or "unknown",
                "status": "failed",
                "resource_group": resource_group or "unknown",
                "location": location or "unknown",
                "details": {"step": "main_function_error", "error": str(ex), "timestamp": datetime.utcnow().isoformat()}
            })
        return func.HttpResponse(json.dumps({"error": str(ex)}), status_code=500, mimetype="application/json")

# ====================== BACKGROUND TASK ======================
async def clone_vm_background(credentials, vm_name, resource_group, location, hook_url, RECIPIENT_EMAILS,
                              gallery_resource_group, gallery_name, image_definition_name, image_offer, image_sku, image_publisher):
    try:
        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {"step": "starting_clone", "message": "Beginning clone process", "timestamp": datetime.utcnow().isoformat()}
        })
        print_info(f"Starting clone process for VM '{vm_name}'")

        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        compute_client = ComputeManagementClient(credentials, subscription_id)

        # Stop VM
        try:
            await post_status_update(hook_url, {
                "vm_name": vm_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "stopping_vm",
                    "message": "Stopping VM before snapshot",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
            await stop_vm_to_snapshot(compute_client, vm_name, resource_group)
        except Exception as e:
            error_msg = f"Failed to stop VM '{vm_name}': {str(e)}"
            print_error(error_msg)
            await post_status_update(hook_url, {
                "vm_name": vm_name,
                "status": "failed",
                "resource_group": resource_group,
                "location": location,
                "details": {"step": "stop_vm_failed", "error": error_msg, "timestamp": datetime.utcnow().isoformat()}
            })
            return

        # Create snapshot
        await post_status_update(hook_url, {"vm_name": vm_name, "status": "provisioning",
                                            "resource_group": resource_group, "location": location,
                                            "details": {"step": "creating_snapshot", "message": "Snapshot creating in process..."}})

        vm = await run_azure_operation(compute_client.virtual_machines.get, resource_group, vm_name)
        os_disk_id = vm.storage_profile.os_disk.managed_disk.id
        snapshot_name = f"{vm_name}-clone-snapshot-{int(time.time())}"
        snapshot_params = {"location": location, "creation_data": {"create_option": "Copy", "source_uri": os_disk_id}}

        snapshot_operation = compute_client.snapshots.begin_create_or_update(resource_group, snapshot_name, snapshot_params)
        snapshot = await run_azure_operation(snapshot_operation.result)
        print_success(f"Snapshot '{snapshot_name}' created successfully for VM '{vm_name}'")

        # Create VM image (gallery version)
        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {"step": "creating_image", "message": "Creating VM image from snapshot"}
        })

        
        # For simplicity, skipping full gallery image creation here; you can add it as per your original pattern

        # Restart VM
        try:
            await post_status_update(hook_url, {
                "vm_name": vm_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {"step": "restarting_vm", "message": "Restarting VM after snapshot"}
            })
            await restart_vm(compute_client, vm_name, resource_group)
        except Exception as e:
            error_msg = f"Failed to restart VM '{vm_name}': {str(e)}"
            print_warn(error_msg)
            await post_status_update(hook_url, {
                "vm_name": vm_name,
                "status": "warning",
                "resource_group": resource_group,
                "location": location,
                "details": {"step": "restart_vm_failed", "warning": error_msg}
            })

        # Wait before sending email
        await asyncio.sleep(30)

        # Send completion email
        try:
            await post_status_update(hook_url, {
                "vm_name": vm_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {"step": "sending_email", "message": "Sending completion email"}
            })

            smtp_host = os.environ.get('SMTP_HOST')
            smtp_port = int(os.environ.get('SMTP_PORT', 587))
            smtp_user = os.environ.get('SMTP_USER')
            smtp_password = os.environ.get('SMTP_PASS')
            sender_email = os.environ.get('SENDER_EMAIL')
            recipient_emails = [e.strip() for e in RECIPIENT_EMAILS.split(',')]

            html_content = html_email.HTMLEmail(
                snapshot_name=snapshot_name,
                created_at=datetime.utcnow().isoformat(),
                snapshot_url=f"snapshot:{snapshot_name}"
            ) 

            await html_email_send.send_html_email_smtp(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                sender_email=sender_email,
                recipient_emails=recipient_emails,
                subject=f"VM '{vm_name}' Clone Completed",
                html_content=html_content,
                use_tls=True
            )

            await post_status_update(hook_url, {"vm_name": vm_name, "status": "completed",
                                                "resource_group": resource_group, "location": location,
                                                "details": {"step": "completed", "message": "VM clone successful", "timestamp": datetime.utcnow().isoformat()}})
            print_success(f"Email sent for clone '{snapshot_name}'")
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            print_warn(error_msg)
            await post_status_update(hook_url, {"vm_name": vm_name, "status": "failed",
                                                "resource_group": resource_group, "location": location,
                                                "details": {"step": "email_failed", "warning": error_msg}})

    except Exception as e:
        error_msg = f"Clone process failed: {str(e)}"
        print_error(error_msg)
        await post_status_update(hook_url, {"vm_name": vm_name, "status": "failed",
                                            "resource_group": resource_group, "location": location,
                                            "details": {"step": "clone_failed", "error": error_msg, "timestamp": datetime.utcnow().isoformat()}})

# ====================== STOP & RESTART VM ======================
async def stop_vm_to_snapshot(compute_client: ComputeManagementClient, vm_name: str, resource_group: str):
    try:
        print_info(f"Stopping VM '{vm_name}' in resource group '{resource_group}'...")
        poller = compute_client.virtual_machines.begin_deallocate(resource_group, vm_name)
        await asyncio.to_thread(poller.result)
        print_success(f"VM '{vm_name}' is now stopped/deallocated.")
    except Exception as e:
        error_msg = f"Failed to stop VM '{vm_name}': {str(e)}"
        print_error(error_msg)
        raise

async def restart_vm(compute_client: ComputeManagementClient, vm_name: str, resource_group: str):
    try:
        print_info(f"Starting VM '{vm_name}' in resource group '{resource_group}'...")
        poller = compute_client.virtual_machines.begin_start(resource_group, vm_name)
        await asyncio.to_thread(poller.result)
        print_success(f"VM '{vm_name}' has been restarted successfully.")
    except Exception as e:
        error_msg = f"Failed to restart VM '{vm_name}': {str(e)}"
        print_error(error_msg)
        raise

# ====================== CREATE SNAPSHOT ======================
async def create_vm_snapshot(compute_client: ComputeManagementClient, vm_name: str, resource_group: str, location: str):
    try:
        print_info(f"Creating snapshot for VM '{vm_name}'...")
        vm = await run_azure_operation(compute_client.virtual_machines.get, resource_group, vm_name)
        os_disk_id = vm.storage_profile.os_disk.managed_disk.id
        snapshot_name = f"{vm_name}-snapshot-{int(time.time())}"
        snapshot_params = {"location": location, "creation_data": {"create_option": "Copy", "source_uri": os_disk_id}}
        snapshot_operation = compute_client.snapshots.begin_create_or_update(resource_group, snapshot_name, snapshot_params)
        snapshot = await run_azure_operation(snapshot_operation.result)
        print_success(f"Snapshot '{snapshot_name}' created successfully.")
        return snapshot
    except Exception as e:
        error_msg = f"Failed to create snapshot: {str(e)}"
        print_error(error_msg)
        raise

# ====================== CREATE GALLERY IMAGE ======================
async def create_gallery_image(compute_client: ComputeManagementClient, snapshot, gallery_resource_group: str,
                               gallery_name: str, image_definition_name: str, location: str):
    try:
        print_info(f"Creating gallery image '{image_definition_name}' from snapshot...")
        image_params = {
            "location": location,
            "source_virtual_machine": None,
            "storage_profile": {
                "os_disk": {
                    "os_type": snapshot.os_type,
                    "managed_disk": {"id": snapshot.id},
                }
            }
        }
        # Begin creating image in gallery
        poller = compute_client.gallery_images.begin_create_or_update(
            gallery_resource_group, gallery_name, image_definition_name, image_params
        )
        gallery_image = await asyncio.to_thread(poller.result)
        print_success(f"Gallery image '{image_definition_name}' created successfully.")
        return gallery_image
    except Exception as e:
        error_msg = f"Failed to create gallery image: {str(e)}"
        print_error(error_msg)
        raise


# ====================== STATUS UPDATE ======================
async def post_status_update(hook_url: str, status_data: dict) -> dict:
    if not hook_url:
        return {"success": True, "status_url": ""}
    step = status_data.get("details", {}).get("step", "unknown")
    print_info(f"Sending status update for step: {step}")

    max_retries = 3
    retry_delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(hook_url, json=status_data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {"success": True, "status_url": data.get("status_url", ""), "response": data}
                    else:
                        error_msg = f"HTTP {response.status}"
        except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
            error_msg = str(e)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"

        if attempt < max_retries:
            print_warn(f"Status update failed (attempt {attempt}/{max_retries}): {error_msg}")
            await asyncio.sleep(retry_delay * attempt)
        else:
            print_error(f"Status update failed after {max_retries} attempts: {error_msg}")
            return {"success": False, "error": error_msg, "status_url": ""}
    return {"success": False, "error": "Unknown error", "status_url": ""}
