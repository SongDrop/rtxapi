import os
import json
import logging
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing cloned_vm_list request...")

    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Required parameters
        gallery_resource_group = req_body.get("gallery_resource_group") or req.params.get("gallery_resource_group")
        gallery_name = req_body.get("gallery_name") or req.params.get("gallery_name")

        missing = []
        for param in ["gallery_resource_group", "gallery_name"]:
            if not locals()[param]:
                missing.append(param)
        if missing:
            return func.HttpResponse(
                json.dumps({"error": f"Missing parameters: {', '.join(missing)}"}),
                status_code=400,
                mimetype="application/json"
            )

        # Azure auth info from env vars
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_APP_CLIENT_ID")
        client_secret = os.getenv("AZURE_APP_CLIENT_SECRET")

        if not all([subscription_id, tenant_id, client_id, client_secret]):
            return func.HttpResponse(
                json.dumps({"error": "Azure environment variables for authentication not fully set"}),
                status_code=500,
                mimetype="application/json"
            )

        credentials = ClientSecretCredential(client_id=client_id, client_secret=client_secret, tenant_id=tenant_id)
        compute_client = ComputeManagementClient(credentials, subscription_id)

        # List all gallery images (image definitions) in the gallery
        image_definitions = list(compute_client.gallery_images.list_by_gallery(gallery_resource_group, gallery_name))

        result = []
        for image_def in image_definitions:
            # List all versions for this image definition
            versions = list(compute_client.gallery_image_versions.list_by_gallery_image(
                gallery_resource_group,
                gallery_name,
                image_def.name
            ))
            versions_info = [{"name": v.name, "location": v.location} for v in versions]

            result.append({
                "image_definition_name": image_def.name,
                "os_type": image_def.os_type.value if image_def.os_type else None,
                "publisher": image_def.publisher,
                "offer": image_def.offer,
                "sku": image_def.sku,
                "hyper_v_generation": image_def.hyper_v_generation,
                "security_type": image_def.security_profile.security_type if image_def.security_profile else None,
                "versions": versions_info
            })

        return func.HttpResponse(
            json.dumps({
                "gallery_resource_group": gallery_resource_group,
                "gallery_name": gallery_name,
                "image_definitions": result
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logger.exception("Unhandled error in cloned_vm_list:")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )