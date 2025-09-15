import os
import json
import logging
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
import asyncio
import concurrent.futures
import aiohttp
from datetime import datetime

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


async def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to delete snapshots.")

    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''
        location = req_body.get('location') or req.params.get('location', 'global')

        if not resource_group:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'resource_group' parameter"}),
                status_code=400,
                mimetype="application/json"
            )

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            err = "AZURE_SUBSCRIPTION_ID environment variable is not set."
            logger.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        # Initial status update
        hook_response = await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": None,
                "status": "deleting",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "init",
                    "message": "Starting snapshot deletion",
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
                    "vm_name": None,
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
        response_log = []

        # Start background deletion
        asyncio.create_task(
            delete_snapshots(
                compute_client,
                resource_group,
                location,
                response_log,
                hook_url
            )
        )

        # Return immediately with status URL
        return func.HttpResponse(
            json.dumps({
                "message": "Snapshot deletion started",
                "status_url": status_url,
                "resource_group": resource_group
            }),
            status_code=202,
            mimetype="application/json"
        )

    except Exception as ex:
        logger.exception("Unhandled error:")
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": None,
                "status": "failed",
                "resource_group": resource_group if 'resource_group' in locals() else "unknown",
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

async def delete_snapshots(compute_client, resource_group, location, response_log, hook_url):
    # Initial status update
    if hook_url:
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": None,
                "status": "deleting",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "starting_deletion",
                    "message": "Beginning snapshot deletion process",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
    
    try:
        # List snapshots
        print_info(f"Listing snapshots in resource group '{resource_group}'")
        snapshots_list = []
        snapshots_gen = compute_client.snapshots.list_by_resource_group(resource_group)
        for snapshot in snapshots_gen:
            snapshots_list.append(snapshot)
        
        print_info(f"Found {len(snapshots_list)} snapshots in '{resource_group}'")
        
        if hook_url:
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": None,
                    "status": "deleting",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "snapshots_listed",
                        "message": f"Found {len(snapshots_list)} snapshots to delete",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
        
        deleted_snapshots = []
        
        for snapshot in snapshots_list:
            snapshot_name = snapshot.name
            print_info(f"Processing snapshot: {snapshot_name}")

            # Cancel any active SAS/export
            try:
                # Check if grant_access operation is available and needed
                print_info(f"Skipping SAS cancellation for {snapshot_name} - proceeding with deletion")
            except Exception as e:
                print_warn(f"No active export or failed to cancel for {snapshot_name}: {e}")

            # Delete snapshot
            try:
                # Use async wrapper for the blocking operation
                delete_operation = await run_blocking(
                    compute_client.snapshots.begin_delete,
                    resource_group_name=resource_group,
                    snapshot_name=snapshot_name
                )
                
                # Wait for completion
                await run_blocking(delete_operation.result)
                
                deleted_snapshots.append(snapshot_name)
                print_info(f"Deleted snapshot: {snapshot_name}")

                # Update webhook
                if hook_url:
                    await post_status_update(
                        hook_url=hook_url,
                        status_data={
                            "vm_name": None,
                            "status": "deleting",
                            "resource_group": resource_group,
                            "location": location,
                            "details": {
                                "step": "snapshot_deleted",
                                "snapshot_name": snapshot_name,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        }
                    )

            except Exception as e:
                error_msg = f"Failed to delete snapshot {snapshot_name}: {e}"
                print_error(error_msg)
                response_log.append({"warning": error_msg})

        # Final success update
        if hook_url:
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": None,
                    "status": "completed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "completed",
                        "message": f"Deleted {len(deleted_snapshots)} of {len(snapshots_list)} snapshots",
                        "deleted_snapshots": deleted_snapshots,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
        print_success(f"Completed snapshot deletion for resource group '{resource_group}'")
        
    except Exception as e:
        error_msg = f"Error in snapshot deletion process: {str(e)}"
        print_error(error_msg)
        
        if hook_url:
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "vm_name": None,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "process_error",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )


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
