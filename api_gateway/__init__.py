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
RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")
##your api name
API_FUNCTION_APP_NAME = os.getenv("API_FUNCTION_APP_NAME")

def get_function_default_key(function_name, key_to_return:str = "default"):
    try:
        credential = DefaultAzureCredential()
        client = WebSiteManagementClient(credential, SUBSCRIPTION_ID)

        # List function keys
        keys = client.web_apps.list_function_keys(RESOURCE_GROUP, API_FUNCTION_APP_NAME, function_name)
        default_key = keys.keys.get(key_to_return)
        return default_key
    except Exception as e:
        logger.error(f"Error fetching function key: {e}")
        return None

#This function acts as a api-gateway
#https://myapi-2kso12.uksouth-01.azurewebsites.net/api_gateway?code=5e99A6wYRJZf2m_VloSCNlaVFGq00arDjI16MgdAhAQYAzFuEMjEIQ==&function_name={the_other_function}
#you call this function with the other function name such as 'create_vm' in request and it will return back
#https://myapi-2kso12.uksouth-01.azurewebsites.net/create_vm?code={default_sas_token}
#here we are essentially giving back the correct api function link with the SAS token added

#this approach also allow to do extra authentication for the proxy
##https://myapi-2kso12.uksouth-01.azurewebsites.net/api_gateway?code={code}&function_name={the_other_function}&auth_token={your_auth_token}

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to generate full function URL with key")

    # Get the function_name from query parameters, fallback to env var if not provided
    function_name = req.params.get('function_name') or ''
    if not function_name:
        return func.HttpResponse(
            "Please provide a function_name query parameter",
            status_code=400
        )

    try:
        credential = DefaultAzureCredential()
        client = WebSiteManagementClient(credential, SUBSCRIPTION_ID)
        #key_to_return = 'default' > you can create multiple keys as 
        #well for each function app but we use default
        #########
        keys = client.web_apps.list_function_keys(function_name, key_to_return="default")
        default_key = keys.keys.get("default")
        if not default_key:
            logger.error(f"Error fetching function key for '{function_name}': {e}")
            return func.HttpResponse(f"No default key found for function '{function_name}'", status_code=500)

        base_url = f"https://{API_FUNCTION_APP_NAME}.azurewebsites.net/{function_name}"
        full_url = f"{base_url}?code={default_key}"
        return func.HttpResponse(full_url, status_code=200)

    except Exception as e:
        logger.error(f"Error fetching function key for '{function_name}': {e}")
        return func.HttpResponse("Failed to get function key", status_code=500)