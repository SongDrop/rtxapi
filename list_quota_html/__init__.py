import logging
import os
import json
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient

def generate_quota_html(quota_data):
    """Generate HTML from quota data"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Azure Resource Quotas</title>
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
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #0078d4;
                border-bottom: 2px solid #0078d4;
                padding-bottom: 10px;
            }}
            .location-info {{
                background-color: #e3f2fd;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
            }}
            .quota-header {{
                display: grid;
                grid-template-columns: 2fr 1fr 1fr 1fr;
                font-weight: bold;
                background-color: #0078d4;
                color: white;
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            .quota-item {{
                display: grid;
                grid-template-columns: 2fr 1fr 1fr 1fr;
                padding: 12px;
                border-bottom: 1px solid #e0e0e0;
                align-items: center;
            }}
            .quota-item:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .usage-bar {{
                height: 20px;
                background-color: #e0e0e0;
                border-radius: 10px;
                margin-top: 5px;
                overflow: hidden;
            }}
            .usage-fill {{
                height: 100%;
                background-color: #0078d4;
                border-radius: 10px;
            }}
            .high-usage {{
                background-color: #ff5722;
            }}
            .medium-usage {{
                background-color: #ff9800;
            }}
            .low-usage {{
                background-color: #4caf50;
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
            .summary-card {{
                display: flex;
                justify-content: space-around;
                margin-bottom: 20px;
            }}
            .card {{
                background-color: #e3f2fd;
                padding: 15px;
                border-radius: 4px;
                text-align: center;
                flex: 1;
                margin: 0 10px;
            }}
            .card h3 {{
                margin-top: 0;
                color: #0078d4;
            }}
            .card-value {{
                font-size: 24px;
                font-weight: bold;
                color: #0078d4;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Azure Resource Quotas</h1>
            <button class="refresh-btn" onclick="window.location.reload()">Refresh Quotas</button>
            
            <div class="location-info">
                <strong>Resource Group:</strong> {quota_data['resource_group']} <br>
                <strong>Location:</strong> {quota_data['location']} <br>
                <strong>Total Quotas:</strong> {len(quota_data['quotas'])}
            </div>
            
            <div class="summary-card">
                <div class="card">
                    <h3>High Usage</h3>
                    <div class="card-value" id="high-usage-count">0</div>
                    <div>> 80% utilized</div>
                </div>
                <div class="card">
                    <h3>Medium Usage</h3>
                    <div class="card-value" id="medium-usage-count">0</div>
                    <div>50-80% utilized</div>
                </div>
                <div class="card">
                    <h3>Low Usage</h3>
                    <div class="card-value" id="low-usage-count">0</div>
                    <div>< 50% utilized</div>
                </div>
            </div>
            
            <div class="quota-header">
                <span>Resource Type</span>
                <span>Current Usage</span>
                <span>Limit</span>
                <span>Utilization</span>
            </div>
    """
    
    # Counters for summary cards
    high_usage = 0
    medium_usage = 0
    low_usage = 0
    
    # Add each quota to the HTML
    for quota in quota_data['quotas']:
        # Calculate utilization percentage
        if quota['limit'] > 0:
            utilization = (quota['current_value'] / quota['limit']) * 100
        else:
            utilization = 0
            
        # Determine usage class for coloring
        if utilization > 80:
            usage_class = "high-usage"
            high_usage += 1
        elif utilization > 50:
            usage_class = "medium-usage"
            medium_usage += 1
        else:
            usage_class = "low-usage"
            low_usage += 1
        
        html_content += f"""
            <div class="quota-item">
                <span>{quota['name']}</span>
                <span>{quota['current_value']} {quota['unit']}</span>
                <span>{quota['limit']} {quota['unit']}</span>
                <span>
                    {utilization:.1f}%
                    <div class="usage-bar">
                        <div class="usage-fill {usage_class}" style="width: {utilization}%"></div>
                    </div>
                </span>
            </div>
        """
    
    # Add JavaScript to update summary cards
    html_content += f"""
        </div>
        <script>
            document.getElementById('high-usage-count').textContent = '{high_usage}';
            document.getElementById('medium-usage-count').textContent = '{medium_usage}';
            document.getElementById('low-usage-count').textContent = '{low_usage}';
        </script>
    </body>
    </html>
    """
    
    return html_content

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

        # Return HTML if requested
        if format_html:
            html_output = generate_quota_html(result)
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