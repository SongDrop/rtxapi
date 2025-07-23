import sys
import json
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.storage.blob import generate_container_sas, ContainerSasPermissions
import azure.functions as func

load_dotenv()  # Load environment variables from .env file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Processing SAS token generation request...')

    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Get parameters from JSON body or query parameters
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        storage_account_name = req_body.get('storage_account_name') or req.params.get('storage_account_name')
        container_name = req_body.get('container_name') or req.params.get('container_name')
        # Parse expiry hours from request (string or int), default 24
        expiry_hours_raw = req_body.get('sas_expiry_hours') or req.params.get('sas_expiry_hours') or '1'
        try:
            expiry_hours = int(expiry_hours_raw)
            if expiry_hours <= 0:
                expiry_hours = 1
        except Exception:
            expiry_hours = 1

        # Then generate the SAS token expiry like this:
        expiry_time = datetime.utcnow() + timedelta(hours=expiry_hours)

        # Validate required parameters
        if not resource_group:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'resource_group' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not storage_account_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'storage_account_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not container_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'container_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )

        # Authenticate using ClientSecretCredential
        try:
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
        except KeyError as e:
            err = f"Missing environment variable: {e}"
            logger.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
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

        # Create clients
        resource_client = ResourceManagementClient(credentials, subscription_id)
        storage_client = StorageManagementClient(credentials, subscription_id)

        # Check if resource group exists
        try:
            _ = resource_client.resource_groups.get(resource_group)
            logger.info(f"Resource group '{resource_group}' found.")
        except Exception as e:
            err = f"Resource group '{resource_group}' not found or inaccessible: {e}"
            logger.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=404,
                mimetype="application/json"
            )

        # Get storage account keys
        try:
            keys = storage_client.storage_accounts.list_keys(resource_group, storage_account_name)
            storage_keys = {v.key_name: v.value for v in keys.keys}
            storage_key = storage_keys.get('key1') or list(storage_keys.values())[0]
            logger.info(f"Retrieved storage account key for '{storage_account_name}'.")
        except Exception as e:
            err = f"Failed to get storage account keys: {e}"
            logger.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        # Generate SAS token for container with read, write, create, list permissions, valid for 1 day
        try:
            sas_token = generate_container_sas(
                account_name=storage_account_name,
                container_name=container_name,
                account_key=storage_key,
                permission=ContainerSasPermissions(read=True, write=True, create=True, list=True),
                expiry=expiry_time
            )
            full_url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}?{sas_token}"
            logger.info(f"SAS token generated for container '{container_name}'.")
        except Exception as e:
            err = f"Failed to generate SAS token: {e}"
            logger.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        # Return SAS URL as JSON
        return func.HttpResponse(
            json.dumps({
                "sas_token": sas_token,
                "container_sas_url": full_url
            }),
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