def generate_setup(SNAPSHOT_URL: str = None) -> str:
    script = f'''# Check for admin privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    Write-Host "Not running as Administrator. Relaunching as admin..."
    $scriptPath = if ($MyInvocation.MyCommand.Definition) {{ $MyInvocation.MyCommand.Definition }} else {{ $PSCommandPath }}
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" -Verb RunAs -Wait
    exit
}}

$ErrorActionPreference = "Stop"
$logDir = "C:\\Program Files\\Logs"
$installLog = "$logDir\\setup_hyperv_log.txt"
New-Item -Path $logDir -ItemType Directory -Force | Out-Null
Add-Content -Path $installLog -Value "=== Hyper-V Setup Script Started $(Get-Date) ==="

# --- Enable Hyper-V ---
$hyperVFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
if ($hyperVFeature.State -ne "Enabled") {{
    Write-Host "Enabling Hyper-V feature..."
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -All -NoRestart
    Add-Content -Path $installLog -Value "[INFO] Hyper-V enabled. Restart required."

    # Schedule this script to continue after restart
    $taskName = "PostHyperVSetup"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
    Write-Host "Scheduled task created to continue after restart."

    Write-Host "Restarting computer to complete Hyper-V installation..."
    Add-Content -Path $installLog -Value "[INFO] Restarting for Hyper-V..."
    Restart-Computer -Force
    exit
}} else {{
    Write-Host "Hyper-V already enabled."
    Add-Content -Path $installLog -Value "[INFO] Hyper-V already enabled."
}}

# --- Post-reboot continuation: download snapshot if provided ---
'''

    if SNAPSHOT_URL:
        # Use the current user's profile for Downloads folder
        script += f'''
try {{
    $userProfile = [Environment]::GetFolderPath("UserProfile")
    $snapshotDir = Join-Path $userProfile "Downloads"
    if (-not (Test-Path $snapshotDir)) {{ New-Item -Path $snapshotDir -ItemType Directory -Force | Out-Null }}
    $snapshotPath = Join-Path $snapshotDir "azure-os-disk.vhd"

    Write-Host "Downloading Hyper-V snapshot from {SNAPSHOT_URL} to $snapshotPath..."
    Invoke-WebRequest -Uri "{SNAPSHOT_URL}" -OutFile $snapshotPath -UseBasicParsing
    Write-Host "Snapshot downloaded successfully."
    Add-Content -Path $installLog -Value "[SUCCESS] Snapshot downloaded to $snapshotPath"
}} catch {{
    Write-Warning "Failed to download snapshot: $_"
    Add-Content -Path $installLog -Value "[ERROR] Snapshot download failed: $_"
}}
'''

    script += '''
Add-Content -Path $installLog -Value "=== Hyper-V Setup Script Finished $(Get-Date) ==="
Write-Host "Hyper-V setup script finished."
'''

    return script
