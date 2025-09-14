import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from datetime import datetime, timezone

def generate_snapshots_html(snapshot_data):
    """Generate HTML from snapshot data"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Azure Snapshots</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #242424;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #0078d4;
                border-bottom: 2px solid #0078d4;
                padding-bottom: 10px;
            }}
            .summary-info {{
                background-color: #e3f2fd;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
            }}
            .snapshot-header {{
                display: grid;
                grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr;
                font-weight: bold;
                background-color: #0078d4;
                color: white;
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            .snapshot-item {{
                display: grid;
                grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr;
                padding: 12px;
                border-bottom: 1px solid #e0e0e0;
                align-items: center;
            }}
            .snapshot-item:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .refresh-btn {{
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 4px;
                cursor: pointer;
                margin-bottom: 20px;
                font-size: 16px;
            }}
            .refresh-btn:hover {{
                background-color: #106ebe;
            }}
            .size-badge {{
                background-color: #e3f2fd;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                color: #0078d4;
            }}
            .state-active {{
                color: #4caf50;
                font-weight: bold;
            }}
            .state-inactive {{
                color: #ff5722;
            }}
            .action-btn {{
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                margin-right: 5px;
                font-size: 12px;
            }}
            .action-btn:hover {{
                background-color: #106ebe;
            }}
            .delete-btn {{
                background-color: #ff5722;
            }}
            .delete-btn:hover {{
                background-color: #e64a19;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Azure Snapshots</h1>
            <button class="refresh-btn" onclick="window.location.reload()">Refresh Snapshots</button>
            
            <div class="summary-info">
                <strong>Resource Group:</strong> {snapshot_data['resource_group']} <br>
                <strong>Total Snapshots:</strong> {snapshot_data['snapshot_count']} <br>
                <strong>Total Size:</strong> {snapshot_data['total_size_gb']} GB
            </div>
            
            <div class="snapshot-header">
                <span>Snapshot Name</span>
                <span>Size (GB)</span>
                <span>SKU</span>
                <span>Created Time</span>
                <span>Status</span>
                <span>Actions</span>
            </div>
    """
    
    # Add each snapshot to the HTML
    for snapshot in snapshot_data['snapshots']:
        # Format created time
        created_time = snapshot.get('time_created', 'N/A')
        if created_time != 'N/A':
            try:
                created_dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                created_time = created_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        html_content += f"""
            <div class="snapshot-item">
                <span>{snapshot['name']}</span>
                <span><div class="size-badge">{snapshot['disk_size_gb']} GB</div></span>
                <span>{snapshot['sku']}</span>
                <span>{created_time}</span>
                <span class="state-active">{snapshot['provisioning_state']}</span>
                <span>
                    <button class="action-btn" onclick="alert('Create VM from {snapshot['name']}')">Create VM</button>
                    <button class="action-btn delete-btn" onclick="alert('Delete {snapshot['name']}')">Delete</button>
                </span>
            </div>
        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    return html_content

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to list Azure snapshots.')

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

        # Check if HTML format is requested
        format_html = req.params.get('format') == 'html'

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

        # List snapshots in resource group
        try:
            snapshots = compute_client.snapshots.list_by_resource_group(resource_group)
            snapshot_list = []
            total_size_gb = 0
            
            for snapshot in snapshots:
                disk_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                total_size_gb += disk_size_gb
                
                snapshot_list.append({
                    "name": snapshot.name,
                    "location": snapshot.location,
                    "disk_size_gb": disk_size_gb,
                    "sku": snapshot.sku.name if snapshot.sku else "Standard",
                    "provisioning_state": snapshot.provisioning_state,
                    "time_created": snapshot.time_created.isoformat() if snapshot.time_created else "N/A",
                    "os_type": str(snapshot.os_type) if snapshot.os_type else "Unknown",
                    "hyper_v_generation": str(snapshot.hyper_v_generation) if snapshot.hyper_v_generation else "Unknown"
                })
            
            result = {
                "resource_group": resource_group,
                "snapshot_count": len(snapshot_list),
                "total_size_gb": total_size_gb,
                "snapshots": snapshot_list
            }
            
        except Exception as e:
            err = f"Error retrieving snapshots: {e}"
            logging.error(err)
            return func.HttpResponse(
                json.dumps({"error": err}),
                status_code=500,
                mimetype="application/json"
            )

        # Return HTML if requested
        if format_html:
            html_output = generate_snapshots_html(result)
            return func.HttpResponse(
                html_output,
                status_code=200,
                mimetype="text/html"
            )
        else:
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