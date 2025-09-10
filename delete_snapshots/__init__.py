import os
import json
import logging
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
import asyncio
import concurrent.futures
from datetime import datetime
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

executor = concurrent.futures.ThreadPoolExecutor()


async def run_blocking(func, *args, **kwargs):
    """
    Run a blocking function in a thread pool asynchronously.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))


def print_info(msg):
    logger.info(f"[INFO] {msg}")


def print_warn(msg):
    logger.warning(f"[WARN] {msg}")


def print_error(msg):
    logger.error(f"[ERROR] {msg}")


async def post_status_update(hook_url: str, status_data: dict) -> dict:
    """
    Send status update to a webhook with retries.
    Always returns JSON with `success` and `status_url` fields.
    """
    if not hook_url:
        return {"success": True, "status_url": ""}
    
    step = status_data.get("details", {}).get("step", "unknown")
    print_info(f"Sending status update for step: {step}")

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



async def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to delete snapshots.")

    try:
        # --- Parse input ---
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        hook_url = req_body.get('hook_url') or req.params.get('hook_url', '')
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

        # --- Authenticate ---
        credentials = ClientSecretCredential(
            client_id=os.environ['AZURE_APP_CLIENT_ID'],
            client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
            tenant_id=os.environ['AZURE_APP_TENANT_ID']
        )
        compute_client = ComputeManagementClient(credentials, subscription_id)

        # --- Initial webhook status ---
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "vm_name": None,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "init",
                    "message": "Starting snapshot deletion",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        # --- List snapshots ---
        logger.info(f"[INFO] Listing snapshots in resource group '{resource_group}'")
        snapshots_gen = await run_blocking(compute_client.snapshots.list_by_resource_group, resource_group)
        snapshots = list(snapshots_gen)
        logger.info(f"[INFO] Found {len(snapshots)} snapshots in '{resource_group}'")

        deleted_snapshots = []

        for snapshot in snapshots:
            snapshot_name = snapshot.name
            logger.info(f"[INFO] Processing snapshot: {snapshot_name}")

            # --- Cancel any active SAS/export ---
            try:
                await run_blocking(
                    compute_client.snapshots.begin_grant_access,
                    resource_group_name=resource_group,
                    snapshot_name=snapshot_name,
                    grant_access_data={"access": "None", "durationInSeconds": 0}
                ).result()
                logger.info(f"[INFO] Cancelled export/SAS for snapshot {snapshot_name}")
            except Exception as e:
                logger.warning(f"[WARN] No active export or failed to cancel for {snapshot_name}: {e}")

            # --- Delete snapshot ---
            try:
                await run_blocking(
                    compute_client.snapshots.begin_delete,
                    resource_group_name=resource_group,
                    snapshot_name=snapshot_name
                ).wait()
                deleted_snapshots.append(snapshot_name)
                logger.info(f"[INFO] Deleted snapshot: {snapshot_name}")

                # --- Update webhook ---
                if hook_url:
                    await post_status_update(
                        hook_url=hook_url,
                        status_data={
                            "vm_name": None,
                            "status": "provisioning",
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
                logger.warning(f"[WARN] Failed to delete snapshot {snapshot_name}: {e}")

        # --- Final result ---
        result = {
            "resource_group": resource_group,
            "deleted_snapshots": deleted_snapshots,
            "deleted_count": len(deleted_snapshots)
        }

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as ex:
        logger.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )