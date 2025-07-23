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


from azure.identity import ClientSecretCredential
from azure.mgmt.web import WebSiteManagementClient
import os
import json
import logging
import azure.functions as func

logger = logging.getLogger(__name__)

def get_function_key(function_name, key_to_return: str = "default"):
    try:
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
            # Returning None instead of HttpResponse here; 
            # HttpResponse should be returned from Azure Function main handler, not helper function
            return None

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            logger.error("AZURE_SUBSCRIPTION_ID environment variable is not set.")
            return None

        client = WebSiteManagementClient(credentials, subscription_id)
        keys = client.web_apps.list_function_keys(os.environ.get('API_RESOURCE_GROUP'), os.environ.get('API_NAME'), function_name)
        
        if keys and hasattr(keys, 'keys') and keys.keys:
            default_key = keys.keys.get(key_to_return)
            if default_key:
                return default_key
            else:
                logger.error(f"Key '{key_to_return}' not found for function '{function_name}'.")
                return None
        else:
            logger.error(f"No keys found for function '{function_name}'.")
            return None

    except Exception as e:
        logger.error(f"Exception fetching function key for '{function_name}': {e}", exc_info=True)
        return None

#This function acts as a api-gateway
#https://myapi-{azure_id}.uksouth-01.azurewebsites.net/api_gateway?code={code}&function_name={the_other_function}
#you call this function with the other function name such as 'create_vm' in request and it will return back
#https://myapi-{azure_id}.uksouth-01.azurewebsites.net/create_vm?code={default_sas_token}
#here we are essentially giving back the correct api function link with the SAS token added

#this approach also allow to do extra authentication for the proxy
##https://myapi-{azure_id}.uksouth-01.azurewebsites.net/api_gateway?code={code}&function_name={the_other_function}&auth_token={your_auth_token}

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to generate full function URL with key")

    try:
        req_body = req.get_json()
    except ValueError:
        req_body = {}

    # Get parameters from JSON body or query parameters
    function_name = req_body.get('function_name') or req.params.get('function_name')
    if not function_name:
        return func.HttpResponse(
            "Please provide a function_name query parameter",
            status_code=400
        )

    # if not all([SUBSCRIPTION_ID, API_RESOURCE_GROUP, API_NAME, API_DEFAULT_DOMAIN]):
    #     logger.error("One or more required environment variables are missing.")
    #     return func.HttpResponse(
    #         "One or more required environment variables are missing.",
    #         status_code=400
    #     )
    # #key_to_return = 'default' > you can create multiple keys as 
    # #well for each function app but we use default
    # #########
    # key_to_return = "default"
    # default_key = get_function_key(function_name, key_to_return)
    # if not default_key:
    #     logger.error(f"No '{key_to_return}' key found for function '{function_name}'.")
    #     return func.HttpResponse(
    #         f"No'{key_to_return}' key found for function '{function_name}'.",
    #         status_code=404
    #     )

    # base_url = f"https://{API_DEFAULT_DOMAIN}/{function_name}"
    # full_url = f"{base_url}?code={default_key}"
    # return func.HttpResponse(full_url, status_code=200)

    method = req.method
    if method == "GET":
        return func.HttpResponse("create_vm: Received a GET request", status_code=200)
    elif method == "POST":
        return func.HttpResponse("create_vm: Received a POST request", status_code=200)
    else:
        return func.HttpResponse(f"create_vm: Received a {method} request", status_code=200)
        return func.HttpResponse(f"Received a {method} request", status_code=200)
