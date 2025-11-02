import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
import logging
from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.cognitiveservices.models import (
    CognitiveServicesAccount,
    Sku,
    CognitiveServicesAccountProperties,
    ApiProperties,
    Deployment,
    DeploymentProperties,
    DeploymentModel,
    DeploymentScaleSettings
)
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SearchField,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField
)
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.search import SearchManagementClient
from azure.mgmt.search.models import SearchService, Sku as SearchSku
import azure.functions as func
import aiohttp
from . import html_email
from . import html_email_send

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting LLM deployment application initialization...")

# LLM deployment constants - ALWAYS DEPLOY ADA-002 FOR EMBEDDINGS + MAIN MODEL
SUPPORTED_MODELS = {
    "gpt-4": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "gpt-4",
        "model_name": "gpt-4",
        "max_tokens": 8192,
        "type": "completion"
    },
    "gpt-4-32k": {
        "kind": "OpenAI", 
        "sku": "S0",
        "deployment_name": "gpt-4-32k",
        "model_name": "gpt-4-32k",
        "max_tokens": 32768,
        "type": "completion"
    },
    "gpt-35-turbo": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "gpt-35-turbo",
        "model_name": "gpt-35-turbo",
        "max_tokens": 4096,
        "type": "completion"
    },
    "deepseek-coder": {
        "kind": "OpenAI",
        "sku": "S0", 
        "deployment_name": "deepseek-coder",
        "model_name": "deepseek-coder",
        "max_tokens": 4096,
        "type": "completion"
    },
    "deepseek-chat": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "deepseek-chat", 
        "model_name": "deepseek-chat",
        "max_tokens": 4096,
        "type": "completion"
    },
    "llama-2-7b": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "llama-2-7b",
        "model_name": "llama-2-7b",
        "max_tokens": 4096,
        "type": "completion"
    },
    "llama-2-70b": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "llama-2-70b",
        "model_name": "llama-2-70b", 
        "max_tokens": 4096,
        "type": "completion"
    },
    "claude-3-sonnet": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "claude-3-sonnet",
        "model_name": "claude-3-sonnet",
        "max_tokens": 4096,
        "type": "completion"
    },
    # EMBEDDING MODEL - ALWAYS DEPLOYED
    "text-embedding-ada-002": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "text-embedding-ada-002",
        "model_name": "text-embedding-ada-002", 
        "dimensions": 1536,
        "type": "embeddings"
    }
}

VECTOR_INDEX_CONFIGS = {
    "small": {
        "vector_dimension": 1536,
        "hnsw_parameters": {
            "m": 4,
            "efConstruction": 400,
            "efSearch": 500
        }
    },
    "medium": {
        "vector_dimension": 1536, 
        "hnsw_parameters": {
            "m": 8,
            "efConstruction": 800,
            "efSearch": 1000
        }
    },
    "large": {
        "vector_dimension": 1536,
        "hnsw_parameters": {
            "m": 16,
            "efConstruction": 1600,
            "efSearch": 2000
        }
    }
}

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

async def run_azure_operation(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)
 
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing LLM deployment request...')
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Extract parameters with defaults
        deployment_name = req_body.get('deployment_name') or req.params.get('deployment_name')
        resource_group = req_body.get('resource_group') or req.params.get('resource_group')
        location = req_body.get('location') or req.params.get('location')
        model_type = req_body.get('model_type') or req.params.get('model_type')
        storage_account_name = req_body.get('storage_account_name') or req.params.get('storage_account_name')
        search_service_name = req_body.get('search_service_name') or req.params.get('search_service_name')
        index_size = req_body.get('index_size') or req.params.get('index_size') or 'medium'
        enable_semantic_search = req_body.get('enable_semantic_search', True)
        RECIPIENT_EMAILS = req_body.get('recipient_emails') or req.params.get('recipient_emails')
        hook_url = req_body.get('hook_url') or req.params.get('hook_url') or ''
        
        ### Parameter checking to handle errors 
        if not deployment_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'deployment_name' parameter"}),
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
        if not model_type:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'model_type' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if model_type not in SUPPORTED_MODELS:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Unsupported model type '{model_type}'. Supported models: {list(SUPPORTED_MODELS.keys())}"
                }),
                status_code=400,
                mimetype="application/json"
            )
        if not storage_account_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'storage_account_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not search_service_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'search_service_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if index_size not in VECTOR_INDEX_CONFIGS:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Invalid index_size '{index_size}'. Supported sizes: {list(VECTOR_INDEX_CONFIGS.keys())}"
                }),
                status_code=400,
                mimetype="application/json"
            )
        if not RECIPIENT_EMAILS:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'recipient_emails' parameter"}),
                status_code=400,
                mimetype="application/json"
            )

        # App constants
        storage_account_base = deployment_name

        # Initial status update
        hook_response = await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "init",
                    "deployment_name": deployment_name,
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
                    "deployment_name": deployment_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "authenticating",
                        "message": "Authenticating with Azure"
                    }
                }
            )
            
            # Validate environment variables
            required_vars = ['AZURE_APP_CLIENT_ID', 'AZURE_APP_CLIENT_SECRET', 
                            'AZURE_APP_TENANT_ID', 'AZURE_SUBSCRIPTION_ID']
            missing = [var for var in required_vars if not os.environ.get(var)]
            if missing:
                raise Exception(f"Missing environment variables: {', '.join(missing)}")

            credentials = ClientSecretCredential(
                client_id=os.environ['AZURE_APP_CLIENT_ID'],
                client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
                tenant_id=os.environ['AZURE_APP_TENANT_ID']
            )

            # Start background deployment
            asyncio.create_task(
                deploy_llm_background(
                    credentials,
                    deployment_name, resource_group, location, model_type,
                    storage_account_name, search_service_name, index_size,
                    enable_semantic_search, RECIPIENT_EMAILS, hook_url
                )
            )

            #✅background-task started, hook will be notified during
            return func.HttpResponse(
                json.dumps({
                    "message": "LLM deployment started",
                    "status_url": status_url,
                    "deployment_name": deployment_name,
                    "model_type": model_type
                }),
                status_code=202,
                mimetype="application/json"
            )

        except Exception as ex:
            logging.exception("Authentication error:")
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
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


async def deploy_llm_background(
    credentials,
    deployment_name, resource_group, location, model_type,
    storage_account_name, search_service_name, index_size,
    enable_semantic_search, RECIPIENT_EMAILS, hook_url
):
    try:
        # Initial status update
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "starting_deployment", 
                    "message": "Beginning LLM deployment process",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        
        # Initialize Azure clients
        cognitive_client = CognitiveServicesManagementClient(credentials, subscription_id)
        storage_client = StorageManagementClient(credentials, subscription_id)
        search_mgmt_client = SearchManagementClient(credentials, subscription_id)

        # Get model configurations - BOTH MAIN MODEL AND EMBEDDING MODEL
        main_model_config = SUPPORTED_MODELS[model_type]
        embedding_model_config = SUPPORTED_MODELS["text-embedding-ada-002"]
        index_config = VECTOR_INDEX_CONFIGS[index_size]

        # Create storage account
        storage_account_name = f"{storage_account_name}{int(time.time()) % 10000}"
        try:
            storage_config = await run_azure_operation(
                create_storage_account,
                storage_client,
                resource_group,
                storage_account_name,
                location
            )
            global AZURE_STORAGE_ACCOUNT_KEY
            AZURE_STORAGE_ACCOUNT_KEY = storage_config["AZURE_STORAGE_KEY"]
            AZURE_STORAGE_URL = storage_config["AZURE_STORAGE_URL"]
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "storage_created",
                        "message": "Storage account created successfully",
                        "storage_account_name": storage_account_name
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create storage account: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "storage_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create Cognitive Services account
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "creating_cognitive_services",
                    "message": f"Creating Azure OpenAI service for {model_type}"
                }
            }
        )

        try:
            cognitive_account = await run_azure_operation(
                create_cognitive_services_account,
                cognitive_client, resource_group, deployment_name, location, main_model_config
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "cognitive_services_created",
                        "message": "Azure OpenAI service created successfully",
                        "endpoint": cognitive_account.properties.endpoint
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create Cognitive Services account: {str(e)}"
            print_error(error_msg)
            await cleanup_llm_resources_on_failure(
                cognitive_client, storage_client, search_mgmt_client,
                resource_group, deployment_name, storage_account_name, search_service_name
            )
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "cognitive_services_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create Search Service
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "creating_search_service",
                    "message": "Creating Azure AI Search service"
                }
            }
        )

        try:
            search_endpoint, admin_key = await run_azure_operation(
                create_search_service,
                search_mgmt_client, resource_group, search_service_name, location
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "search_service_created",
                        "message": "Azure AI Search service created",
                        "search_endpoint": search_endpoint
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create search service: {str(e)}"
            print_error(error_msg)
            await cleanup_llm_resources_on_failure(
                cognitive_client, storage_client, search_mgmt_client,
                resource_group, deployment_name, storage_account_name, search_service_name
            )
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "search_service_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create Vector Index
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "creating_vector_index",
                    "message": "Creating vector search index"
                }
            }
        )

        try:
            index_name = await run_azure_operation(
                create_vector_index,
                credentials, search_endpoint, deployment_name, index_config, enable_semantic_search
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "vector_index_created",
                        "message": "Vector search index created successfully",
                        "index_name": index_name
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create vector index: {str(e)}"
            print_error(error_msg)
            await cleanup_llm_resources_on_failure(
                cognitive_client, storage_client, search_mgmt_client,
                resource_group, deployment_name, storage_account_name, search_service_name
            )
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "vector_index_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # DEPLOY BOTH MODELS: Main model + Embedding model
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "deploying_models",
                    "message": f"Deploying {model_type} and text-embedding-ada-002 models"
                }
            }
        )

        try:
            # Deploy main model
            main_deployment = await run_azure_operation(
                deploy_model,
                cognitive_client, resource_group, deployment_name, main_model_config
            )
            
            # Deploy embedding model
            embedding_deployment = await run_azure_operation(
                deploy_model,
                cognitive_client, resource_group, deployment_name, embedding_model_config
            )
            
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "provisioning",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "models_deployed",
                        "message": f"Both {model_type} and text-embedding-ada-002 models deployed successfully"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to deploy models: {str(e)}"
            print_error(error_msg)
            await cleanup_llm_resources_on_failure(
                cognitive_client, storage_client, search_mgmt_client,
                resource_group, deployment_name, storage_account_name, search_service_name
            )
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "failed",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "model_deployment_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Get deployment endpoints and keys
        try:
            # Get Cognitive Services keys
            cognitive_keys = await run_azure_operation(
                cognitive_client.accounts.list_keys,
                resource_group, deployment_name
            )
            cognitive_endpoint = cognitive_account.properties.endpoint
            
            # Prepare deployment information
            deployment_info = {
                "cognitive_services": {
                    "endpoint": cognitive_endpoint,
                    "key": cognitive_keys.key1,
                    "deployments": {
                        "main_model": main_model_config["deployment_name"],
                        "embedding_model": embedding_model_config["deployment_name"]
                    }
                },
                "azure_ai_search": {
                    "endpoint": search_endpoint,
                    "admin_key": admin_key,
                    "index_name": index_name
                },
                "storage": {
                    "account_name": storage_account_name,
                    "connection_string": storage_config["connection_string"]
                }
            }

            # Cleanup temporary storage
            try:
                await cleanup_temp_storage(
                    resource_group, storage_client, storage_account_name
                )
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "deployment_name": deployment_name,
                        "status": "provisioning",
                        "resource_group": resource_group,
                        "location": location,
                        "model_type": model_type,
                        "details": {
                            "step": "cleanup_complete",
                            "message": "Temporary resources cleaned up"
                        }
                    }
                )
            except Exception as e:
                error_msg = f"Cleanup failed (non-critical): {str(e)}"
                print_warn(error_msg)
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "deployment_name": deployment_name,
                        "status": "provisioning",
                        "resource_group": resource_group,
                        "location": location,
                        "model_type": model_type,
                        "details": {
                            "step": "cleanup_warning",
                            "warning": error_msg
                        }
                    }
                )

            # Send completion email
            try:
                smtp_host = os.environ.get('SMTP_HOST')
                smtp_port = int(os.environ.get('SMTP_PORT', 587))
                smtp_user = os.environ.get('SMTP_USER')
                smtp_password = os.environ.get('SMTP_PASS')
                sender_email = os.environ.get('SENDER_EMAIL')
                recipient_emails = [e.strip() for e in RECIPIENT_EMAILS.split(',')]
                
                html_content = html_email.HTMLEmail(
                    logo_url="https://i.postimg.cc/vBpLm0mF/llm-deployment.png",
                    cognitive_endpoint=cognitive_endpoint,
                    search_endpoint=search_endpoint,
                    created_at=datetime.utcnow().isoformat(),
                    link1=f"{cognitive_endpoint}",
                    link2=f"{search_endpoint}",
                    link3=f"https://portal.azure.com",
                    new_deployment_url=f"https://yourapp.com/deployllm",
                    dash_url="https://yourapp.com"
                )

                await html_email_send.send_html_email_smtp(
                        smtp_host=smtp_host,
                        smtp_port=smtp_port,
                        smtp_user=smtp_user,
                        smtp_password=smtp_password,
                        sender_email=sender_email,
                        recipient_emails=recipient_emails,
                        subject=f"LLM Deployment '{deployment_name}' Completed",
                        html_content=html_content,
                        use_tls=True
                    )
                
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "deployment_name": deployment_name,
                        "status": "provisioning",
                        "resource_group": resource_group,
                        "location": location,
                        "model_type": model_type,
                        "details": {
                            "step": "email_sent",
                            "message": "Completion email sent"
                        }
                    }
                )
            except Exception as e:
                error_msg = f"Failed to send email: {str(e)}"
                print_warn(error_msg)
                await post_status_update(
                    hook_url=hook_url,
                    status_data={
                        "deployment_name": deployment_name,
                        "status": "provisioning",
                        "resource_group": resource_group,
                        "location": location,
                        "model_type": model_type,
                        "details": {
                            "step": "email_failed",
                            "warning": error_msg
                        }
                    }
                )

            # Final success update
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "completed",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "completed",
                        "message": "LLM deployment successful",
                        "cognitive_endpoint": cognitive_endpoint,
                        "search_endpoint": search_endpoint,
                        "deployments": {
                            "main_model": main_model_config["deployment_name"],
                            "embedding_model": embedding_model_config["deployment_name"]
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

            print_success(f"LLM deployment completed successfully! Models: {model_type} + text-embedding-ada-002")
            
        except Exception as e:
            error_msg = f"Failed to finalize deployment: {str(e)}"
            print_error(error_msg)
            await post_status_update(
                hook_url=hook_url,
                status_data={
                    "deployment_name": deployment_name,
                    "status": "completed_with_warnings",
                    "resource_group": resource_group,
                    "location": location,
                    "model_type": model_type,
                    "details": {
                        "step": "finalization_warning",
                        "warning": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

    except Exception as e:
        # Top-level error handler for background task
        error_msg = f"Unhandled exception in background task: {str(e)}"
        print_error(error_msg)
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "failed",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "background_task_failed",
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
        await cleanup_llm_resources_on_failure(
            cognitive_client, storage_client, search_mgmt_client,
            resource_group, deployment_name, storage_account_name, search_service_name
        )


# ====================== HELPER FUNCTIONS ======================

def create_storage_account(storage_client, resource_group_name, storage_name, location):
    """Create or get storage account"""
    print_info(f"Creating storage account '{storage_name}'...")
    try:
        try:
            storage_client.storage_accounts.get_properties(resource_group_name, storage_name)
            print_info(f"Storage account '{storage_name}' already exists.")
        except:
            poller = storage_client.storage_accounts.begin_create(
                resource_group_name,
                storage_name,
                {
                    "sku": {"name": "Standard_LRS"},
                    "kind": "StorageV2",
                    "location": location,
                    "enable_https_traffic_only": True
                }
            )
            poller.result()
            print_success(f"Storage account '{storage_name}' created.")

        keys = storage_client.storage_accounts.list_keys(resource_group_name, storage_name)
        storage_key = keys.keys[0].value
        storage_url = f"https://{storage_name}.blob.core.windows.net"

        return {
            "AZURE_STORAGE_URL": storage_url,
            "AZURE_STORAGE_NAME": storage_name,
            "AZURE_STORAGE_KEY": storage_key,
            "connection_string": f"DefaultEndpointsProtocol=https;AccountName={storage_name};AccountKey={storage_key};EndpointSuffix=core.windows.net"
        }
    except Exception as e:
        print_error(f"Failed to create storage account: {e}")
        raise

def create_cognitive_services_account(cognitive_client, resource_group, account_name, location, model_config):
    """Create Azure Cognitive Services account"""
    print_info(f"Creating Cognitive Services account '{account_name}'...")
    
    try:
        cognitive_client.accounts.get(resource_group, account_name)
        print_info(f"Cognitive Services account '{account_name}' already exists.")
    except ResourceNotFoundError:
        sku = Sku(name=model_config["sku"])
        properties = CognitiveServicesAccountProperties()
        
        if model_config["kind"] in ["OpenAI", "OAI"]:
            properties = CognitiveServicesAccountProperties(
                custom_sub_domain_name=account_name,
                api_properties=ApiProperties(
                    event_hub_connection_string=""
                )
            )

        account = CognitiveServicesAccount(
            location=location,
            sku=sku,
            kind=model_config["kind"],
            properties=properties
        )

        poller = cognitive_client.accounts.begin_create(
            resource_group,
            account_name,
            account
        )
        account = poller.result()
        print_success(f"Cognitive Services account '{account_name}' created.")
    
    return cognitive_client.accounts.get(resource_group, account_name)

def create_search_service(search_mgmt_client, resource_group, search_service_name, location):
    """Create Azure AI Search service"""
    print_info(f"Creating search service '{search_service_name}'...")
    
    try:
        search_mgmt_client.services.get(resource_group, search_service_name)
        print_info(f"Search service '{search_service_name}' already exists.")
    except ResourceNotFoundError:
        search_service = SearchService(
            location=location,
            sku=SearchSku(name="standard"),
            replica_count=1,
            partition_count=1
        )
        
        poller = search_mgmt_client.services.begin_create_or_update(
            resource_group,
            search_service_name,
            search_service
        )
        search_service = poller.result()
        print_success(f"Search service '{search_service_name}' created.")

    # Get admin keys
    admin_keys = search_mgmt_client.admin_keys.get(resource_group, search_service_name)
    search_endpoint = f"https://{search_service_name}.search.windows.net"
    
    return search_endpoint, admin_keys.primary_key

def create_vector_index(credentials, search_endpoint, deployment_name, index_config, enable_semantic_search):
    """Create vector search index"""
    print_info(f"Creating vector index for '{deployment_name}'...")
    
    search_client = SearchIndexClient(
        endpoint=search_endpoint,
        credential=credentials
    )

    index_name = f"{deployment_name}-vector-index"
    
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="content", type=SearchFieldDataType.String, searchable=True),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="content_vector", 
                   type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                   searchable=True,
                   vector_search_dimensions=index_config["vector_dimension"],
                   vector_search_profile_name="myHnswProfile"),
        SimpleField(name="metadata", type=SearchFieldDataType.String),
        SimpleField(name="timestamp", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True)
    ]

    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw",
                parameters=index_config["hnsw_parameters"]
            )
        ]
    )

    semantic_config = None
    if enable_semantic_search:
        semantic_config = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name="my-semantic-config",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="content"),
                        prioritized_content_fields=[SemanticField(field_name="content")],
                        prioritized_keywords_fields=[SemanticField(field_name="category")]
                    )
                )
            ]
        )

    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_config
    )

    try:
        search_client.create_index(index)
        print_success(f"Search index '{index_name}' created.")
    except Exception as e:
        print_warn(f"Index may already exist: {str(e)}")
        search_client.create_or_update_index(index)
        print_success(f"Search index '{index_name}' updated.")

    return index_name

def deploy_model(cognitive_client, resource_group, account_name, model_config):
    """Deploy the specific model to Azure OpenAI"""
    print_info(f"Deploying model '{model_config['deployment_name']}'...")
    
    try:
        # Check if deployment already exists
        try:
            deployment = cognitive_client.deployments.get(
                resource_group, 
                account_name, 
                model_config['deployment_name']
            )
            print_info(f"Model deployment '{model_config['deployment_name']}' already exists.")
            return deployment
        except ResourceNotFoundError:
            # Model deployment doesn't exist, create it
            deployment_properties = DeploymentProperties(
                model=DeploymentModel(
                    format="OpenAI",
                    name=model_config['model_name'],
                    version="1"
                ),
                scale_settings=DeploymentScaleSettings(
                    scale_type="Standard"
                )
            )
            
            deployment = Deployment(properties=deployment_properties)
            
            # Begin the deployment operation
            poller = cognitive_client.deployments.begin_create_or_update(
                resource_group,
                account_name,
                model_config['deployment_name'],
                deployment
            )
            
            # Wait for deployment to complete
            deployment_result = poller.result()
            
            print_success(f"Model '{model_config['deployment_name']}' deployed successfully.")
            return deployment_result
            
    except Exception as e:
        print_error(f"Failed to deploy model '{model_config['deployment_name']}': {str(e)}")
        raise

async def cleanup_temp_storage(resource_group, storage_client, storage_account_name):
    """Cleanup temporary storage on success"""
    try:
        storage_client.storage_accounts.delete(resource_group, storage_account_name)
    except Exception as e:
        print_warn(f"Temp storage cleanup failed: {str(e)}")

async def cleanup_llm_resources_on_failure(
    cognitive_client, storage_client, search_mgmt_client, resource_group, 
    deployment_name, storage_account_name, search_service_name
):
    """Cleanup all resources on failure"""
    print_warn("Cleaning up LLM deployment resources due to failure...")
    
    # Delete Cognitive Services account
    try:
        cognitive_client.accounts.begin_delete(resource_group, deployment_name).wait()
    except Exception:
        pass
    
    # Delete storage account
    try:
        storage_client.storage_accounts.delete(resource_group, storage_account_name)
    except Exception:
        pass
    
    # Delete search service
    try:
        search_mgmt_client.services.begin_delete(resource_group, search_service_name).wait()
    except Exception:
        pass
    
    print_success("LLM resources cleanup completed.")

# ====================== STATUS UPDATE FUNCTION ======================
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
            await asyncio.sleep(retry_delay * attempt)  # Exponential backoff
        else:
            print_error(f"Status update failed after {max_retries} attempts: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_url": ""
            }
    
    return {"success": False, "error": "Unknown error", "status_url": ""}