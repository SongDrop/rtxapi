import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient

def get_ip_from_vm_name(credentials, subscription_id, vm_name, resource_group):
    """Get the private and public IP addresses for a VM"""
    try:
        network_client = NetworkManagementClient(credentials, subscription_id)
        
        # Get the VM to find its network interfaces
        compute_client = ComputeManagementClient(credentials, subscription_id)
        vm = compute_client.virtual_machines.get(resource_group, vm_name)
        
        # Get network interfaces
        network_interface_refs = vm.network_profile.network_interfaces
        ips = {"private": "N/A", "public": "N/A"}
        
        for interface_ref in network_interface_refs:
            # Extract interface name from ID
            interface_name = interface_ref.id.split('/')[-1]
            
            # Get the network interface
            network_interface = network_client.network_interfaces.get(
                resource_group, interface_name
            )
            
            # Get private IP
            if network_interface.ip_configurations:
                private_ip = network_interface.ip_configurations[0].private_ip_address
                ips["private"] = private_ip if private_ip else "N/A"
                
                # Check for public IP
                public_ip_ref = network_interface.ip_configurations[0].public_ip_address
                if public_ip_ref:
                    public_ip_name = public_ip_ref.id.split('/')[-1]
                    public_ip = network_client.public_ip_addresses.get(
                        resource_group, public_ip_name
                    )
                    ips["public"] = public_ip.ip_address if public_ip.ip_address else "N/A"
        
        return ips
        
    except Exception as e:
        logging.error(f"Error getting IP for VM {vm_name}: {e}")
        return {"private": "N/A", "public": "N/A"}

def is_valid_ip(ip):
    """Check if the IP address is valid (simple IPv4 check)"""
    import re
    if ip == "N/A":
        return False
    ipv4_regex = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return re.match(ipv4_regex, ip) is not None

def generate_html(vm_data, credentials, subscription_id):
    """Generate HTML from VM data with enhanced IP links"""
    # Constants for the links (same as in your Tampermonkey script)
    logoURL = "https://i.postimg.cc/L8kDTTsb/96252163.png"
    baseURL = "https://cdn.sdappnet.cloud/rtx/rtxvm.html?url="
    formURL = 'https://forms.gle/QgFZQhaehZLs9sySA'
    dumbdropURL = "https://i.postimg.cc/RF5FDjQx/icon.png"
    dumbdropPort = "3475"
    rdpURL = "https://i.postimg.cc/VsCWBLfm/rdp.png"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Azure Virtual Machines</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #242424;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 10px;
            }}
            h1 {{
                color: #0078d4;
                border-bottom: 2px solid #0078d4;
                padding-bottom: 10px;
            }}
            .vm-header {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                font-weight: bold;
                background-color: #0078d4;
                color: white;
                padding: 10px;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            .vm-item {{
                margin-bottom: 15px;
                padding: 15px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #f9f9f9;
            }}
            .vm-name {{
                font-weight: bold;
                color: #0078d4;
                margin-bottom: 5px;
            }}
            .vm-link {{
                display: inline-block;
                background-color: #0078d4;
                color: white;
                padding: 8px 15px;
                text-decoration: none;
                border-radius: 4px;
                margin-top: 8px;
                transition: background-color 0.3s;
            }}
            .vm-link:hover {{
                background-color: #106ebe;
            }}
            .vm-instance {{
                color: #505050;
                font-style: italic;
            }}
            .ip-info {{
                margin-top: 5px;
                font-size: 0.9em;
            }}
            .refresh-btn {{
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 4px;
                cursor: pointer;
                margin-bottom: 20px;
            }}
            .refresh-btn:hover {{
                background-color: #106ebe;
            }}
            .ip-link-container {{
                margin-top: 8px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .ip-logo {{
                height: 16px;
                vertical-align: middle;
            }}
            .ip-link {{
                color: #0078d4;
                text-decoration: none;
                font-size: 0.9em;
                margin-left: 6px;
            }}
            .ip-link:hover {{
                text-decoration: underline;
            }}
            .ip-address {{
                font-weight: bold;
                color: #242424;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Azure Virtual Machines</h1>
            <button class="refresh-btn" onclick="window.location.reload()">Refresh IP Addresses</button>
            
            <div class="vm-header">
                <span>Group Name | Location</span>
                <span>IP Addresses</span>
            </div>
    """
    
    # Add each VM to the HTML
    for vm in vm_data['vms']:
        # Get IP addresses for this VM
        ips = get_ip_from_vm_name(credentials, subscription_id, vm['name'], vm_data['resource_group'])
        
        # Determine which IP to use for connection (prefer public, fallback to private)
        connect_ip = ips['public'] if ips['public'] != "N/A" else ips['private']
        
        html_content += f"""
            <div class="vm-item">
                <div class="vm-name">{vm['name']}</div>
                <div>{vm_data['resource_group']} | {vm['location']}</div>
                <div class="vm-instance">{vm['vm_size']}</div>
                <div class="ip-info">
        """
        
        # Add enhanced IP links for private IP if it's a valid IP
        if is_valid_ip(ips['private']):
            html_content += f"""
            """
        
        html_content += f"""
                    <br><strong>Public IP:</strong> <span class="ip-address">{ips['public']}</span>
        """
        
        # Add enhanced IP links for public IP if it's a valid IP
        if is_valid_ip(ips['public']):
            html_content += f"""
                    <div class="ip-link-container">
                        <img src="{logoURL}" alt="logo" class="ip-logo">
                        <a class="ip-link" href="{baseURL}{ips['public']}&form={formURL}" target="_blank">[Connect]</a>
                        <img src="{dumbdropURL}" alt="files" class="ip-logo">
                        <a class="ip-link" href="https://{ips['public']}:{dumbdropPort}" target="_blank">[Files]</a>
                        <img src="{rdpURL}" alt="rdp" class="ip-logo">
                        <a class="ip-link" href="https://cdn.sdappnet.cloud/rtx/rdpgen.html?ip={ips['public']}&user=source&vm_name={vm['name']}" target="_blank">RDP Windows</a>
                    </div>
            """
        
        html_content += f"""
        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    return html_content

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

        # Check if HTML format is requested - check both body and query params
        format_html = req_body.get('format') == 'html' or req.params.get('format') == 'html'

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
            
            # Return HTML if requested
            if format_html:
                html_output = generate_html(result, credentials, subscription_id)
                return func.HttpResponse(
                    html_output,
                    status_code=200,
                    mimetype="text/html"
                )
            else:
                # Return JSON
                return func.HttpResponse(
                    json.dumps(result),
                    status_code=200,
                    mimetype="application/json"
                )
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