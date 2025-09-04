<pre>
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
- Writes final log entry with the setup completion timestamp.
- Script is fully automated, combining system hardening, debloating, network configuration, and Hyper-V setup.

---

**Summary:**  
This script is designed for automated Windows provisioning. It prepares the machine by disabling telemetry and unnecessary services, applying user and system-level debloat, configuring network privacy, and installing/enabling Hyper-V with a post-reboot helper. All actions are logged and optionally reported to a webhook for monitoring purposes.
</pre>
