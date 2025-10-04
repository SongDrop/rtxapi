import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.resource import ResourceManagementClient


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to list DNS records for a zone.')

    try:
        # Parse inputs
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        domain = req_body.get('domain') or req.params.get('domain')
        record_type = req_body.get('record_type') or req.params.get('record_type')  # optional

        if not resource_group or not domain:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'resource_group' or 'domain' parameter"}),
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
        dns_client = DnsManagementClient(credentials, subscription_id)

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

        # If no specific record type requested, fetch multiple types
        record_types = (
            [record_type.upper()]
            if record_type
            else ["A", "AAAA", "CNAME", "MX", "NS", "PTR", "SRV", "TXT"]
        )

        all_records = {}

        for rtype in record_types:
            try:
                record_sets = dns_client.record_sets.list_by_type(
                    resource_group_name=resource_group,
                    zone_name=domain,
                    record_type=rtype
                )
            except Exception as e:
                logging.warning(f"Could not fetch {rtype} records: {e}")
                continue

            record_list = []
            for record in record_sets:
                entry = {"name": record.name, "ttl": record.ttl}

                if rtype == "A":
                    entry["ip_addresses"] = [r.ipv4_address for r in record.a_records] if record.a_records else []
                elif rtype == "AAAA":
                    entry["ip_addresses"] = [r.ipv6_address for r in record.aaaa_records] if record.aaaa_records else []
                elif rtype == "CNAME":
                    entry["cname"] = record.cname_record.cname if record.cname_record else None
                elif rtype == "MX":
                    entry["exchange"] = [f"{r.exchange} (priority {r.preference})" for r in record.mx_records] if record.mx_records else []
                elif rtype == "NS":
                    entry["ns_records"] = [r.nsdname for r in record.ns_records] if record.ns_records else []
                elif rtype == "PTR":
                    entry["ptr_records"] = [r.ptrdname for r in record.ptr_records] if record.ptr_records else []
                elif rtype == "SRV":
                    entry["srv_records"] = [
                        f"{r.target}:{r.port} (priority {r.priority}, weight {r.weight})"
                        for r in record.srv_records
                    ] if record.srv_records else []
                elif rtype == "TXT":
                    entry["text_records"] = [" ".join(r.value) for r in record.txt_records] if record.txt_records else []

                record_list.append(entry)

            all_records[rtype] = record_list

        result = {
            "resource_group": resource_group,
            "domain": domain,
            "record_types_requested": record_types,
            "records": all_records
        }

        return func.HttpResponse(
            json.dumps(result, indent=2),
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
