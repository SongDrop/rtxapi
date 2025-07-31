import sys
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

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing create_vm request...')
 
    method = req.method
    if method == "GET":
        return func.HttpResponse("create_vm: Received a GET request", status_code=200)
    elif method == "POST":
        return func.HttpResponse("create_vm: Received a POST request", status_code=200)
    else:
        return func.HttpResponse(f"create_vm: Received a {method} request", status_code=200)
        return func.HttpResponse(f"Received a {method} request", status_code=200)
