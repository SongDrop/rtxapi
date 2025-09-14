import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to list Azure resources/VMs.')

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

        list_vms_only = req_body.get('list_vms_only')
        if list_vms_only is None:
            # fallback to query param, treat 'yes'/'true'/1 as True
            list_vms_only_str = req.params.get('list_vms_only', 'yes').lower()
            list_vms_only = list_vms_only_str in ['yes', 'y', 'true', '1', '']

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

        # Check if resource group exists
        try:
            _ = resource_client.resource_groups.get(resource_group)
        except Exception as e:
            err = f"Resource group '{resource_group}' not found or inaccessible: {e}"
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=404,
                mimetype="application/json"
            )

        if list_vms_only:
            # List VMs in resource group
            vms = compute_client.virtual_machines.list(resource_group)
            vm_list = []
            for vm in vms:
                vm_list.append({
                    "name": vm.name,
                    "location": vm.location,
                    "vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else None
                })
            result = {
                "resource_group": resource_group,
                "vm_count": len(vm_list),
                "vms": vm_list
            }
        else:
            # List all resources in resource group
            resources = resource_client.resources.list_by_resource_group(resource_group)
            res_list = []
            for res in resources:
                res_list.append({
                    "name": res.name,
                    "type": res.type,
                    "location": res.location
                })
            result = {
                "resource_group": resource_group,
                "resource_count": len(res_list),
                "resources": res_list
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