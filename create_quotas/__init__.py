import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
import requests

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to create Azure quota increase request.')

    try:
        # Parse inputs from JSON body
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        #Get paramenters
        # Requested CPU cores limit
        cpu_limit = req_body.get('cpu_limit') or req.params.get('cpu_limit')
        # Example: "Standard_Dv2_Family", "Standard_B_Family", etc.
        vm_family = req_body.get('vm_family') or req.params.get('vm_family')
        # Example: "Standard_Dv2_Family", "Standard_B_Family", etc.
        location = req_body.get('location') or req.params.get('location') or 'uksouth'
        # Example: "Standard_Dv2_Family", "Standard_B_Family", etc.
        quota_desc = req_body.get('quota_desc') or req.params.get('v') or 'Increase quota on Azure'

        # Required parameters
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        if not subscription_id:
            return func.HttpResponse(
                json.dumps({"error": "AZURE_SUBSCRIPTION_ID environment variable is missing"}),
                status_code=500,
                mimetype="application/json"
            )
        resource_location = req_body.get("location")
        if not resource_location:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'location' in request body"}),
                status_code=400,
                mimetype="application/json"
            )
        if not vm_family:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'vm_family' in request body"}),
                status_code=400,
                mimetype="application/json"
            )

        if cpu_limit is None:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'cpu_limit' in request body"}),
                status_code=400,
                mimetype="application/json"
            )

        # Authenticate using ClientSecretCredential
        try:
            credential = ClientSecretCredential(
                client_id=os.getenv("AZURE_APP_CLIENT_ID"),
                client_secret=os.getenv("AZURE_APP_CLIENT_SECRET"),
                tenant_id=os.getenv("AZURE_TENANT_ID")
            )
        except Exception as e:
            logging.error(f"Authentication error: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Authentication failure"}),
                status_code=500,
                mimetype="application/json"
            )

        # Acquire token for Azure Management API
        token = credential.get_token("https://management.azure.com/.default")
        access_token = token.token

        # Prepare REST API URL for quota request
        url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            f"/providers/Microsoft.Compute/locations/{resource_location}"
            f"/providers/Microsoft.Quota/quotas/{vm_family}/request?api-version=2022-08-01"
        )

        # Prepare request body according to Azure Quota API spec
        # See https://learn.microsoft.com/en-us/rest/api/compute/resource-quotas/request-quota-increase
        request_body = {
            "properties": {
                "newLimit": cpu_limit,
                "quotaRequestType": "StandardQuotaIncrease"
            }
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Call the REST API to create quota increase request
        response = requests.post(url, headers=headers, json=request_body)

        if response.status_code not in (200, 201, 202):
            logging.error(f"Quota request failed: {response.status_code} {response.text}")
            return func.HttpResponse(
                json.dumps({
                    "error": "Quota request failed",
                    "status_code": response.status_code,
                    "response": response.text
                }),
                status_code=500,
                mimetype="application/json"
            )

        return func.HttpResponse(
            response.text,
            status_code=response.status_code,
            mimetype="application/json"
        )

    except Exception as ex:
        logging.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )