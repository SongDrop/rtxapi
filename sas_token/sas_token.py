import os
import sys
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.storage.blob import generate_container_sas, ContainerSasPermissions
from datetime import datetime, timedelta
import pyperclip

load_dotenv()

def print_info(msg):
    print(f"[INFO] {msg}")

def print_success(msg):
    print(f"[SUCCESS] {msg}")

def print_error(msg):
    print(f"[ERROR] {msg}")

def prompt_input(prompt, default=None):
    if default:
        prompt_full = f"{prompt} [{default}]: "
    else:
        prompt_full = f"{prompt}: "
    value = input(prompt_full)
    if not value and default:
        return default
    return value

def main():
    resource_group = prompt_input("Enter the resource group name", "vhd")
    storage_account_name = prompt_input("Enter the storage account name","vhdvm")
    container_name = prompt_input("Enter the container name","vhdvm")
    
    # Authenticate
    try:
        credentials = ClientSecretCredential(
            client_id=os.environ['AZURE_APP_CLIENT_ID'],
            client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
            tenant_id=os.environ['AZURE_APP_TENANT_ID']
        )
    except KeyError as e:
        print_error(f"Missing environment variable: {e}")
        sys.exit(1)

    subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
    if not subscription_id:
        print_error("AZURE_SUBSCRIPTION_ID environment variable is not set.")
        sys.exit(1)

    resource_client = ResourceManagementClient(credentials, subscription_id)
    storage_client = StorageManagementClient(credentials, subscription_id)

    # Check if resource group exists
    try:
        rg = resource_client.resource_groups.get(resource_group)
        print_success(f"Resource group '{resource_group}' found.")
    except Exception as e:
        print_error(f"Resource group '{resource_group}' not found or inaccessible: {e}")
        sys.exit(1)

    # Get storage account keys
    try:
        keys = storage_client.storage_accounts.list_keys(resource_group, storage_account_name)
        storage_keys = {v.key_name: v.value for v in keys.keys}
        storage_key = storage_keys.get('key1') or list(storage_keys.values())[0]
        print_success(f"Retrieved storage account key for '{storage_account_name}'.")
    except Exception as e:
        print_error(f"Failed to get storage account keys: {e}")
        sys.exit(1)

    # Generate SAS token for container with read and write permissions, valid for 1 day
    try:
        sas_token = generate_container_sas(
            account_name=storage_account_name,
            container_name=container_name,
            account_key=storage_key,
            permission=ContainerSasPermissions(read=True, write=True, create=True, list=True),
            expiry=datetime.utcnow() + timedelta(days=1)
        )
        print_success(f"SAS token generated for container '{container_name}':")
        print(sas_token)
        print_info(f"Full URL with SAS:")
        full_url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}?{sas_token}"
        print_info(full_url)
        # Copy to clipboard
        try:
            pyperclip.copy(full_url)
            print_success("The full URL with SAS token has been copied to your clipboard.")
        except Exception as e:
            print_error(f"Failed to copy to clipboard: {e}")
    except Exception as e:
        print_error(f"Failed to generate SAS token: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()