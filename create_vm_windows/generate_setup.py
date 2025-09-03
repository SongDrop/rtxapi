def generate_setup(WEBHOOK_URL: str = None) -> str:
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

# --- Registry helper ---
function Set-RegistryValue {{
    param(
        [string]$Path, 
        [string]$Name, 
        [Object]$Value, 
        [Microsoft.Win32.RegistryValueKind]$Type = [Microsoft.Win32.RegistryValueKind]::DWord
    )
    if (-not (Test-Path $Path)) {{ New-Item -Path $Path -Force | Out-Null }}
    New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType $Type -Force | Out-Null
}}

# --- SYSTEM CLEANUP & DEBLOAT ---

# OOBE completed
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Setup\\State" -Name "ImageState" -Value 7 
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Setup\\State" -Name "OOBEInProgress" -Value 0
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Setup\\State" -Name "SetupPhase" -Value 0
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Setup\\State" -Name "SystemSetupInProgress" -Value 0

# Cortana
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search" -Name "AllowCortana" -Value 0

# Edge first-run
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge" -Name "HideFirstRunExperience" -Value 1

# Windows Update auto-disable
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU" -Name "NoAutoUpdate" -Value 1

# MSA login
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" -Name "NoConnectedUser" -Value 3

# Telemetry
Set-RegistryValue -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" -Name "AllowTelemetry" -Value 0

# Content Delivery Manager tweaks
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "RotatingLockScreenEnabled" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "RotatingLockScreenOverlayEnabled" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "SubscribedContent-338388Enabled" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "SubscribedContent-310093Enabled" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "SystemPaneSuggestionsEnabled" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "SubscribedContent-SettingsEnabled" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "SubscribedContent-AppsEnabled" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" -Name "SubscribedContent-338387Enabled" -Value 0

# OneDrive
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\OneDrive" -Name "DisableFirstRun" -Value 1
Remove-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name "OneDrive" -ErrorAction SilentlyContinue

# Xbox
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Xbox" -Name "ShowFirstRunUI" -Value 0

# Game Bar
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\GameBar" -Name "ShowStartupPanel" -Value 0

# Office
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Office\\16.0\\Common\\General" -Name "ShownFirstRunOptIn" -Value 1
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Office\\16.0\\Common\\Internet" -Name "SignInOptions" -Value 3

# Feedback Hub
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\feedbackhub" -Name "Value" -Value 2

# Explorer tweaks
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer" -Name "PeopleBand" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name "TaskbarDa" -Value 0
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name "EnableBalloonTips" -Value 0

# Pen / Windows Ink
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Pen" -Name "PenWorkspaceButton" -Value 0

# Appx / Store
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Appx" -Name "DisabledByPolicy" -Value 1
Set-RegistryValue -Path "HKCU:\\Software\\Policies\\Microsoft\\WindowsStore" -Name "AutoDownload" -Value 2
Set-RegistryValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\PushNotifications" -Name "NoToastApplicationNotification" -Value 1

# Windows Search / Indexing
Stop-Service "WSearch" -Force
Set-Service "WSearch" -StartupType Disabled

# DiagTrack / Telemetry
Stop-Service "DiagTrack" -Force
Set-Service "DiagTrack" -StartupType Disabled

# Windows Error Reporting
Stop-Service "WerSvc" -Force
Set-Service "WerSvc" -StartupType Disabled

# Remote Assistance
Set-RegistryValue -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Remote Assistance" -Name "fAllowToGetHelp" -Value 0

Notify-Webhook -Status "provisioning" -Step "windows_setup_fininished" -Message "Windows setup finished..."

'''
    return script
