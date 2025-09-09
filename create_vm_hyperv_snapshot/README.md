# Azure Windows VM Snapshot Script Documentation

This document explains the `create_vm_snapshot.py` Python async script step by step.

---

## 1. Initialization and Setup

- Imports environment variables for Azure credentials, SMTP, and runtime configuration.
- Initializes logging and console colors for structured logging output.
- Defines async helpers like `run_azure_operation` and logging helpers (`print_info`, `print_success`, etc.).

---

## 2. HTTP Trigger and Input Validation

- Receives HTTP requests via Azure Functions with parameters:
  - `vm_name`
  - `resource_group`
  - `location`
  - `hook_url`
  - `recipient_emails`
- Validates required parameters and returns `400` errors if missing.
- Posts an initial status update to the webhook indicating the snapshot process has started.

---

## 3. Azure Authentication

- Checks environment variables for Azure credentials and subscription.
- Uses `ClientSecretCredential` for authentication.

---

## 4. Background Snapshot Task

- Starts the snapshot process as a background async task (`snapshot_vm_background`).
- Ensures the HTTP trigger returns immediately while the snapshot continues in the background.

---

## 5. Snapshot Process

1. **Stop VM**

   - Deallocates the VM using `compute_client.virtual_machines.begin_deallocate` to safely create a snapshot.

2. **Create VM Snapshot**

   - Retrieves the VM details and OS disk ID.
   - Creates a snapshot with `create_option: "Copy"`.
   - Polls the snapshot operation to completion.

3. **Generate SAS URL**

   - Grants temporary read access (10 hours) using `GrantAccessData`.
   - Receives a SAS URL for downloading the snapshot.

4. **Restart VM**
   - Restarts the VM using `compute_client.virtual_machines.begin_start`.
   - Logs a warning if VM restart fails but continues processing.

---

## 6. Status Updates

- Posts progress updates at every major step to the webhook.
- Retries failed webhook posts up to 3 times with incremental delay.
- Includes details like step name, timestamps, and messages.

---

## 7. Email Notification

- Sends an HTML email to the configured recipients after snapshot creation.
- Email includes:
  - Snapshot name
  - Creation timestamp
  - SAS URL for manual VHD download
- SMTP configuration is read from environment variables.
- Logs a warning if email sending fails, without stopping snapshot completion.

---

## 8. Error Handling

- Each step is wrapped in `try/except` blocks.
- Errors are logged and reported to the webhook.
- Background task stops safely if critical errors occur (e.g., VM cannot be stopped).

---

## 9. Helper Functions Overview

- **VM control:** `stop_vm_to_snapshot`, `restart_vm`
- **Status update:** `post_status_update`
- **Azure operations:** `run_azure_operation` to run synchronous SDK calls asynchronously

---

## 10. Summary

This script automates the snapshot creation of an Azure Windows VM with the following features:

- Safe deallocation of the VM before snapshot
- Managed snapshot creation with polling
- SAS URL generation for manual VHD download
- Restarting VM after snapshot
- Webhook notifications at every step
- Email notification with snapshot SAS URL for optional manual conversion
- Robust error handling and logging
