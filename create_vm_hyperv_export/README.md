# Azure Windows VM Provisioning and Hyper-V VHD Export Documentation

This document explains, step by step, the combined Python async and PowerShell scripts used to provision a Windows VM in Azure, capture a snapshot, and automatically convert/export it as a bootable VHD.

---

## 1. Initialization and Setup (Python)

- Loads environment variables for Azure credentials, SMTP, and webhook configuration.
- Sets global variables for:
  - Storage account keys
  - Snapshot URLs
  - SAS tokens for secure access
- Prepares helper functions for:
  - Logging (`print_info`, `print_warn`, `print_error`, `print_success`)
  - Sending webhook status updates (`post_status_update`)

---

## 2. VM Snapshot and Storage Preparation

1. **Stop VM safely**:

   - Calls `stop_vm_to_snapshot` to deallocate the VM.
   - Ensures the OS disk is in a consistent state.

2. **Create snapshot**:

   - Copies the VM OS disk using `compute_client.snapshots.begin_create_or_update`.

3. **Generate SAS URL for snapshot**:

   - Uses `compute_client.disks.begin_export` to produce a secure, temporary download link.

4. **Restart VM**:
   - Calls `restart_vm` after snapshot creation.

---

## 3. Temporary Storage Account and VHD Export Container

- Creates a temporary Azure storage account for storing VHD exports.
- Creates a container (`vhdusb`) and generates a SAS token for uploading fixed-size bootable VHD files using AzCopy.

---

## 4. PowerShell Setup Script Generation

- Dynamically generates a `setup.ps1` script with placeholders replaced for:
  - `SNAPSHOT_URL`
  - `AZURE_SAS_TOKEN`
  - `WEBHOOK_URL`
- The script is uploaded to blob storage and executed on the VM using `CustomScriptExtension`.

---

## 5. Network Infrastructure Setup

1. **Virtual Network and Subnet**: Creates VNet and subnet for the VM.
2. **Public IP**: Assigns public IP to VM NIC.
3. **Network Security Group (NSG)**: Adds inbound rules for required ports (`PORTS_TO_OPEN`).
4. **Network Interface (NIC)**: Attaches subnet, public IP, and NSG.

---

## 6. VM Creation

- Defines OS disk and VM image (fresh Windows Marketplace image).
- Sets admin credentials and security profile (Trusted Launch).
- Creates VM using `compute_client.virtual_machines.begin_create_or_update`.

---

## 7. Public IP and DNS Verification

- Verifies public IP assignment.
- Creates DNS zone and A records:
  - `pin.{subdomain}`
  - `drop.{subdomain}`
  - `web.{subdomain}`
- Retries NS delegation verification using public resolvers.

---

## 8. Custom Script Extension Execution

- Installs `CustomScriptExtension` on VM.
- Executes uploaded PowerShell setup script.
- Updates webhook with success/failure of script execution.

---

## 9. PowerShell Setup Script – Hyper-V Preparation and Cleanup

1. **Admin Elevation**:

   - Checks for admin privileges; relaunches if necessary.

2. **System Debloat**:

   - Registry tweaks for telemetry, Cortana, Windows Search, Edge first-run, and Windows Update auto settings.
   - Disables unnecessary services (`WSearch`, `DiagTrack`, `WerSvc`).

3. **User Debloat**:

   - Adjusts HKCU keys for OneDrive, Xbox, GameBar, Office, notifications, and lock screen features.

4. **Network Profile Enforcement**:

   - Forces all network profiles to Private.
   - Disables discovery-related firewall rules.

5. **Post-Reboot Helper**:
   - Ensures all tweaks persist after Hyper-V installation.
   - Creates a watchdog script to enforce Private network profiles.
   - Registers scheduled tasks for post-reboot execution.

---

## 10. Hyper-V Enablement and Snapshot Processing

1. **Enable Hyper-V**:

   - Checks if `Microsoft-Hyper-V-All` is installed.
   - Enables Hyper-V if not already enabled and schedules a reboot.

2. **VHD Download & Conversion**:

   - Downloads snapshot VHD via `wget` (resumable).
   - Converts dynamic VHD to fixed-size VHD using `Convert-VHD`.

3. **Free Space Zeroing**:

   - Uses `sdelete` or `cipher /w` to zero unused space, optimizing for USB export.

4. **VHD Optimization**:

   - Compacts VHD using `Optimize-VHD` to minimize size.

5. **VHD Upload**:
   - Uploads fixed VHD to Azure via AzCopy with SAS token.

---

## 11. Watchdog Script for Network and Services

- Script ensures:
  - All network profiles remain Private.
  - `NlaSvc` and discovery-related services stay disabled.
  - Scheduled tasks enforce network settings across reboots.

---

## 12. Cleanup and Logging

- Removes temporary helper scripts.
- Unregisters scheduled tasks.
- Logs progress and errors to:
  - `C:\Program Files\Logs\setup_hyperv_log.txt`
- Sends webhook notifications at each significant step.

---

## 13. Final Status Reporting

- Sends `completed` webhook status.
- Optionally, sends email with:
  - VM details
  - VHD download link
  - AzCopy release link

---

## 14. Error Handling

- Each major step wrapped in `try/catch`.
- On failure:
  - Sends `failed` webhook status.
  - Cleans up Azure resources.
- Ensures robust handling of partial failures, network issues, or file download errors.

---

## 15. Summary

The combined Python and PowerShell automation pipeline allows:

- **Fully automated VM provisioning** in Azure.
- **Snapshot creation and export** to storage.
- **Hyper-V setup on Windows VM**, including debloating and network hardening.
- **Conversion to bootable fixed VHD** with free-space zeroing and optimization.
- **Automated upload** to Azure storage or local USB export.
- **Webhook and email notifications** at every step.
- **Post-reboot persistence** with watchdog scripts.

This enables a reliable **cloud → bootable Hyper-V/USB workflow** with minimal manual intervention.
