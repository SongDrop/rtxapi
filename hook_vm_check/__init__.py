import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
import logging
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
    logging.info('Processing create_vm request...')
 
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        sas_url = req_body.get('sas_url') or req.params.get('sas_url')

 
        ###Parameter checking to handle errors 
        if not vm_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'vm_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not sas_url:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'sas_url' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
    
        
        # Fetch JSON content from the blob using SAS URL
        response = requests.get(sas_url)
        if response.status_code != 200:
            return func.HttpResponse(
                json.dumps({"error": f"Failed to fetch blob content, status code {response.status_code}"}),
                status_code=500,
                mimetype="application/json"
            )

        # Attempt to parse JSON from response
        try:
            data = response.json()
        except json.JSONDecodeError:
            return func.HttpResponse(
                json.dumps({"error": "Blob content is not valid JSON"}),
                status_code=500,
                mimetype="application/json"
            )

        return func.HttpResponse(
            json.dumps(data),
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
 