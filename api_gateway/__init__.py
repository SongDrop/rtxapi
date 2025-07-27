import sys
import json
import os
import logging
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from azure.identity import ClientSecretCredential
from azure.mgmt.web import WebSiteManagementClient
import azure.functions as func

#https://medium.com/@ssbmqtjt/how-to-connect-an-azure-function-with-an-azure-key-vault-azure-portal-and-python-bd5140178a7

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")

# Environment variables
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
##
API_RESOURCE_GROUP = os.getenv("API_RESOURCE_GROUP")
API_NAME = os.getenv("API_NAME")
API_DEFAULT_DOMAIN = os.getenv("API_DEFAULT_DOMAIN")
###
AZURE_APP_CLIENT_ID = os.getenv("AZURE_APP_CLIENT_ID")
AZURE_APP_CLIENT_SECRET = os.getenv("AZURE_APP_CLIENT_SECRET")

def get_function_keys(function_name):
    try:
        credentials = ClientSecretCredential(
            client_id=AZURE_APP_CLIENT_ID,
            client_secret=AZURE_APP_CLIENT_SECRET,
            tenant_id=AZURE_TENANT_ID
        )
        client = WebSiteManagementClient(credentials, SUBSCRIPTION_ID)

        keys = client.web_apps.list_function_keys(
            API_RESOURCE_GROUP,
            API_NAME,
            function_name
        )


        # keys is a dict-like object, get keys as dict
        if keys and hasattr(keys, 'additional_properties'):
            function_keys = keys.additional_properties
        elif keys:
            # fallback if keys is already a dict-like object
            function_keys = dict(keys)
        return function_keys

    except Exception as e:
        logger.error(f"Exception fetching keys for function '{function_name}': {e}", exc_info=True)
        return None

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to retrieve function keys")

    try:
        req_body = req.get_json()
    except ValueError:
        req_body = {}

    # Accept function_name from query params or JSON body
    function_name = req_body.get('function_name') or req.params.get('function_name')
    if not function_name:
        return func.HttpResponse(
            "Please provide a function_name parameter",
            status_code=400
        )

    # Check environment variables upfront
    missing_vars = []
    for var in ["AZURE_SUBSCRIPTION_ID", "API_RESOURCE_GROUP", "API_NAME", "AZURE_APP_CLIENT_ID", "AZURE_APP_CLIENT_SECRET", "AZURE_TENANT_ID"]:
        if not os.getenv(var):
            missing_vars.append(var)
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return func.HttpResponse(
            f"Missing required environment variables: {', '.join(missing_vars)}",
            status_code=400
        )

    keys = get_function_keys(function_name)
    if not keys:
        return func.HttpResponse(
            f"No keys found for function '{function_name}' or error occurred.",
            status_code=404
        )

    return func.HttpResponse(
        json.dumps(keys),
        mimetype='application/json',
        status_code=200
    )
