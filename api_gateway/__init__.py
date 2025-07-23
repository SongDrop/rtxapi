import os
import logging
import azure.functions as func

from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")
FUNCTION_APP_NAME = os.getenv("FUNCTION_APP_NAME")
FUNCTION_NAME = os.getenv("FUNCTION_NAME")

def get_function_default_key():
    try:
        credential = DefaultAzureCredential()
        client = WebSiteManagementClient(credential, SUBSCRIPTION_ID)

        # List function keys
        keys = client.web_apps.list_function_keys(RESOURCE_GROUP, FUNCTION_APP_NAME, FUNCTION_NAME)
        default_key = keys.keys.get("default")
        return default_key
    except Exception as e:
        logger.error(f"Error fetching function key: {e}")
        return None

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to generate full function URL with key")

    # Get the function_name from query parameters, fallback to env var if not provided
    function_name = req.params.get('function_name') or FUNCTION_NAME
    if not function_name:
        return func.HttpResponse(
            "Please provide a function_name query parameter or set FUNCTION_NAME env variable.",
            status_code=400
        )

    try:
        credential = DefaultAzureCredential()
        client = WebSiteManagementClient(credential, SUBSCRIPTION_ID)

        keys = client.web_apps.list_function_keys(RESOURCE_GROUP, FUNCTION_APP_NAME, function_name)
        default_key = keys.keys.get("default")
        if not default_key:
            return func.HttpResponse(f"No default key found for function '{function_name}'", status_code=404)

        base_url = f"https://{FUNCTION_APP_NAME}.azurewebsites.net/api/{function_name}"
        full_url = f"{base_url}?code={default_key}"
        return func.HttpResponse(full_url, status_code=200)

    except Exception as e:
        logger.error(f"Error fetching function key for '{function_name}': {e}")
        return func.HttpResponse("Failed to get function key", status_code=500)