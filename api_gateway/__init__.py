import sys
import json
import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
import azure.functions as func

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")

##Azure subscription id
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
##Resource group where your api function is
API_RESOURCE_GROUP = os.getenv("API_RESOURCE_GROUP") #group your api is saved
##your api name
API_NAME = os.getenv("API_NAME") #your api name
###this is on azure portal e.g yourapi-00000.uksouth-01.azurewebsites.net
###Or when you add your custom domain myapi.com or myapi.domain.com
API_DEFAULT_DOMAIN = os.getenv("API_DEFAULT_DOMAIN") #your api name
 
def get_function_keys(function_name):
    try:
        # Authenticate
        try:
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_CLIENT_ID'],
                client_secret=os.environ['AZURE_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_TENANT_ID']
            )
        except KeyError as e:
            logger.error(f"Missing environment variable: {e}")
            return None

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            logger.error("AZURE_SUBSCRIPTION_ID environment variable is not set.")
            return None

        client = WebSiteManagementClient(credentials, subscription_id)
        keys = client.web_apps.list_function_keys(
            os.environ.get('API_RESOURCE_GROUP'),
            os.environ.get('API_NAME'),
            function_name
        )
         
        # keys.additional_properties is a dict of key names to values
        function_keys = keys.additional_properties
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

    function_name = req_body.get('function_name') or req.params.get('function_name')
    if not function_name:
        return func.HttpResponse(
            "Please provide a function_name parameter",
            status_code=400
        )

    if not all([SUBSCRIPTION_ID, API_RESOURCE_GROUP, API_NAME, API_DEFAULT_DOMAIN]):
        logger.error("Missing required environment variables")
        return func.HttpResponse(
            "Missing required environment variables",
            status_code=400
        )

    keys = get_function_keys(function_name)
    if not keys:
        return func.HttpResponse(
            f"No keys found for function '{function_name}'",
            status_code=404
        )

    return func.HttpResponse(
        json.dumps(keys),
        mimetype='application/json',
        status_code=200
    )