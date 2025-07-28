import os
import json
import logging
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.dns import DnsManagementClient
import asyncio
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

executor = concurrent.futures.ThreadPoolExecutor()

async def run_blocking(func, *args, **kwargs):
    """
    Helper to run blocking function in thread pool asynchronously.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

async def delete_vm_and_resources(compute_client, network_client, dns_client, resource_group, vm_name, domain, a_records_list, response_log):
    try:
        # Get VM details
        vm = await run_blocking(compute_client.virtual_machines.get, resource_group, vm_name)
        os_disk_name = None
        if vm.storage_profile and vm.storage_profile.os_disk:
            os_disk_name = vm.storage_profile.os_disk.name
    except Exception as e:
        response_log.append({"warning": f"Failed to get VM '{vm_name}': {str(e)}"})
        os_disk_name = None

    # Define deletion coroutines
    async def delete_vm():
        try:
            await run_blocking(compute_client.virtual_machines.begin_delete(resource_group, vm_name).result)
            response_log.append({"success": f"Deleted VM '{vm_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete VM '{vm_name}': {str(e)}"})

    async def delete_os_disk():
        if not os_disk_name:
            return
        try:
            await run_blocking(compute_client.disks.begin_delete(resource_group, os_disk_name).result)
            response_log.append({"success": f"Deleted OS disk '{os_disk_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete OS disk '{os_disk_name}': {str(e)}"})

    async def delete_nic():
        nic_name = f"{vm_name}-nic"
        try:
            await run_blocking(network_client.network_interfaces.begin_delete(resource_group, nic_name).result)
            response_log.append({"success": f"Deleted NIC '{nic_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete NIC '{nic_name}': {str(e)}"})

    async def delete_nsg():
        nsg_name = f"{vm_name}-nsg"
        try:
            await run_blocking(network_client.network_security_groups.begin_delete(resource_group, nsg_name).result)
            response_log.append({"success": f"Deleted NSG '{nsg_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete NSG '{nsg_name}': {str(e)}"})

    async def delete_public_ip():
        public_ip_name = f"{vm_name}-public-ip"
        try:
            await run_blocking(network_client.public_ip_addresses.begin_delete(resource_group, public_ip_name).result)
            response_log.append({"success": f"Deleted Public IP '{public_ip_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete Public IP '{public_ip_name}': {str(e)}"})

    async def delete_vnet():
        vnet_name = f"{vm_name}-vnet"
        try:
            await run_blocking(network_client.virtual_networks.begin_delete(resource_group, vnet_name).result)
            response_log.append({"success": f"Deleted VNet '{vnet_name}'."})
        except Exception as e:
            response_log.append({"warning": f"Failed to delete VNet '{vnet_name}': {str(e)}"})

    async def delete_dns_records():
        for record_name in a_records_list:
            record_to_delete = record_name if record_name else '@'
            try:
                await run_blocking(dns_client.record_sets.delete, resource_group, domain, record_to_delete, 'A')
                response_log.append({"success": f"Deleted DNS A record '{record_to_delete}' in zone '{domain}'."})
            except Exception as e:
                response_log.append({"warning": f"Failed to delete DNS A record '{record_to_delete}' in zone '{domain}': {str(e)}"})

    # Run deletions concurrently where possible
    # VM and OS disk deletions must be sequential since disk depends on VM
    await delete_vm()
    await delete_os_disk()

    # Run network related deletes concurrently
    await asyncio.gather(
        delete_nic(),
        delete_nsg(),
        delete_public_ip(),
        delete_vnet(),
        delete_dns_records()
    )

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing request to delete VM and related resources.")

    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        vm_name = req_body.get('vm_name') or req.params.get('vm_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        domain = req_body.get('domain') or req.params.get('domain')
        a_records = vm_name  # single record name string, so split works

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
        if not domain:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'domain' parameter"}),
                status_code=400,
                mimetype="application/json"
            )

        # a_records can be comma separated string or list
        if isinstance(a_records, str):
            a_records_list = [r.strip() for r in a_records.split(",") if r.strip()]
        elif isinstance(a_records, list):
            a_records_list = a_records
        else:
            a_records_list = []

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            err = "AZURE_SUBSCRIPTION_ID environment variable is not set."
            logger.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        try:
            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )
        except KeyError as e:
            err = f"Missing environment variable: {e}"
            logger.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        compute_client = ComputeManagementClient(credentials, subscription_id)
        network_client = NetworkManagementClient(credentials, subscription_id)
        dns_client = DnsManagementClient(credentials, subscription_id)

        response_log = []

        await delete_vm_and_resources(
            compute_client, network_client, dns_client,
            resource_group, vm_name, domain, a_records_list, response_log
        )

        response_log.append({"success": "Deletion process completed."})

        return func.HttpResponse(
            json.dumps({"results": response_log}, indent=2),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as ex:
        logger.exception("Unhandled error:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )