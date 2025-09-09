# Azure Windows VM Provisioning Script - Step-by-Step Documentation

This document explains what the provided Python async script does, step by step.

---

## 1. Initialization and Setup

- Imports environment variables for Azure credentials, SMTP configuration, and other runtime settings.
- Sets global variables for storage account keys, snapshot URLs, and SAS tokens.
- Prepares helper functions for printing logs (`print_info`, `print_warn`, `print_error`, `print_success`) and posting status updates to a webhook.

---

## 2. VM Snapshot and Storage Preparation

1. **Stop VM for snapshot**:

   - Calls `stop_vm_to_snapshot` to deallocate the VM to safely take a snapshot of the OS disk.

2. **Create VM snapshot**:

   - Uses `compute_client.snapshots.begin_create_or_update` to copy the VM’s OS disk.

3. **Generate SAS URL for snapshot export**:

   - Uses `compute_client.disks.begin_export` to export the snapshot to a storage account.
   - SAS URL allows downloading the VHD file securely.

4. **Restart VM**:
   - After snapshot creation, the VM is restarted using `restart_vm`.

---

## 3. Storage Account and VHD Export Container

1. **Create storage account**:

   - Generates a unique name and calls `create_storage_account`.
   - Stores `AZURE_STORAGE_ACCOUNT_KEY` and `AZURE_STORAGE_URL` for further operations.

2. **Create VHD export container**:
   - Calls `create_vhd_export_container_and_sas` to create a container (`vhdusb`) for fixed-size bootable VHD files.
   - Generates a SAS token for uploading VHDs via AzCopy.

---

## 4. PowerShell Setup Script Generation

- Generates a setup script (`{vm_name}-setup.ps1`) with:
  - `SNAPSHOT_URL` for Hyper-V download.
  - `AZURE_SAS_TOKEN` for uploading VHDs.
  - `WEBHOOK_URL` for sending status updates.
- Uploads the script to a storage blob and generates a SAS URL for VM execution.

---

## 5. Network Infrastructure Setup

1. **Create virtual network (VNet) and subnet**.
2. **Create public IP** and associate it with the VM.
3. **Create or get Network Security Group (NSG)**:
   - Adds inbound rules for required ports defined in `PORTS_TO_OPEN`.
4. **Create Network Interface (NIC)**:
   - Attaches subnet, public IP, and NSG to the NIC.

---

## 6. VM Creation

1. **Define VM OS Disk**:

   - Standard_LRS, boot from image, SSD size defined by `OS_DISK_SSD_GB`.

2. **Define OS Profile**:

   - Admin username/password, Windows configuration with automatic updates enabled.

3. **Define VM Image Reference**:

   - Uses a fresh Windows marketplace image.

4. **Define Security Profile**:

   - Trusted Launch enabled.

5. **Create VM**:
   - Calls `compute_client.virtual_machines.begin_create_or_update` with all parameters.

---

## 7. Public IP Verification

- Verifies the NIC has a public IP assigned.
- Fetches and stores the public IP for DNS and notification purposes.
- Cleans up resources if public IP is missing.

---

## 8. DNS Configuration

1. **Create DNS zone if not exists**.
2. **Verify NS delegation** with retries using Google DNS as resolver.
3. **Create DNS A records**:
   - `pin.{subdomain}`
   - `drop.{subdomain}`
   - `web.{subdomain}`

---

## 9. Custom Script Extension Installation

- Installs the `CustomScriptExtension` on the VM.
- Executes the uploaded PowerShell setup script from blob storage.
- Updates webhook status on success or failure.

---

## 10. Temporary Storage Cleanup

- Deletes blob and container used for setup script.
- Deletes temporary storage account.
- Logs warning if cleanup fails (non-critical).

---

## 11. Completion Email

- Sends HTML email notification to configured recipients.
- Includes:
  - VM name
  - VHD download link
  - AzCopy GitHub release link
- Updates webhook status for email success or failure.

---

## 12. Final Status Update

- Waits briefly for cleanup to finish.
- Sends final `completed` status to webhook.
- Logs URLs for Moonlight service, drop files service, and pin code.

---

## 13. Error Handling

- Each major step has `try/except` blocks.
- On failure:
  - Sends `failed` status to webhook with step name and error message.
  - Cleans up Azure resources using `cleanup_resources_on_failure`.
- Top-level exceptions are caught to ensure proper cleanup and logging.

---

## 14. Helper Functions Overview

1. **Storage helpers**:

   - `create_storage_account`
   - `ensure_container_exists`
   - `upload_blob_and_generate_sas`

2. **VM Size compatibility**:

   - `get_compatible_vm_sizes`
   - `check_vm_size_compatibility`

3. **DNS helpers**:

   - `check_ns_delegation_with_retries`
   - `check_ns_delegation`

4. **Cleanup helpers**:

   - `cleanup_temp_storage`
   - `cleanup_resources_on_failure`

5. **Snapshot helpers**:

   - `stop_vm_to_snapshot`
   - `create_vm_snapshot_and_generate_sas`
   - `restart_vm`

6. **VHD export helpers**:

   - `create_vhd_export_container_and_sas`

7. **Status update**:
   - `post_status_update` with retry logic.

---

### Summary

This script fully automates the provisioning of a Windows VM in Azure with:

- VM snapshot and export
- Temporary storage handling
- Network and DNS setup
- Script extension execution
- Email notification
- Detailed webhook status updates at every step
- Robust error handling and cleanup

It is designed for automation pipelines where reliability, status reporting, and resource cleanup are critical.
