import json
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import logging
from azure.mgmt.storage import StorageManagementClient
import azure.functions as func

 
# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")
 
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
    logging.info('Processing hook_vm request...')
 
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        location = req_body.get('location') or req.params.get('location') #uksouth
        status = req_body.get('status') or req.params.get('status')
        details = req_body.get("details", {}) or req.params.get('details', {})
        storage_account_base = vm_name
 
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
        if not location:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'location' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not status:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'status' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        #Checks successful -> continue 
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
 
        # Authenticate with Azure
        try:
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
        except KeyError as e:
            err = f"Missing environment variable: {e}"
            print_error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )
        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            print_error("Set AZURE_SUBSCRIPTION_ID environment variable.")
            return func.HttpResponse(
                json.dumps({"error": f"Set AZURE_SUBSCRIPTION_ID environment variable."}),
                status_code=500,
                mimetype="application/json"
            )

        storage_client = StorageManagementClient(credentials, subscription_id)
 
        # Container storage
        storage_account_name = f"{storage_account_base}provision"
        storage_config = await create_storage_account(storage_client, resource_group, storage_account_name, location)
        global AZURE_STORAGE_ACCOUNT_KEY
        AZURE_STORAGE_ACCOUNT_KEY = storage_config["AZURE_STORAGE_KEY"]
        AZURE_STORAGE_URL = storage_config["AZURE_STORAGE_URL"]
            
        # Autoinstall script generation
        print_info("Generating Bash setup script...")
        # Prepare status data (your JSON structure)
        status_data = {
            "vm_name": vm_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }

        blob_service_client = BlobServiceClient(account_url=AZURE_STORAGE_URL, credential=credentials)
        container_name = 'vm-webhook-json'
        blob_name = f"{vm_name}-webhook.json"

        # Uploading generated script to storage
        blob_url_with_sas = await upload_blob_and_generate_sas(blob_service_client, container_name, blob_name, json.dumps(status_data), sas_expiry_hours=2)

        print_success("-----------------------------------------------------")
        print_success(f"Updated json status to Blob Storage: {blob_url_with_sas}")
        print_success("-----------------------------------------------------")

        if status == "failed" or status == "completed":
            storage_client.storage_accounts.delete(resource_group, storage_account_name)
            print_success(f"Deleted storage account '{storage_account_name}'.")

        result = {
            "message": "Status updated",
            "vm_name": vm_name,
            "status": status,
            "status_url": blob_url_with_sas,
            "expiry_time": (datetime.utcnow() + timedelta(hours=2)).isoformat()
        }
        return func.HttpResponse(
                json.dumps(result),
                status_code=200,
                mimetype="application/json"
            )

    except Exception as ex:
        logging.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )

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
 