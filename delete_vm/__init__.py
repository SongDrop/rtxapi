import sys
from pathlib import Path

# Add .python_packages to Python path
python_packages_path = str(Path(__file__).parent.parent / ".python_packages" / "lib" / "site-packages")
if python_packages_path not in sys.path:
    sys.path.append(python_packages_path)
import json
import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
import random
import string
import subprocess
import shutil
import platform
import webbrowser
import dns.resolver
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkSecurityGroup, SecurityRule, NetworkInterface
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import (
    VirtualMachine, HardwareProfile, StorageProfile,
    OSProfile, NetworkProfile, NetworkInterfaceReference,
    VirtualMachineExtension, WindowsConfiguration,SecurityProfile
)
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import RecordSet
from azure.mgmt.storage import StorageManagementClient
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="delete_vm")
def delete_vm(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    method = req.method  # this will be 'GET', 'POST', etc.

    if method == "GET":
        return func.HttpResponse("Received a GET request", status_code=200)
    elif method == "POST":
        return func.HttpResponse("Received a POST request", status_code=200)
    else:
        return func.HttpResponse(f"Received a {method} request", status_code=200)
