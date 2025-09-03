def generate_setup(SNAPSHOT_URL: str = None, WEBHOOK_URL: str = None, AZURE_SAS_TOKEN: str = None) -> str:
    script = f'''# Check for admin privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    Write-Host "Not running as Administrator. Relaunching as admin..."
    $scriptPath = if ($MyInvocation.MyCommand.Definition) {{ $MyInvocation.MyCommand.Definition }} else {{ $PSCommandPath }}
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" -Verb RunAs -Wait
    exit
}}

$ErrorActionPreference = "Stop"
$env:WEBHOOK_URL = "{WEBHOOK_URL}"
$env:AZURE_SAS_TOKEN = "{AZURE_SAS_TOKEN}"
$env:AZ_COPY_URL = "https://github.com/ProjectIGIRemakeTeam/azcopy-windows/releases/download/azcopy/AzCopyWin.zip"

# --- Webhook helper ---
function Notify-Webhook {{
    param([string]$Status, [string]$Step, [string]$Message)
    if (-not $env:WEBHOOK_URL) {{ return }}
    $payload = @{{ 
        vm_name = $env:COMPUTERNAME
        status = $Status
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        details = @{{ step = $Step; message = $Message }}
    }} | ConvertTo-Json -Depth 4
    try {{
        Invoke-RestMethod -Uri $env:WEBHOOK_URL -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec 30
    }} catch {{
        Write-Warning "Failed to notify webhook: $_"
    }}
}}

# --- Log Setup ---
$logDir = "C:\\Program Files\\Logs"
$installLog = "$logDir\\setup_hyperv_log.txt"
try {{
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}} catch {{
    Write-Warning "Failed to create log directory: $_"
}}
Add-Content -Path $installLog -Value "=== Hyper-V Setup Script Started $(Get-Date) ==="

# Mark Windows as OOBE-completed
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State" -Name "ImageState" -Value "IMAGE_STATE_COMPLETE"
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State" -Name "OOBEInProgress" -Value 0
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State" -Name "SetupPhase" -Value 0
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State" -Name "SystemSetupInProgress" -Value 0

# Suppress Cortana first-run
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search" -Name "AllowCortana" -Value 0

# Suppress Edge first-run
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge" -Name "HideFirstRunExperience" -Value 1

# Turn off automatic updates temporarily
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Name "NoAutoUpdate" -Value 1

# Prevent MSA login prompts
New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name "NoConnectedUser" -PropertyType DWord -Value 3 -Force

# Disable diagnostic data prompts
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection" -Name "AllowTelemetry" -Value 0

# Suppress “Set default apps” notification
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "RotatingLockScreenEnabled" -Value 0 -Force
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "RotatingLockScreenOverlayEnabled" -Value 0 -Force
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "SubscribedContent-338388Enabled" -Value 0 -Force

# Disable OneDrive first-run setup
New-ItemProperty -Path "HKCU:\Software\Microsoft\OneDrive" -Name "DisableFirstRun" -Value 1 -Force

# Disable Xbox first-run
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Xbox" -Name "ShowFirstRunUI" -Value 0

# Disable Xbox Game Bar
Set-ItemProperty -Path "HKCU:\Software\Microsoft\GameBar" -Name "ShowStartupPanel" -Value 0 -Force

# Disable Windows welcome experience
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "SubscribedContent-310093Enabled" -Value 0 -Force
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "SystemPaneSuggestionsEnabled" -Value 0 -Force

# Disable lock screen background slideshow
New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization" -Name "NoLockScreen" -Value 1 -Force

# Disable OneDrive auto-start
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "OneDrive" -Value "" -ErrorAction SilentlyContinue

# Disable Office First Run
New-ItemProperty -Path "HKCU:\Software\Microsoft\Office\16.0\Common\General" -Name "ShownFirstRunOptIn" -Value 1 -Force

# Disable Feedback Hub first-run
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\feedbackhub" -Name "Value" -Value 2 -Force

# Disable Connected User Experiences and Telemetry
Stop-Service "DiagTrack" -Force
Set-Service "DiagTrack" -StartupType Disabled

# Disable Windows tips, suggestions, and notifications
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "SubscribedContent-SettingsEnabled" -Value 0 -Force
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "SubscribedContent-AppsEnabled" -Value 0 -Force

# Disable People Bar
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" -Name "PeopleBand" -Value 0 -Force

# Disable Widgets (Windows 11)
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarDa" -Value 0 -Force

# Disable Spotlight images on lock screen
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "RotatingLockScreenEnabled" -Value 0 -Force
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "RotatingLockScreenOverlayEnabled" -Value 0 -Force

# Disable Windows Store first-run
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Appx" -Name "DisabledByPolicy" -Value 1 -Force

# Disable all current user startup items
Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" | foreach {{
    Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $_.PSChildName -ErrorAction SilentlyContinue
}}

# Disable Action Center (notification center)
Set-ItemProperty -Path "HKCU:\Software\Policies\Microsoft\Windows\Explorer" -Name "DisableNotificationCenter" -Value 1 -Force

# Disable Windows Defender popups (not the service)
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "EnableBalloonTips" -Value 0 -Force

# Prevent Microsoft Store from auto-updating apps
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications" -Name "NoToastApplicationNotification" -Value 1 -Force
Set-ItemProperty -Path "HKCU:\Software\Policies\Microsoft\WindowsStore" -Name "AutoDownload" -Value 2 -Force

# Disable “Get Office” notifications
New-ItemProperty -Path "HKCU:\Software\Microsoft\Office\16.0\Common\Internet" -Name "SignInOptions" -Value 3 -Force

# Lock screen tips
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name "SubscribedContent-338387Enabled" -Value 0 -Force

# Disable Windows Error Reporting service
Stop-Service "WerSvc" -Force
Set-Service "WerSvc" -StartupType Disabled

# Disable “Windows Ink Workspace” popups
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Pen" -Name "PenWorkspaceButton" -Value 0 -Force

# Disable Windows Search indexing for faster snapshot/VHD performance
Set-Service "WSearch" -StartupType Disabled
Stop-Service "WSearch" -Force

# Disable Remote Assistance prompts:
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Remote Assistance" -Name "fAllowToGetHelp" -Value 0 -Force

# --- Enable Hyper-V ---
try {{
    $hyperVFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
    if ($hyperVFeature.State -ne "Enabled") {{
        Notify-Webhook -Status "provisioning" -Step "hyperv_enable" -Message "Enabling Hyper-V..."
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -All -NoRestart

        # Schedule post-reboot continuation
        $taskName = "PostHyperVSetup"
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
        Notify-Webhook -Status "info" -Step "hyperv_enable" -Message "Scheduled post-reboot continuation."

        Notify-Webhook -Status "provisioning" -Step "hyperv_restart" -Message "Restarting computer to complete Hyper-V installation..."
        Restart-Computer -Force
        exit
    }} else {{
        Notify-Webhook -Status "success" -Step "hyperv_enable" -Message "Hyper-V already enabled."
    }}
}} catch {{
    Notify-Webhook -Status "failed" -Step "hyperv_enable" -Message "Hyper-V installation failed: $_"
    exit 1
}}

# --- Download snapshot ---
$userProfile = [Environment]::GetFolderPath("UserProfile")
$snapshotDir = Join-Path $userProfile "Downloads"
if (-not (Test-Path $snapshotDir)) {{ New-Item -Path $snapshotDir -ItemType Directory -Force | Out-Null }}

'''

    if SNAPSHOT_URL:
        script += f'''
$snapshotPath = Join-Path $snapshotDir "azure-os-disk.vhd"

try {{
    ####STEP-1: DOWNLOAD SNAPSHOT
    Notify-Webhook -Status "provisioning" -Step "snapshot_download" -Message "Downloading snapshot from {SNAPSHOT_URL}..."
    Invoke-WebRequest -Uri "{SNAPSHOT_URL}" -OutFile $snapshotPath -UseBasicParsing
    if (-Not (Test-Path $snapshotPath)) {{
        throw "Snapshot download failed: File not found"
    }}
    Notify-Webhook -Status "success" -Step "snapshot_download" -Message "Snapshot downloaded to $snapshotPath"

    ####STEP-2: CREATE BOOTABLE FIXED VHD
    Notify-Webhook -Status "provisioning" -Step "hyperv_finalize" -Message "Creating bootable fixed VHD..."
    Import-Module Hyper-V -ErrorAction Stop
    $fixedVHD = Join-Path $snapshotDir "azure-os-disk_fixed.vhd"
    Convert-VHD -Path $snapshotPath -DestinationPath $fixedVHD -VHDType Fixed
    if (-Not (Test-Path $fixedVHD)) {{
        throw "Fixed VHD creation failed: File not found"
    }}
    Notify-Webhook -Status "success" -Step "hyperv_finalize" -Message "Bootable fixed VHD created at $fixedVHD"

    ####STEP-3: DOWNLOAD AZCOPY
    try {{
        $azcopyZip = Join-Path $snapshotDir "AzCopyWin.zip"
        Invoke-WebRequest -Uri "$env:AZ_COPY_URL" -OutFile $azcopyZip -UseBasicParsing
        Expand-Archive -Path $azcopyZip -DestinationPath $snapshotDir -Force
        Remove-Item $azcopyZip -Force
        Notify-Webhook -Status "success" -Step "azcopy_download" -Message "AzCopy downloaded and extracted"
    }} catch {{
        throw "AzCopy download/extract failed: $_"
    }}

    s####STEP-4: UPLOAD FIXED VHD VIA AZCOPY
    try {{
        $azcopyExe = Join-Path $snapshotDir "AzCopy\azcopy.exe"
        Notify-Webhook -Status "provisioning" -Step "vhd_upload" -Message "Uploading fixed VHD via CMD..."
        
        # Run AzCopy using cmd.exe
        $cmdArgs = "/c `"$azcopyExe copy `"$fixedVHD`" `$env:AZURE_SAS_TOKEN --recursive`""
        Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -Wait -NoNewWindow
        
        Notify-Webhook -Status "success" -Step "vhd_upload" -Message "Fixed VHD uploaded successfully"
    }} catch {{
        throw "AzCopy upload failed: $_"
    }}


    ####STEP-5: COMPLETION
    Notify-Webhook -Status "success" -Step "setup_finished" -Message "Hyper-V setup and VHD upload completed successfully"

}} catch {{
    Notify-Webhook -Status "failed" -Step "hyperv_process" -Message "Process failed: $_"
    exit 1
}}
'''

    return script
