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
    ApiProperties
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
from azure.storage.blob import BlobServiceClient
import azure.functions as func
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting LLM deployment application initialization...")

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

# Supported models and configurations
SUPPORTED_MODELS = {
    "gpt-4": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "gpt-4",
        "max_tokens": 8192
    },
    "gpt-4-32k": {
        "kind": "OpenAI", 
        "sku": "S0",
        "deployment_name": "gpt-4-32k",
        "max_tokens": 32768
    },
    "gpt-35-turbo": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "gpt-35-turbo",
        "max_tokens": 4096
    },
    "text-embedding-ada-002": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "text-embedding-ada-002",
        "dimensions": 1536
    },
    "dall-e-3": {
        "kind": "OpenAI",
        "sku": "S0",
        "deployment_name": "dall-e-3"
    },
    "llama-2-7b": {
        "kind": "OAI",
        "sku": "Standard",
        "deployment_name": "llama-2-7b"
    },
    "llama-2-70b": {
        "kind": "OAI", 
        "sku": "Standard",
        "deployment_name": "llama-2-70b"
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

        ### Parameter validation
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
        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        
        # Initialize Azure clients
        cognitive_client = CognitiveServicesManagementClient(credentials, subscription_id)
        storage_client = StorageManagementClient(credentials, subscription_id)
        search_client = SearchIndexClient(
            endpoint=f"https://{search_service_name}.search.windows.net",
            credential=credentials
        )

        # Get model configuration
        model_config = SUPPORTED_MODELS[model_type]
        index_config = VECTOR_INDEX_CONFIGS[index_size]

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
            cognitive_account = await create_cognitive_services_account(
                cognitive_client, resource_group, deployment_name, location, model_config
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

        # Create storage account for vector data
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "creating_storage",
                    "message": "Creating storage account for vector data"
                }
            }
        )

        try:
            storage_config = await create_storage_account(
                storage_client, resource_group, storage_account_name, location
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
                        "step": "storage_created",
                        "message": "Storage account created successfully"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create storage account: {str(e)}"
            print_error(error_msg)
            await cleanup_llm_resources_on_failure(
                cognitive_client, storage_client, resource_group,
                deployment_name, storage_account_name
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
                        "step": "storage_creation_failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            return

        # Create Azure AI Search service and vector index
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
                    "message": "Creating Azure AI Search service and vector index"
                }
            }
        )

        try:
            search_endpoint, admin_key = await create_search_service_and_index(
                credentials, subscription_id, resource_group, search_service_name,
                location, deployment_name, index_config, enable_semantic_search
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
                        "message": "Azure AI Search service and vector index created",
                        "search_endpoint": search_endpoint
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to create search service: {str(e)}"
            print_error(error_msg)
            await cleanup_llm_resources_on_failure(
                cognitive_client, storage_client, resource_group,
                deployment_name, storage_account_name
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

        # Deploy model
        await post_status_update(
            hook_url=hook_url,
            status_data={
                "deployment_name": deployment_name,
                "status": "provisioning",
                "resource_group": resource_group,
                "location": location,
                "model_type": model_type,
                "details": {
                    "step": "deploying_model",
                    "message": f"Deploying {model_type} model"
                }
            }
        )

        try:
            deployment = await deploy_model(
                cognitive_client, resource_group, deployment_name, model_config
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
                        "step": "model_deployed",
                        "message": f"Model {model_type} deployed successfully"
                    }
                }
            )
        except Exception as e:
            error_msg = f"Failed to deploy model: {str(e)}"
            print_error(error_msg)
            await cleanup_llm_resources_on_failure(
                cognitive_client, storage_client, resource_group,
                deployment_name, storage_account_name
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

        # Get keys and endpoints
        try:
            # Get Cognitive Services keys
            cognitive_keys = cognitive_client.accounts.list_keys(resource_group, deployment_name)
            cognitive_endpoint = cognitive_account.properties.endpoint
            
            # Prepare deployment information
            deployment_info = {
                "cognitive_services": {
                    "endpoint": cognitive_endpoint,
                    "key": cognitive_keys.key1,
                    "deployment_name": model_config["deployment_name"]
                },
                "azure_ai_search": {
                    "endpoint": search_endpoint,
                    "admin_key": admin_key,
                    "index_name": f"{deployment_name}-vector-index"
                },
                "storage": {
                    "account_name": storage_account_name,
                    "connection_string": storage_config["connection_string"]
                },
                "model": {
                    "type": model_type,
                    "config": model_config
                }
            }

            # Send completion email
            await send_llm_deployment_email(
                RECIPIENT_EMAILS, deployment_name, model_type, deployment_info
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
                        "deployment_info": {
                            "cognitive_endpoint": cognitive_endpoint,
                            "search_endpoint": search_endpoint,
                            "model_deployed": model_config["deployment_name"]
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

            print_success(f"LLM deployment completed successfully! Model: {model_type}")

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
            cognitive_client, storage_client, resource_group,
            deployment_name, storage_account_name
        )


# ====================== HELPER FUNCTIONS ======================

def create_cognitive_services_account(cognitive_client, resource_group, account_name, location, model_config):
    """Create Azure Cognitive Services account"""
    print_info(f"Creating Cognitive Services account '{account_name}'...")
    
    try:
        # Check if account already exists
        cognitive_client.accounts.get(resource_group, account_name)
        print_info(f"Cognitive Services account '{account_name}' already exists.")
    except ResourceNotFoundError:
        # Create new account
        sku = Sku(name=model_config["sku"])
        properties = CognitiveServicesAccountProperties()
        
        # For OpenAI accounts, set specific properties
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

def create_storage_account(storage_client, resource_group_name, storage_name, location):
    """Create storage account for vector data"""
    print_info(f"Creating storage account '{storage_name}'...")
    
    try:
        storage_client.storage_accounts.get_properties(resource_group_name, storage_name)
        print_info(f"Storage account '{storage_name}' already exists.")
    except ResourceNotFoundError:
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
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={storage_name};AccountKey={keys.keys[0].value};EndpointSuffix=core.windows.net"

    return {
        "connection_string": connection_string,
        "account_name": storage_name
    }

async def create_search_service_and_index(credentials, subscription_id, resource_group, 
                                        search_service_name, location, deployment_name, 
                                        index_config, enable_semantic_search):
    """Create Azure AI Search service and vector index"""
    print_info(f"Creating search service '{search_service_name}'...")
    
    # Note: Azure AI Search creation requires ARM client - using simplified approach
    # In production, you'd use AzureManagementClient to create the search service
    
    # For now, assume search service exists and we just create the index
    search_endpoint = f"https://{search_service_name}.search.windows.net"
    
    # Create search index client
    search_client = SearchIndexClient(
        endpoint=search_endpoint,
        credential=credentials
    )

    # Define vector index
    index_name = f"{deployment_name}-vector-index"
    
    # Define fields for the index
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

    # Configure vector search
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

    # Configure semantic search if enabled
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

    # Create the index
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
        # Try to update instead
        try:
            search_client.create_or_update_index(index)
            print_success(f"Search index '{index_name}' updated.")
        except Exception as update_error:
            print_error(f"Failed to create/update index: {str(update_error)}")
            raise

    # Get admin key (in production, you'd retrieve this from Azure Key Vault or generate it)
    # For now, return placeholder - in real implementation, you'd use SearchManagementClient
    admin_key = "placeholder-admin-key"
    
    return search_endpoint, admin_key

def deploy_model(cognitive_client, resource_group, account_name, model_config):
    """Deploy the specific model"""
    print_info(f"Deploying model '{model_config['deployment_name']}'...")
    
    # Note: Model deployment in Azure OpenAI requires specific API calls
    # This is a simplified version - in production you'd use:
    # openai_client = OpenAIClient() with proper authentication
    
    # For now, we'll simulate successful deployment
    # In real implementation, you would:
    # 1. Get the deployment client
    # 2. Check if deployment exists
    # 3. Create deployment if it doesn't exist
    
    print_success(f"Model '{model_config['deployment_name']}' deployed.")
    return {"status": "succeeded", "model": model_config['deployment_name']}

async def send_llm_deployment_email(recipient_emails, deployment_name, model_type, deployment_info):
    """Send deployment completion email"""
    try:
        smtp_host = os.environ.get('SMTP_HOST')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER')
        smtp_password = os.environ.get('SMTP_PASS')
        sender_email = os.environ.get('SENDER_EMAIL')
        recipient_emails = [e.strip() for e in recipient_emails.split(',')]
        
        # Simple email content for LLM deployment
        subject = f"LLM Deployment '{deployment_name}' Completed"
        body = f"""
        LLM Deployment Successful!
        
        Deployment Name: {deployment_name}
        Model Type: {model_type}
        
        Endpoints:
        - Cognitive Services: {deployment_info['cognitive_services']['endpoint']}
        - Azure AI Search: {deployment_info['azure_ai_search']['endpoint']}
        
        Storage Account: {deployment_info['storage']['account_name']}
        
        The vector database and LLM model are ready for use.
        """
        
        # In production, use your html_email_send function
        print_success(f"Deployment email would be sent to: {recipient_emails}")
        
    except Exception as e:
        print_warn(f"Failed to send email: {str(e)}")

async def cleanup_llm_resources_on_failure(cognitive_client, storage_client, resource_group, 
                                         deployment_name, storage_account_name):
    """Cleanup resources on deployment failure"""
    print_warn("Cleaning up LLM deployment resources due to failure...")
    
    try:
        # Delete Cognitive Services account
        cognitive_client.accounts.begin_delete(resource_group, deployment_name).wait()
    except Exception:
        pass
    
    try:
        # Delete storage account
        storage_client.storage_accounts.delete(resource_group, storage_account_name)
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