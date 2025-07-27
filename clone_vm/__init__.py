import os
import sys
import time
import json
import logging
import azure.functions as func
from packaging import version  # For semantic versioning
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute.models import (
    Snapshot,
    Gallery,
    GalleryImage,
    GalleryImageVersion,
    OperatingSystemStateTypes,
    SecurityProfile
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Console colors for logs
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

#####
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


def get_next_version(existing_versions):
    valid_versions = []
    for ver in existing_versions:
        try:
            ver_obj = version.parse(ver.name)
            if isinstance(ver_obj, version.Version):
                valid_versions.append(ver_obj)
        except Exception:
            pass
    if not valid_versions:
        return "1.0.0"
    latest_version = max(valid_versions)
    next_version = version.Version(f"{latest_version.major}.{latest_version.minor}.{latest_version.micro + 1}")
    return str(next_version)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing create_clone_vm request...")

    try:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Required parameters
        resource_group = req_body.get("resource_group") or req.params.get("resource_group")
        vm_name = req_body.get("vm_name") or req.params.get("vm_name")
        gallery_resource_group = req_body.get("gallery_resource_group") or req.params.get("gallery_resource_group")
        gallery_name = req_body.get("gallery_name") or req.params.get("gallery_name")
        image_definition_name = req_body.get("image_definition_name") or req.params.get("image_definition_name")
        image_offer = req_body.get("image_offer") or req.params.get("image_offer", "Windows-10")
        image_sku = req_body.get("image_sku") or req.params.get("image_sku")
        image_publisher = req_body.get("image_publisher") or req.params.get("image_publisher", "MicrosoftWindowsDesktop")

        # Validate required params
        missing = []
        for param in ["resource_group", "vm_name", "gallery_resource_group", "gallery_name", "image_definition_name", "image_sku"]:
            if not locals()[param]:
                missing.append(param)
        if missing:
            return func.HttpResponse(
                json.dumps({"error": f"Missing parameters: {', '.join(missing)}"}),
                status_code=400,
                mimetype="application/json"
            )

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
        resource_client = ResourceManagementClient(credentials, subscription_id)

        # Get VM to clone
        try:
            vm = compute_client.virtual_machines.get(resource_group, vm_name)
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": f"Failed to get VM '{vm_name}': {str(e)}"}),
                status_code=404,
                mimetype="application/json"
            )

        os_disk_id = vm.storage_profile.os_disk.managed_disk.id
        vm_location = vm.location

        # Create snapshot from OS disk
        snapshot_name = f"{vm_name}-osdisk-snapshot"
        snapshot_params = Snapshot(
            location=vm_location,
            creation_data={
                "create_option": "Copy",
                "source_resource_id": os_disk_id
            }
        )
        snapshot = compute_client.snapshots.begin_create_or_update(resource_group, snapshot_name, snapshot_params).result()

        # Create or get Compute Gallery
        try:
            gallery = compute_client.galleries.get(gallery_resource_group, gallery_name)
        except Exception:
            gallery_params = Gallery(location=vm_location)
            gallery = compute_client.galleries.begin_create_or_update(gallery_resource_group, gallery_name, gallery_params).result()

        # Create or get Gallery Image Definition
        try:
            image_def = compute_client.gallery_images.get(gallery_resource_group, gallery_name, image_definition_name)
        except Exception:
            image_def_params = GalleryImage(
                location=vm_location,
                os_type=vm.storage_profile.os_disk.os_type,
                os_state=OperatingSystemStateTypes.SPECIALIZED,
                publisher=image_publisher,
                offer=image_offer,
                sku=image_sku,
                hyper_v_generation="V2",
                security_profile=SecurityProfile(security_type="TrustedLaunch")
            )
            image_def = compute_client.gallery_images.begin_create_or_update(
                gallery_resource_group,
                gallery_name,
                image_definition_name,
                image_def_params
            ).result()

        # List existing image versions
        existing_versions = list(compute_client.gallery_image_versions.list_by_gallery_image(
            gallery_resource_group,
            gallery_name,
            image_definition_name
        ))

        next_version = get_next_version(existing_versions)

        # Create new Gallery Image Version from snapshot
        image_version_params = GalleryImageVersion(
            location=vm_location,
            publishing_profile={
                "target_regions": [{"name": vm_location}],
                "replica_count": 1,
                "storage_account_type": "Standard_LRS"
            },
            storage_profile={
                "os_disk": {
                    "os_type": vm.storage_profile.os_disk.os_type,
                    "snapshot": {"id": snapshot.id},
                    "os_state": OperatingSystemStateTypes.SPECIALIZED
                }
            }
        )

        image_version = compute_client.gallery_image_versions.begin_create_or_update(
            gallery_resource_group,
            gallery_name,
            image_definition_name,
            next_version,
            image_version_params
        ).result()

        # Construct Azure Portal URL
        portal_url = (
            f"https://portal.azure.com/#@{tenant_id}/resource/subscriptions/{subscription_id}"
            f"/resourceGroups/{gallery_resource_group}/providers/Microsoft.Compute/galleries/"
            f"{gallery_name}/images/{image_definition_name}/versions/{next_version}/overview"
        )

        print_success("Clonable VM Image creation completed!")
    
        print_success("-----------------------------------------------------")
        print_success("Azure Windows VM cloning completed successfully!")
        print_success("-----------------------------------------------------")
        print_success("Gallery Image Resource group:-----------------------------")
        print_success(gallery_resource_group)
        print_success("Gallery Name:-----------------------------")
        print_success(gallery_name)
        print_success("Gallery Image Definition Name:-----------------------------")
        print_success(image_definition_name)
        print_success("Gallery Image Version:-----------------------------")
        print_success(image_version_name)
        print_success("-----------------------------------------------------")


        result = {
            "message": "Clonable VM Image created successfully",
            "resource_group": resource_group,
            "gallery_resource_group": gallery_resource_group,
            "gallery_name": gallery_name,
            "image_definition_name": image_definition_name,
            "image_version": next_version,
            "portal_url": portal_url
        }

        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")

    except Exception as e:
        logger.exception("Error in create_clone_vm:")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")