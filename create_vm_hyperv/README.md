# Azure Windows VM Provisioning Script - Step by Step Explanation

This document explains the Python Azure VM provisioning script in detail.

---

## 1. Imports and Initialization

The script imports standard Python libraries (`asyncio`, `json`, `os`, `sys`, `time`, `re`, etc.) for general operations and networking, as well as Azure SDK modules for managing resources:

- `azure.identity.ClientSecretCredential`: Authenticate with Azure using service principal.
- `azure.mgmt.compute`, `network`, `storage`, `dns`: Manage Azure VMs, network resources, storage accounts, and DNS.
- `azure.storage.blob`: Upload setup scripts and generate SAS URLs.
- `azure.functions`: Create an HTTP-triggered Azure Function.

Logging and console colors are configured for readable output.

```python
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")
```

2. Configuration Variables
   Windows VM Image: Uses a Windows 10 22H2 Pro image.
   Ports to Open: Ports 22, 80, 443, 3389, etc., are opened for the VM.
   Console Colors: Defined with bcolors class for logging purposes.
   Disk, username/password, email, pin: Extracted from HTTP request parameters.

3. HTTP Trigger Function: main

The main function handles HTTP requests to create a VM:
Extract parameters from JSON body or URL query.
Validate required parameters like vm_name, resource_group, domain, location, vm_size.
Check VM size compatibility with a predefined list of Hyper-V compatible VM sizes.
Post initial status update to webhook if provided.
Authenticate to Azure using service principal credentials.
Launch background provisioning task using asyncio.create_task().

Returns 202 Accepted if provisioning starts successfully. 4. Background Provisioning: provision_vm_background

This asynchronous function performs the actual VM provisioning:
a. Initialize Azure clients
Compute, Storage, Network, DNS clients.

b. Storage Account Creation
Generates a unique storage account name.
Creates the account and stores keys/URLs for blob operations.
Uploads PowerShell setup script and generates SAS URL.

c. Network Setup
Virtual Network and Subnet: Creates a VNet and subnet.
Public IP: Allocates a dynamic public IP.
Network Security Group (NSG):
Creates or retrieves NSG.
Adds inbound rules for all required ports with dynamic priorities.
Network Interface (NIC): Associates subnet, public IP, and NSG.

d. Virtual Machine Creation
Creates VM with:
Specified size and OS disk.
Windows credentials.
Fresh Windows image reference.
Trusted Launch security profile.
NIC association.

    Waits for VM initialization.

e. Public IP Verification
Checks that NIC has a public IP.
Posts status update with IP info.

f. DNS Configuration
Creates DNS zone if missing.
Checks NS delegation.
Creates A records for services like pin, drop, web.

g. Custom Script Extension
Installs the uploaded PowerShell script on the VM.
Ensures VM is configured automatically with required software/services.

h. Cleanup Temporary Storage
Deletes temporary setup blobs and container.
Deletes storage account used for setup script.

i. Completion Email
Sends an HTML email to recipients with VM info, RDP link, and service URLs.

j. Final Status Update
Marks VM provisioning as completed.
Provides public IP and service URLs in webhook update.

5. Error Handling & Cleanup
   The script ensures robust error handling:
   cleanup_resources_on_failure deletes VM, NIC, NSG, VNet, storage, and DNS records if provisioning fails.
   cleanup_temp_storage removes temporary storage on success.
   Each step posts status updates to the webhook with error or warning messages.

6. Helper Functions
   Storage Operations
   create_storage_account: Creates storage account if missing.
   ensure_container_exists: Ensures a blob container exists.
   upload_blob_and_generate_sas: Uploads data and returns a SAS URL.

VM Size Validation
get_compatible_vm_sizes: Returns Hyper-V compatible VM sizes.
check_vm_size_compatibility: Validates user-selected VM size.

DNS Utilities
check_ns_delegation: Verifies correct NS delegation.
check_ns_delegation_with_retries: Retries delegation check with exponential backoff.

Status Updates
post_status_update: Sends status updates to webhook with retries.

7. Summary

This script automates:
VM provisioning (Windows 10) on Azure.
Network, public IP, and NSG configuration.
Storage account creation and setup script upload.
DNS record management.
Custom script execution on VM.
Email notification to recipients.
Cleanup of resources on error or after setup.

It provides a robust, asynchronous, and fully automated Azure Windows VM provisioning workflow with detailed logging and webhook status reporting.

SMTP Email Sending (html_email_send.py)
The VM provisioning script sends completion emails to recipients using SMTP:

1.  Email Configuration
    Retrieves SMTP settings from environment variables:
    SMTP_HOST, SMTP_PORT
    SMTP_USER, SMTP_PASS
    SENDER_EMAIL

    Recipient emails are parsed from the RECIPIENT_EMAILS parameter.

2.  Email Content Generator(html_email.py)
    Uses html_email.HTMLEmail to generate HTML content with:
    VM public IP
    Links to RDP generator
    Service URLs like pin/drop
    VM username/password

3.  Sending Email

```python
await html_email_send.send_html_email_smtp(
    smtp_host=smtp_host,
    smtp_port=smtp_port,
    smtp_user=smtp_user,
    smtp_password=smtp_password,
    sender_email=sender_email,
    recipient_emails=recipient_emails,
    subject=f"'{vm_name}' VM created",
    html_content=html_content,
    use_tls=True
)
```

    Uses aiohttp and asyncio to ensure asynchronous sending.
    Errors are caught and reported to the webhook but do not block overall provisioning.

4. Status Updates
   Before sending: step = "sending_email"
   On success: step = "email_sent"
   On failure: step = "email_failed" with warning message.

Summary:
The SMTP email section ensures that all VM provisioning results are reported to users with relevant links and credentials while keeping the process fully automated and asynchronous.

# Hyper-V Setup Script Explanation

This PowerShell setup script performs a comprehensive setup and configuration on a Windows machine, primarily to prepare it for Hyper-V installation and system/user debloating. Here is a breakdown of its functionality:

## 1. Admin Privileges Check

- Checks if the script is running with Administrator privileges.
- If not, it relaunches itself as Administrator using `Start-Process` with elevated permissions.

## 2. Webhook Notifications

- Defines a function `Notify-Webhook` that can send JSON-formatted status updates to a given webhook URL.
- Each payload includes:
  - `vm_name`: The computer name
  - `status`: e.g., "provisioning", "info", "failed"
  - `timestamp`: UTC time
  - `details`: Step name and message
- Used throughout the script to report progress or failures.

## 3. Logging

- Creates a log directory at `C:\Program Files\Logs`.
- Logs key events, including script start, helper script creation, scheduled task registration, and completion.

## 4. Registry Helper Function

- `Set-RegistryValue` safely sets registry keys and values.
- Creates the path if it does not exist.
- Logs failures to the install log without stopping the script.

## 5. System Cleanup & Debloat (HKLM + SYSTEM)

- Modifies multiple registry keys to:
  - Disable OOBE (Out-of-Box Experience) prompts.
  - Disable Cortana and privacy popups.
  - Disable auto-updates for Windows Update and telemetry collection.
  - Configure network settings to treat networks as Private.
- Stops and disables unnecessary services like `WSearch`, `DiagTrack`, and `WerSvc`.
- Forces all current network profiles to Private to improve security.

## 6. User Cleanup & Debloat (HKCU)

- Iterates over all user profiles with `NTUSER.DAT`.
- Sets user-specific registry keys to disable:
  - Lock screen features
  - First-run experiences for OneDrive, Xbox, GameBar, Office
  - Windows Store auto-downloads
  - Push notifications
- Essentially minimizes bloatware and privacy-invading defaults.

## 7. Post-Reboot Helper Script

- Creates a helper script at `C:\ProgramData\PostHyperVSetup.ps1`.
- Tasks include:
  - Setting network profiles to Private
  - Disabling Network Discovery firewall rules
  - Stopping and disabling discovery-related services
  - Updating `NetworkList` registry categories
  - Creating Hyper-V Manager shortcut on the Public Desktop
  - Self-cleanup by unregistering its scheduled task and deleting itself
- The helper is scheduled to run at next startup as SYSTEM.

## 8. Scheduled Task

- Registers a scheduled task to run the helper script once at startup.
- Ensures post-reboot tasks are applied, like completing Hyper-V setup and enforcing network settings.

## 9. Hyper-V Installation

- Checks if Hyper-V is already enabled.
- If not enabled:
  - Notifies the webhook that Hyper-V is being installed.
  - Enables `Microsoft-Hyper-V-All` feature.
  - Schedules a reboot to finalize installation.
- If already enabled:
  - Notifies the webhook.
  - Immediately creates a Hyper-V Manager shortcut on the Public Desktop.

## 10. Completion

- Automatically allocating unused space on C:\
- Writes final log entry with the setup completion timestamp.
- Script is fully automated, combining system hardening, debloating, network configuration, and Hyper-V setup.

---

**Summary:**  
This script is designed for automated Windows provisioning. It prepares the machine by disabling telemetry and unnecessary services, applying user and system-level debloat, configuring network privacy, and installing/enabling Hyper-V with a post-reboot helper. All actions are logged and optionally reported to a webhook for monitoring purposes.
