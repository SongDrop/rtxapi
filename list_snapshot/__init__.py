import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to list Azure snapshots.')

    try:
        # Parse inputs - prefer POST JSON body, fallback to query params
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        if not resource_group:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'resource_group' parameter"}),
                status_code=400,
                mimetype="application/json"
            )

        # Authenticate with Azure
        try:
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
        except KeyError as e:
            err = f"Missing environment variable: {e}"
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            err = "AZURE_SUBSCRIPTION_ID environment variable is not set."
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        resource_client = ResourceManagementClient(credentials, subscription_id)
        compute_client = ComputeManagementClient(credentials, subscription_id)

        # Check if resource group exists
        try:
            _ = resource_client.resource_groups.get(resource_group)
        except Exception as e:
            err = f"Resource group '{resource_group}' not found or inaccessible: {e}"
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=404,
                mimetype="application/json"
            )

        # List snapshots in resource group
        try:
            snapshots = compute_client.snapshots.list_by_resource_group(resource_group)
            snapshot_list = []
            total_size_gb = 0
            
            for snapshot in snapshots:
                disk_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                total_size_gb += disk_size_gb
                
                snapshot_list.append({
                    "name": snapshot.name,
                    "location": snapshot.location,
                    "disk_size_gb": disk_size_gb,
                    "sku": snapshot.sku.name if snapshot.sku else "Standard",
                    "provisioning_state": snapshot.provisioning_state,
                    "time_created": snapshot.time_created.isoformat() if snapshot.time_created else "N/A",
                    "os_type": str(snapshot.os_type) if snapshot.os_type else "Unknown",
                    "hyper_v_generation": str(snapshot.hyper_v_generation) if snapshot.hyper_v_generation else "Unknown"
                })
            
            result = {
                "resource_group": resource_group,
                "snapshot_count": len(snapshot_list),
                "total_size_gb": total_size_gb,
                "snapshots": snapshot_list
            }
            
            return func.HttpResponse(
                json.dumps(result),
                status_code=200,
                mimetype="application/json"
            )
            
        except Exception as e:
            err = f"Error retrieving snapshots: {e}"
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

    except Exception as ex:
        logging.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )