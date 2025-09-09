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
from azure.mgmt.compute.models import GrantAccessData, AccessLevel
import logging
from azure.mgmt.compute import ComputeManagementClient
import azure.functions as func
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

from . import html_email
from . import html_email_send

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting snapshot application initialization...")

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
    logging.info('Processing snapshot request...')    
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        location = req_body.get('location') or req.params.get('location')
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')

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
        if not location:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'location' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not RECIPIENT_EMAILS:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'recipient_emails' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        # ====================== Initial Status Update ======================
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

        # ====================== Start Background Snapshot Task ======================
        asyncio.create_task(
            snapshot_vm_background(credentials, vm_name, resource_group, location, hook_url, RECIPIENT_EMAILS)
        )

        # ✅ Background task started
        return func.HttpResponse(
            json.dumps({
                "message": "VM snapshot process started",
                "status_url": status_url,
                "vm_name": vm_name
            }),
            status_code=202,
            mimetype="application/json"
        )

    except Exception as ex:
        logging.exception("Unhandled error in main function:")
        if hook_url:
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": vm_name or "unknown",
                    "status": "failed",
                    "resource_group": resource_group or "unknown",
                    "location": location or "unknown",
                    "details": {
                        "step": "main_function_error",
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


# ====================== BACKGROUND TASK ======================
async def snapshot_vm_background(credentials, vm_name, resource_group, location, hook_url, RECIPIENT_EMAILS):
    try:
        # Initial status update
        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {
                "step": "starting_snapshot",
                "message": "Beginning snapshot process",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        print_info(f"Starting snapshot process for VM '{vm_name}'")

       
        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        # Initialize Azure clients
        compute_client = ComputeManagementClient(credentials, subscription_id)

        # Stop VM before snapshot
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
            return  # stop processing if VM cannot be stopped

        # Creating snapshot 
        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {"step": "creating_snapshot", "message": "Snapshot creating in process..."}
        })

        # Get VM details
        vm = await run_azure_operation(compute_client.virtual_machines.get, resource_group, vm_name)
        os_disk_id = vm.storage_profile.os_disk.managed_disk.id
        snapshot_name = f"{vm_name}-snapshot-{int(time.time())}"
        snapshot_params = {
            "location": location,
            "creation_data": {"create_option": "Copy", "source_uri": os_disk_id}
        }

        # Create snapshot
        snapshot_operation = compute_client.snapshots.begin_create_or_update(
            resource_group, snapshot_name, snapshot_params
        )
        snapshot = await run_azure_operation(snapshot_operation.result)
        print_success(f"Snapshot '{snapshot_name}' created successfully for VM '{vm_name}'")

        # Notify snapshot creation
        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {
                "step": "snapshot_created",
                "message": f"Snapshot '{snapshot_name}' created successfully",
                "snapshot_id": snapshot.id,
                "timestamp": datetime.utcnow().isoformat()
            }
        })

        # Generate SAS URL
        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {"step": "generating_sas", "message": "Generating SAS URL for snapshot"}
        })

        # grant_access_params = GrantAccessData(access=AccessLevel.read, duration_in_seconds=36000)
        # snapshot_access = await asyncio.to_thread(
        #     lambda: compute_client.snapshots.begin_grant_access(resource_group, snapshot_name, grant_access_params).result()
        # )
        # snapshot_sas_url = snapshot_access.access_sas
        # print_info(f"SAS URL generated: {snapshot_sas_url}")

        # Async-safe call to begin_grant_access
        snapshot_access = await asyncio.to_thread(
            lambda: compute_client.snapshots.begin_grant_access(
                resource_group_name=resource_group,
                snapshot_name=snapshot_name,
                grant_access_data={
                    "access": "Read",             # Access type
                    "durationInSeconds": 36000,     # SAS expiry in seconds
                    "fileFormat": "VHD"          # Optional: VHD or VHDX
                }
            ).result()
        )

        # accessSAS is the property containing the SAS URL
        snapshot_sas_url = snapshot_access.accessSAS
        print(f"SAS URL generated: {snapshot_sas_url}")
    

        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "provisioning",
            "resource_group": resource_group,
            "location": location,
            "details": {
                "step": "sas_generated",
                "message": "SAS URL generated successfully",
                "snapshot_url": snapshot_sas_url
            }
        })

        # Restart VM after snapshot
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

        # Wait a moment before sending email
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
                snapshot_url=snapshot_sas_url
            )

            await html_email_send.send_html_email_smtp(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                sender_email=sender_email,
                recipient_emails=recipient_emails,
                subject=f"VM '{vm_name}' Snapshot Exported",
                html_content=html_content,
                use_tls=True
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
                        "url": f"https://cdn.sdappnet.cloud/rtx/snapshot.html?snapshot_name={snapshot_name}&created_at={datetime.utcnow().isoformat()}&snapshot_url={snapshot_sas_url}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            print_success(f"Email sent for snapshot '{snapshot_name}'")

        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            print_warn(error_msg)
            await post_status_update(hook_url, {
                "vm_name": vm_name,
                "status": "failed",
                "resource_group": resource_group,
                "location": location,
                "details": {"step": "email_failed", "warning": error_msg}
            })

    except Exception as e:
        error_msg = f"Snapshot process failed: {str(e)}"
        print_error(error_msg)
        await post_status_update(hook_url, {
            "vm_name": vm_name,
            "status": "failed",
            "resource_group": resource_group,
            "location": location,
            "details": {"step": "snapshot_failed", "error": error_msg, "timestamp": datetime.utcnow().isoformat()}
        })


# ====================== STOP & RESTART VM ======================
async def stop_vm_to_snapshot(compute_client: ComputeManagementClient, vm_name: str, resource_group: str):
    try:
        print(f"Stopping VM '{vm_name}' in resource group '{resource_group}'...")
        #stop only, if it's deallocated it will get a new IP address.
        poller = compute_client.virtual_machines.begin_power_off(resource_group, vm_name, skip_shutdown=False)
        #poller = compute_client.virtual_machines.begin_deallocate(resource_group, vm_name)
        await asyncio.to_thread(poller.result)
        print(f"VM '{vm_name}' is now stopped/deallocated.")
    except Exception as e:
        error_msg = f"Failed to stop VM '{vm_name}': {str(e)}"
        print_error(error_msg)
        raise

async def restart_vm(compute_client: ComputeManagementClient, vm_name: str, resource_group: str):
    try:
        print(f"Starting VM '{vm_name}' in resource group '{resource_group}'...")
        poller = compute_client.virtual_machines.begin_start(resource_group, vm_name)
        await asyncio.to_thread(poller.result)
        print(f"VM '{vm_name}' has been restarted successfully.")
    except Exception as e:
        error_msg = f"Failed to restart VM '{vm_name}': {str(e)}"
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