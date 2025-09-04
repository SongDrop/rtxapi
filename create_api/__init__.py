import asyncio
import json
import os
import logging
import aiohttp
from datetime import datetime
from azure.identity import ClientSecretCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.web.models import (
    FunctionApp, AppServicePlan, SkuDescription,
    SiteConfig, NameValuePair, StringDictionary
)
import azure.functions as func
import yaml
import base64
import requests


GITHUB_REPO_URL = "https://github.com/SongDrop/rtxapi"
# MUST HAVE ENVIRONMENTAL VALUES INSIDE FUNCTION APP
# API_NAME
# API_RESOURCE_GROUP
# AZURE_APP_CLIENT_ID
# AZURE_APP_CLIENT_SECRET
# AZURE_APP_TENANT_ID
# AZURE_SUBSCRIPTION_ID
# GITHUB_TOKEN (with repo permissions)
# GITHUB_REPO (format: owner/repo-name)
# SENDER_EMAIL
# SMTP_HOST
# SMTP_PASS
# SMTP_PORT
# SMTP_USER

# "Thanks for wanting to set up the automated API! Before we begin, please make sure you have:
#         A GitHub repository created (format: yourusername/repo-name)
#         A GitHub Personal Access Token with repo permissions
#         Your Azure subscription details ready
#     The system will automatically:
#         📦 Copy my pre-built API template into your repository
#         ⚡ Create the Azure Function App with Flex Consumption
#         🔧 Set up the perfect GitHub Actions workflow
#         🔐 Configure all secrets and environment variables
#         🔗 Connect your repository for automatic deployments
#     You get a complete, production-ready API based on my battle-tested template!"

# The Magic Now Includes:
#     Template Sync: Your repo structure + code gets copied to their repo
#     Zero Setup: They get your months of work instantly
#     Production Ready: Everything is pre-configured and tested
#     Automatic Updates: If you update your template, they can sync updates

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Console colors for logs
class bcolors:
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

def print_info(msg):
    logging.info(f"{bcolors.OKBLUE}[INFO]{bcolors.ENDC} {msg}")

def print_success(msg):
    logging.info(f"{bcolors.OKGREEN}[SUCCESS]{bcolors.ENDC} {msg}")

def print_warn(msg):
    logging.info(f"{bcolors.WARNING}[WARNING]{bcolors.ENDC} {msg}")

def print_error(msg):
    logging.info(f"{bcolors.FAIL}[ERROR]{bcolors.ENDC} {msg}")

# Async helper function
async def run_azure_operation(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing API creation request...')    
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Extract parameters
        api_name = req_body.get('api_name') or req.params.get('api_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        location = req_body.get('location') or req.params.get('location')
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''
        github_repo = req_body.get('github_repo') or req.params.get('github_repo') or os.environ.get('GITHUB_REPO')

        # Parameter validation
        if not api_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'api_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not resource_group:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'resource_group' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not location:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'location' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not github_repo:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'github_repo' parameter and GITHUB_REPO environment variable"}),
                status_code=400,
                mimetype="application/json"
            )

        # Initial status update
        hook_response = await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "init",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        if not hook_response.get("success") and hook_url:
            error_msg = hook_response.get("error", "Unknown error posting status")
            print_error(f"Initial status update failed: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": f"Status update failed: {error_msg}"}),
                status_code=500,
                mimetype="application/json"
            )

        status_url = hook_response.get("status_url", "")

        try:
            # Azure authentication
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "api_name": api_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "authenticating",
                        "message": "Authenticating with Azure"
                    }
                }
            )
            
            # Validate environment variables
            required_vars = [
                'AZURE_APP_CLIENT_ID', 'AZURE_APP_CLIENT_SECRET', 
                'AZURE_APP_TENANT_ID', 'AZURE_SUBSCRIPTION_ID',
                'GITHUB_TOKEN', 'GITHUB_REPO',
                'SENDER_EMAIL', 'SMTP_HOST', 'SMTP_PASS', 'SMTP_PORT', 'SMTP_USER'
            ]
            missing = [var for var in required_vars if not os.environ.get(var)]
            if missing:
                raise Exception(f"Missing environment variables: {', '.join(missing)}")

            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )

            # Start background API creation
            asyncio.create_task(
                create_api_background(
                    credentials,
                    api_name, resource_group, location, hook_url, github_repo
                )
            )

            return func.HttpResponse(
                json.dumps({
                    "message": "API provisioning started",
                    "status_url": status_url,
                    "api_name": api_name,
                    "github_repo": github_repo
                }),
                status_code=202,
                mimetype="application/json"
            )

        except Exception as ex:
            logging.exception("Authentication error:")
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "api_name": api_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "details": {
                        "step": "authentication_error",
                        "error": str(ex),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return func.HttpResponse(
                json.dumps({"error": str(ex)}),
                status_code=500,
                mimetype="application/json"
            )

    except Exception as ex:
        logging.exception("Unhandled error in main function:")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )

async def create_api_background(
    credentials, api_name, resource_group, location, hook_url, github_repo
):
    try:
        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        github_token = os.environ['GITHUB_TOKEN']
        
        # Initialize Azure clients
        web_client = WebSiteManagementClient(credentials, subscription_id)
        
        # Create or get Flex Consumption plan
        plan_name = f"{api_name}-flex-plan"
        
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "creating_plan",
                    "message": f"Creating Flex Consumption plan: {plan_name}"
                }
            }
        )
        
        try:
            app_service_plan = await run_azure_operation(
                web_client.app_service_plans.get,
                resource_group,
                plan_name
            )
            print_info(f"Using existing App Service Plan: {plan_name}")
        except Exception:
            sku_description = SkuDescription(
                name='EP1',
                tier='ElasticPremium',
                size='EP1',
                family='EP',
                capacity=1
            )
            
            plan_params = AppServicePlan(
                location=location,
                sku=sku_description,
                kind='functionapp,linux,elastic',
                reserved=True
            )
            
            plan_operation = web_client.app_service_plans.begin_create_or_update(
                resource_group,
                plan_name,
                plan_params
            )
            app_service_plan = await run_azure_operation(plan_operation.result)
            print_success(f"Created Flex Consumption plan: {plan_name}")
        
        # Create Function App
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "creating_function_app",
                    "message": f"Creating Function App: {api_name}"
                }
            }
        )
        
        # Create storage account for function app
        storage_account_name = f"{api_name}storage".replace('-', '')[:24].lower()
        
        # Configure app settings
        app_settings = [
            NameValuePair(name="FUNCTIONS_WORKER_RUNTIME", value="python"),
            NameValuePair(name="FUNCTIONS_EXTENSION_VERSION", value="~4"),
            NameValuePair(name="PYTHON_ISOLATE_WORKER_DEPENDENCIES", value="1"),
            NameValuePair(name="SCM_DO_BUILD_DURING_DEPLOYMENT", value="true"),
            NameValuePair(name="ENABLE_ORYX_BUILD", value="true"),
            NameValuePair(name="WEBSITE_RUN_FROM_PACKAGE", value="1"),
            NameValuePair(name="AzureWebJobsStorage", value=f"DefaultEndpointsProtocol=https;AccountName={storage_account_name};AccountKey=...;EndpointSuffix=core.windows.net"),
            NameValuePair(name="APPLICATIONINSIGHTS_CONNECTION_STRING", value=f"InstrumentationKey=..."),
            NameValuePair(name="WEBSITE_CONTENTAZUREFILECONNECTIONSTRING", value=f"DefaultEndpointsProtocol=https;AccountName={storage_account_name};AccountKey=...;EndpointSuffix=core.windows.net"),
            NameValuePair(name="WEBSITE_CONTENTSHARE", value=api_name.lower()),
        ]
        
        site_config = SiteConfig(
            linux_fx_version="PYTHON|3.12",
            app_settings=app_settings
        )
        
        function_app_params = FunctionApp(
            location=location,
            server_farm_id=app_service_plan.id,
            site_config=site_config,
            reserved=True,
            https_only=True
        )
        
        function_app_operation = web_client.web_apps.begin_create_or_update(
            resource_group,
            api_name,
            function_app_params
        )
        
        function_app = await run_azure_operation(function_app_operation.result)
        print_success(f"Created Function App: {api_name}")
        
        # Configure SCM Basic Auth Publishing
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "configuring_scm",
                    "message": "Configuring SCM Basic Auth Publishing"
                }
            }
        )
        
        # Get current config and update SCM settings
        config_operation = web_client.web_apps.list_metadata(
            resource_group,
            api_name
        )
        metadata = await run_azure_operation(config_operation)
        
        # Set SCM Basic Auth Publishing to True
        metadata.properties["SCM_BASIC_AUTH_PUBLISHING"] = "True"
        
        update_operation = web_client.web_apps.update_metadata(
            resource_group,
            api_name,
            metadata
        )
        await run_azure_operation(update_operation)
        print_success("Configured SCM Basic Auth Publishing")
        
        # Get publish profile for GitHub Actions
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "getting_publish_profile",
                    "message": "Retrieving publish profile"
                }
            }
        )
        
        publish_profile_operation = web_client.web_apps.list_publishing_profile_xml_with_secrets(
            resource_group,
            api_name
        )
        publish_profile = await run_azure_operation(publish_profile_operation)
        
        # Setup GitHub repository with workflow
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "configuring_github",
                    "message": "Configuring GitHub repository"
                }
            }
        )
        
        # Setup GitHub repository with the correct workflow
        github_success = await setup_github_repository(
            api_name, resource_group, github_repo, github_token, publish_profile
        )
        
        if not github_success:
            raise Exception("Failed to configure GitHub repository")
        
        # Send completion email
        await send_api_creation_email(api_name, resource_group, location, publish_profile, github_repo)
        
        # Final success update
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "completed",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "completed",
                    "message": "API provisioning successful",
                    "api_url": f"https://{api_name}.azurewebsites.net",
                    "github_repo": f"https://github.com/{github_repo}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        print_success(f"Azure Function API provisioning completed successfully!")
        print_success(f"API URL: https://{api_name}.azurewebsites.net")
        print_success(f"GitHub Repo: https://github.com/{github_repo}")
        
    except Exception as e:
        # Top-level error handler for background task
        error_msg = f"Unhandled exception in background task: {str(e)}"
        print_error(error_msg)
        
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "failed",
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "background_task_failed",
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

async def setup_github_repository(api_name, resource_group, github_repo, github_token, publish_profile, hook_url, location):
    """Setup GitHub repository by syncing from template and configuring workflow"""
    try:
        owner, repo_name = github_repo.split('/')
        
        # GitHub API headers
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # 1. FIRST: Sync from your template repository
        template_owner = "your-github-username"  # ← YOUR GitHub username
        template_repo = "your-api-template-repo" # ← YOUR template repo name
        
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "api_name": api_name,
                "status": "provisioning", 
                "resource_group": resource_group,
                "location": location,
                "details": {
                    "step": "syncing_template",
                    "message": f"Syncing from template: {template_owner}/{template_repo}"
                }
            }
        )
        
        # Method 1: Use GitHub API to sync from template (if user repo is empty)
        sync_url = f'https://api.github.com/repos/{github_repo}/merge-upstream'
        sync_data = {
            'branch': 'main',
            'commit_message': f'Sync from template {template_owner}/{template_repo}'
        }
        
        # Try to sync from upstream first
        try:
            response = requests.post(sync_url, headers=headers, json=sync_data)
            if response.status_code == 200:
                print_success("Synced from template repository successfully")
        except:
            # If sync fails, use alternative method: create files manually
            print_warn("Upstream sync failed, manually creating template files")
            await create_template_files(github_repo, github_token, template_owner, template_repo)
        
        # 2. Create GitHub workflow with the EXACT format Azure expects
        workflow_content = create_github_workflow_yaml(api_name, resource_group)
        
        workflow_url = f'https://api.github.com/repos/{github_repo}/contents/.github/workflows/main_{api_name}.yml'
        
        workflow_data = {
            'message': f'Add Azure Functions deployment workflow for {api_name}',
            'content': base64.b64encode(workflow_content.encode()).decode(),
            'branch': 'main'
        }
        
        # Check if workflow exists and update it
        response = requests.get(workflow_url, headers=headers)
        if response.status_code == 200:
            workflow_data['sha'] = response.json()['sha']
        
        response = requests.put(workflow_url, headers=headers, json=workflow_data)
        
        if response.status_code not in [200, 201]:
            print_error(f"Failed to create workflow: {response.text}")
            return False
        
        # 3. Create GitHub secret for publish profile
        secret_url = f'https://api.github.com/repos/{github_repo}/actions/secrets/AZUREAPPSERVICE_PUBLISHPROFILE'
        
        # Extract publish profile from XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(publish_profile)
        publish_profile_value = None
        
        for profile in root.findall('.//publishProfile'):
            if profile.get('publishMethod') == 'FTP':
                publish_profile_value = profile.get('userPWD')
                break
        
        if not publish_profile_value:
            print_error("Could not extract publish profile from XML")
            return False
        
        # Create secret
        secret_data = {
            'encrypted_value': publish_profile_value
        }
        
        response = requests.put(secret_url, headers=headers, json=secret_data)
        
        if response.status_code not in [200, 201]:
            print_error(f"Failed to create secret: {response.text}")
            return False
        
        print_success("GitHub repository configured successfully with template sync")
        return True
        
    except Exception as e:
        print_error(f"Failed to setup GitHub repository: {str(e)}")
        return False

async def create_template_files(target_repo, github_token, template_owner, template_repo):
    """Manually create template files if sync fails"""
    try:
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # First, get the file structure from your template repo
        template_url = f'https://api.github.com/repos/{template_owner}/{template_repo}/contents/'
        response = requests.get(template_url, headers=headers)
        
        if response.status_code != 200:
            print_error(f"Failed to get template contents: {response.text}")
            return False
        
        # Copy each file from template to user's repo
        for file_info in response.json():
            if file_info['type'] == 'file' and not file_info['name'].startswith('.'):
                file_content = requests.get(file_info['download_url']).text
                
                create_url = f'https://api.github.com/repos/{target_repo}/contents/{file_info["path"]}'
                create_data = {
                    'message': f'Add {file_info["name"]} from template',
                    'content': base64.b64encode(file_content.encode()).decode(),
                    'branch': 'main'
                }
                
                requests.put(create_url, headers=headers, json=create_data)
        
        print_success("Manually created template files")
        return True
        
    except Exception as e:
        print_error(f"Failed to create template files: {str(e)}")
        return False
    
async def setup_github_repository(api_name, resource_group, github_repo, github_token, publish_profile):
    """Setup GitHub repository with correct workflow and secrets"""
    try:
        owner, repo_name = github_repo.split('/')
        
        # Create GitHub workflow
        workflow_content = create_github_workflow_yaml(api_name, resource_group)
        
        # GitHub API setup
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Create or update workflow file
        workflow_url = f'https://api.github.com/repos/{github_repo}/contents/.github/workflows/main_{api_name}.yml'
        
        workflow_data = {
            'message': f'Add Azure Functions deployment workflow for {api_name}',
            'content': base64.b64encode(workflow_content.encode()).decode(),
            'branch': 'main'
        }
        
        # Check if workflow exists
        response = requests.get(workflow_url, headers=headers)
        if response.status_code == 200:
            workflow_data['sha'] = response.json()['sha']
        
        # Create/update workflow file
        response = requests.put(workflow_url, headers=headers, json=workflow_data)
        
        if response.status_code not in [200, 201]:
            print_error(f"Failed to create workflow: {response.text}")
            return False
        
        # Create GitHub secret for publish profile
        secret_url = f'https://api.github.com/repos/{github_repo}/actions/secrets/AZUREAPPSERVICE_PUBLISHPROFILE'
        
        # Extract publish profile from XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(publish_profile)
        publish_profile_value = None
        
        for profile in root.findall('.//publishProfile'):
            if profile.get('publishMethod') == 'FTP':
                publish_profile_value = profile.get('userPWD')
                break
        
        if not publish_profile_value:
            print_error("Could not extract publish profile from XML")
            return False
        
        # Create secret
        secret_data = {
            'encrypted_value': publish_profile_value
        }
        
        response = requests.put(secret_url, headers=headers, json=secret_data)
        
        if response.status_code not in [200, 201]:
            print_error(f"Failed to create secret: {response.text}")
            return False
        
        print_success("GitHub repository configured successfully")
        return True
        
    except Exception as e:
        print_error(f"Failed to setup GitHub repository: {str(e)}")
        return False

def create_github_workflow_yaml(function_app_name, resource_group):
    """Create the exact GitHub Actions workflow YAML that Azure generates"""
    
    workflow_content = f"""# Docs for the Azure Web Apps Deploy action: https://github.com/azure/functions-action
# More GitHub Actions for Azure: https://github.com/Azure/actions
# More info on Python, GitHub Actions, and Azure Functions: https://aka.ms/python-webapps-actions

name: Build and deploy Python project to Azure Function App - {function_app_name}

on:
  push:
    branches:
      - main
  workflow_dispatch:

env:
  AZURE_FUNCTIONAPP_PACKAGE_PATH: '.' # set this to the path to your web app project, defaults to the repository root
  PYTHON_VERSION: '3.10' # set this to the python version to use (supports 3.6, 3.7, 3.8)

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read #This is required for actions/checkout

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python version
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}

      - name: Create and start virtual environment
        run: |
          python -m venv venv
          source venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt

      - name: Prepare Python dependencies
        run: |
          mkdir -p .python_packages/lib/site-packages
          cp -r venv/lib/python3.10/site-packages/* .python_packages/lib/site-packages/

      - name: Create deployment package
        run: |
          mkdir -p staging
          rsync -a --exclude='venv' --exclude='.git' --exclude='.python_packages' --exclude='staging' . staging/
          mv .python_packages staging/
          cd staging && zip -r ../release.zip .
          cd .. && rm -rf staging .python_packages

      - name: Upload artifact for deployment job
        uses: actions/upload-artifact@v4
        with:
          name: python-app
          path: |
            release.zip
            !venv/

  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment: production
    
    steps:
      - name: Download artifact from build job
        uses: actions/download-artifact@v4
        with:
          name: python-app

      - name: Unzip artifact for deployment
        run: unzip release.zip     
        
      - name: 'Deploy to Azure Functions'
        uses: Azure/functions-action@v1
        id: deploy-to-function
        with:
          app-name: '{function_app_name}'
          slot-name: 'Production'
          package: ${{{{ env.AZURE_FUNCTIONAPP_PACKAGE_PATH }}}}
          publish-profile: ${{{{ secrets.AZUREAPPSERVICE_PUBLISHPROFILE }}}}"""

    return workflow_content

async def send_api_creation_email(api_name, resource_group, location, publish_profile, github_repo):
    """Send email with API creation details"""
    try:
        # This would use your actual email sending function
        print_info(f"API {api_name} created successfully!")
        print_info(f"GitHub Repository: {github_repo}")
        print_info("Publish profile secret added to GitHub")
        
    except Exception as e:
        print_warn(f"Failed to send email: {str(e)}")

async def post_status_update(hook_url: str, status_data: dict) -> dict:
    """Send status update to webhook with retry logic"""
    if not hook_url:
        return {"success": True, "status_url": ""}
    
    step = status_data.get("details", {}).get("step", "unknown")
    print_info(f"Sending status update for step: {step}")
    
    # Retry configuration
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    hook_url,
                    json=status_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "status_url": data.get("status_url", ""),
                            "response": data
                        }
                    else:
                        error_msg = f"HTTP {response.status}"
        except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
            error_msg = str(e)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
        
        # Log failure and retry
        if attempt < max_retries:
            print_warn(f"Status update failed (attempt {attempt}/{max_retries}): {error_msg}")
            await asyncio.sleep(retry_delay * attempt)
        else:
            print_error(f"Status update failed after {max_retries} attempts: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_url": ""
            }
    
    return {"success": False, "error": "Unknown error", "status_url": ""}