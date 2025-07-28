import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to list Azure subscription quotas.')

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

        # Get resource group to find location
        try:
            rg = resource_client.resource_groups.get(resource_group)
            location = rg.location
            logging.info(f"Resource group '{resource_group}' is in location '{location}'.")
        except Exception as e:
            err = f"Resource group '{resource_group}' not found or inaccessible: {e}"
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=404,
                mimetype="application/json"
            )

        # List usage (quotas) for the location
        try:
            usage_list = compute_client.usage.list(location)
            quotas = []
            for usage in usage_list:
                name = usage.name.value if hasattr(usage.name, 'value') else usage.name
                unit = usage.unit.value if hasattr(usage.unit, 'value') else usage.unit
                quotas.append({
                    "name": name,
                    "current_value": usage.current_value,
                    "limit": usage.limit,
                    "unit": unit
                })

            result = {
                "resource_group": resource_group,
                "location": location,
                "quotas": quotas
            }
        except Exception as e:
            err = f"Error retrieving quota information: {e}"
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

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