def generate_setup(WEBHOOK_URL: str = None) -> str:
    script = r'''# Check for admin privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Not running as Administrator. Relaunching as admin..."
    $scriptPath = if ($MyInvocation.MyCommand.Definition) { $MyInvocation.MyCommand.Definition } else { $PSCommandPath }
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" -Verb RunAs -Wait
    exit
}

$ErrorActionPreference = "Stop"
$env:WEBHOOK_URL = "__WEBHOOK_URL__"

# --- Webhook helper ---
function Notify-Webhook {
    param([string]$Status, [string]$Step, [string]$Message)
    # Local log first (always visible)
    Add-Content -Path $installLog -Value "[$(Get-Date -Format 'HH:mm:ss')] $Step -> $Message"
    # Only call webhook if URL is set
    if (-not $env:WEBHOOK_URL) { return }
    # payload
    $payload = @{
        vm_name = $env:COMPUTERNAME
        status = $Status
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        resource_group = "windows_internal"
        location = "windows_internal_script"  
        details = @{ step = $Step; message = $Message }
    } | ConvertTo-Json -Depth 4

    try {
        Invoke-RestMethod -Uri $env:WEBHOOK_URL -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec 30
    } catch {
        # Log locally if webhook fails
        Add-Content -Path $installLog -Value "[$(Get-Date -Format 'HH:mm:ss')] Webhook failed: $_"
    }
}

# --- Log setup ---
$logDir = "C:\Program Files\Logs"
$installLog = "$logDir\setup_windows_log.txt"
try {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
} catch {
    Write-Warning "Failed to create log directory: $_"
}
Add-Content -Path $installLog -Value "=== Windows Setup Script Started $(Get-Date) ==="

# --- Registry helper ---
function Set-RegistryValue {
    param(
        [string]$Path,
        [string]$Name,
        [Object]$Value,
        [Microsoft.Win32.RegistryValueKind]$Type = [Microsoft.Win32.RegistryValueKind]::DWord
    )

    if (-not (Test-Path $Path)) {
        try {
            New-Item -Path $Path -Force | Out-Null
        } catch {
            return
        }
    }

    try {
        New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType $Type -Force | Out-Null
    } catch {
    }
}

# --- SYSTEM CLEANUP & DEBLOAT (HKLM + SYSTEM) ---
Notify-Webhook -Status "provisioning" -Step "debloat_windows" -Message "Debloating Windows"

# Create system keys hashtable with proper syntax
$systemKeys = @{}

# Add registry keys one by one to avoid syntax issues
$systemKeys["HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State"] = @{ 
    "ImageState" = 7; "OOBEInProgress" = 0; "SetupPhase" = 0; "SystemSetupInProgress" = 0 
}
$systemKeys["HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE"] = @{ 
    "PrivacyConsentStatus" = 1; "DisablePrivacyExperience" = 1; "SkipMachineOOBE" = 1; "SkipUserOOBE" = 1 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows\OOBE"] = @{ 
    "DisablePrivacyExperience" = 1 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search"] = @{ 
    "AllowCortana" = 0 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Edge"] = @{ 
    "HideFirstRunExperience" = 1 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"] = @{ 
    "NoAutoUpdate" = 1 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows\System"] = @{ 
    "NoConnectedUser" = 3 
}
$systemKeys["HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection"] = @{ 
    "AllowTelemetry" = 0 
}
$systemKeys["HKLM:\SYSTEM\CurrentControlSet\Control\Remote Assistance"] = @{ 
    "fAllowToGetHelp" = 0 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections"] = @{ 
    "NC_ShowSharedAccessUI" = 0 
}
$systemKeys["HKLM:\SYSTEM\CurrentControlSet\Control\Network"] = @{ 
    "NewNetworkWindowOff" = 1; "Category" = 1 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections"] = @{ 
    "NC_StdDomainUserSetLocation" = 1; "NC_EnableNetSetupWizard" = 0 
}
$systemKeys["HKLM:\SOFTWARE\Microsoft\Windows Defender\Features"] = @{ 
    "DisableAntiSpywareNotification" = 1 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Security Center\Notifications"] = @{ 
    "DisableNotifications" = 1 
}
$systemKeys["HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Notifications"] = @{ 
    "DisableEnhancedNotifications" = 1 
}

try {
    Get-NetConnectionProfile | ForEach-Object {
        try { Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue } catch { }
    }
} catch { }

foreach ($path in $systemKeys.Keys) {
    foreach ($kv in $systemKeys[$path].GetEnumerator()) {
        Set-RegistryValue -Path $path -Name $kv.Key -Value $kv.Value
    }
}

foreach ($path in $systemKeys.Keys) {
    foreach ($kv in $systemKeys[$path].GetEnumerator()) {
        Set-RegistryValue -Path $path -Name $kv.Key -Value $kv.Value
    }
}

# --- Extra registry to suppress "no internet" and location prompts ---
try {
    New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_DoNotShowLocalOnlyConnectivityPrompt" -Value 1 -PropertyType DWord -Force | Out-Null
} catch { }

# --- Force all existing network profiles to Private ---
try {
    $profilesPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
    if (Test-Path $profilesPath) {
        Get-ChildItem $profilesPath | ForEach-Object {
            try {
                Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Force
            } catch { }
        }
    }
} catch { }


$services = @("WSearch","DiagTrack","WerSvc")
foreach ($svc in $services) {
    try { Stop-Service $svc -Force -ErrorAction SilentlyContinue } catch { }
    try { Set-Service $svc -StartupType Disabled } catch { }
}

# --- USER CLEANUP & DEBLOAT (HKCU) ---
$hkcuProfiles = Get-ChildItem "C:\Users" -Directory | Where-Object { Test-Path "$($_.FullName)\NTUSER.DAT" }

$userKeys = @(
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
        Values=@{
            "RotatingLockScreenEnabled" = 0
            "RotatingLockScreenOverlayEnabled" = 0
            "SubscribedContent-338388Enabled" = 0
            "SubscribedContent-310093Enabled" = 0
            "SystemPaneSuggestionsEnabled" = 0
            "SubscribedContent-SettingsEnabled" = 0
            "SubscribedContent-AppsEnabled" = 0
            "SubscribedContent-338387Enabled" = 0
        }
    }
    @{
        Path="Software\Microsoft\OneDrive"
        Values=@{
            "DisableFirstRun" = 1
        }
    }
    @{
        Path="Software\Microsoft\Xbox"
        Values=@{
            "ShowFirstRunUI" = 0
        }
    }
    @{
        Path="Software\Microsoft\GameBar"
        Values=@{
            "ShowStartupPanel" = 0
        }
    }
    @{
        Path="Software\Microsoft\Office\16.0\Common\General"
        Values=@{
            "ShownFirstRunOptIn" = 1
        }
    }
    @{
        Path="Software\Microsoft\Office\16.0\Common\Internet"
        Values=@{
            "SignInOptions" = 3
        }
    }
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\feedbackhub"
        Values=@{
            "Value" = 2
        }
    }
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
        Values=@{
            "PeopleBand" = 0
        }
    }
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
        Values=@{
            "TaskbarDa" = 0
            "EnableBalloonTips" = 0
        }
    }
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\Pen"
        Values=@{
            "PenWorkspaceButton" = 0
        }
    }
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\Appx"
        Values=@{
            "DisabledByPolicy" = 1
        }
    }
    @{
        Path="Software\Policies\Microsoft\WindowsStore"
        Values=@{
            "AutoDownload" = 2
        }
    }
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\PushNotifications"
        Values=@{
            "NoToastApplicationNotification" = 1
        }
    }
    @{
        Path="Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
        Values=@{
            "NOC_GLOBAL_SETTING_TOASTS_ENABLED" = 0
        }
    }
    @{
        Path="Software\Microsoft\Windows Defender Security Center\Notifications"
        Values=@{
            "DisableNotifications" = 1
        }
    }
)

foreach ($profile in $hkcuProfiles) {
    foreach ($key in $userKeys) {
        foreach ($kv in $key.Values.GetEnumerator()) {
            try {
                $fullPath = "HKU:\$($profile.SID)\$($key.Path)"
                if (-not (Test-Path $fullPath)) { New-Item -Path $fullPath -Force | Out-Null }
                Set-RegistryValue -Path $fullPath -Name $kv.Key -Value $kv.Value
            } catch { }
        }
    }
}

Notify-Webhook -Status "provisioning" -Step "post_reboot_script" -Message "Creating Windows Post-Reboot script"

# ---- Post-reboot helper script ----
$helperPath = "C:\ProgramData\PostWindowsSetup.ps1"

# Create helper script content
$helperContent = @'
# Post-reboot Windows setup script with watchdog for network profiles
try {
    Write-Output "Starting PostWindowsSetup..."

    # --- 0. Ensure script is running as Administrator ---
    if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Write-Warning "Script must be run as Administrator to modify protected registry keys."
        return
    }

    # --- 1. Delay to allow system services to stabilize ---
    Start-Sleep -Seconds 5

    # --- 2. Set all current network profiles to Private via registry ---
    try {
        $profilesPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
        if (Test-Path $profilesPath) {
            $profiles = Get-ItemProperty -Path "$profilesPath\*" | Select-Object `
                @{Name='InterfaceIndex';Expression={$_.PSChildName}},
                @{Name='Name';Expression={$_.ProfileName}},
                @{Name='NetworkCategory';Expression={
                    switch ($_.Category) {
                        0 {"Public"}
                        1 {"Private"}
                        2 {"Domain"}
                        default {"Unknown"}
                    }
                }}
            foreach ($p in $profiles) {
                if ($p.NetworkCategory -ne "Private") {
                    Write-Output "Forcing profile $($p.Name) to Private"
                    Set-ItemProperty -Path "$profilesPath\$($p.InterfaceIndex)" -Name "Category" -Value 1 -Force
                }
            }
        }
    } catch {
        Write-Warning "Failed to update registry network profiles: $_"
    }

    # --- 3. Restart netprofm service only (defer NlaSvc) ---
    try {
        Restart-Service "netprofm" -Force -ErrorAction SilentlyContinue
        Write-Output "Restarted service: netprofm"
    } catch {
        Write-Warning "Failed to restart service netprofm: $_"
    }

    # --- 4. Disable Network Discovery firewall rules ---
    try {
        Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled False -ErrorAction SilentlyContinue
        Set-NetFirewallRule -Group "@FirewallAPI.dll,-32752" -Enabled False -ErrorAction SilentlyContinue
        Write-Output "Disabled Network Discovery firewall rules"
    } catch {
        Write-Warning "Failed to disable firewall rules: $_"
    }

    # --- 5. Stop and disable discovery-related services ---
    $servicesToDisable = @("FDResPub", "FDHost", "UPnPHost", "SSDPSRV")
    foreach ($svc in $servicesToDisable) {
        try {
            Stop-Service $svc -Force -ErrorAction SilentlyContinue
            Set-Service $svc -StartupType Disabled -ErrorAction SilentlyContinue
            Write-Output "Disabled service: ${svc}"
        } catch {
            Write-Warning "Failed to disable service ${svc}: $_"
        }
    }

    # --- 6. Disable network location wizard & suppress prompts ---
    try {
        New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Network" -Name "NewNetworkWindowOff" -Value 1 -PropertyType DWord -Force | Out-Null
        New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Network\NetworkLocationWizard" -Name "HideWizard" -Value 1 -PropertyType DWord -Force | Out-Null
        New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_StdDomainUserSetLocation" -Value 1 -PropertyType DWord -Force | Out-Null
        New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_EnableNetSetupWizard" -Value 0 -PropertyType DWord -Force | Out-Null
        New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_DoNotShowLocalOnlyConnectivityPrompt" -Value 1 -PropertyType DWord -Force | Out-Null
        Write-Output "Disabled network location wizard and suppressed prompts as SYSTEM"
    } catch {
        Write-Warning "Failed to update registry for network wizard: $_"
    }

    # --- 7. Disable firewall notifications ---
    try {
        New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows Defender\Features" -Name "DisableAntiSpywareNotification" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
        New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Security Center\Notifications" -Name "DisableNotifications" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
        New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Notifications" -Name "DisableEnhancedNotifications" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
        Write-Output "Disabled firewall notifications (if permitted)"
    } catch {
        Write-Warning "Failed to update firewall notification settings: $_"
    }

    # --- 8. Safely restart NlaSvc to enforce Private profiles ---
    try {
        $needRestartNla = $false
        if (Test-Path $profilesPath) {
            $profiles = Get-ItemProperty -Path "$profilesPath\*" | Select-Object PSChildName, Category
            foreach ($p in $profiles) {
                if ($p.Category -ne 1) { $needRestartNla = $true }
            }
        }
        if ($needRestartNla) {
            try {
                Stop-Service "NlaSvc" -Force -ErrorAction SilentlyContinue
                Start-Service "NlaSvc" -ErrorAction SilentlyContinue
                Set-Service "NlaSvc" -StartupType Disabled -ErrorAction SilentlyContinue
                Write-Output "Safely restarted and disabled NlaSvc to enforce Private network profiles"
            } catch {
                Write-Warning "Failed to disable NlaSvc safely: $_"
            }
        }
    } catch {
        Write-Warning "Failed to check or restart NlaSvc: $_"
    }

    # --- 9. Install watchdog script to enforce Private profiles ---
    try {
        $watchdogPath = "C:\ProgramData\EnforcePrivateNetworks_.ps1"
        $watchdogContent = @"
# Enforce all network profiles to Private and disable NlaSvc safely
try {
    Write-Output 'Starting EnforcePrivateNetworks script...'

    # Registry path to network profiles
    `$profilesPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles'

    # Force all profiles to Private
    if (Test-Path `$profilesPath) {
        Get-ChildItem `$profilesPath | ForEach-Object {
            try {
                Set-ItemProperty -Path `$_.PSPath -Name 'Category' -Value 1 -Force
                Write-Output "Registry forced Private for profile `$(`$_.PSChildName)"
            } catch {
                Write-Warning "Failed to update registry for profile `$(`$_.PSChildName): `$_"
            }
        }
    }

    # Stop and disable NlaSvc
    `$nla = Get-Service 'NlaSvc' -ErrorAction SilentlyContinue
    if (`$nla) {
        Stop-Service 'NlaSvc' -Force -ErrorAction SilentlyContinue
        Set-Service 'NlaSvc' -StartupType Disabled -ErrorAction SilentlyContinue
        Write-Output "Stopped and disabled NlaSvc service"
    }

    Write-Output 'EnforcePrivateNetworks script completed successfully.'
} catch {
    Write-Warning "Script failed: `$_"
}
"@
        $watchdogContent | Set-Content -Path $watchdogPath -Force -Encoding UTF8

        $taskName = "EnforcePrivateNetworks"
        if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        }

        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$watchdogPath`""
        $trigger = New-ScheduledTaskTrigger -AtStartup
        Register-ScheduledTask -Action $action -Trigger $trigger -TaskName $taskName -Description "Watchdog to enforce Private network profiles and disable NlaSvc" -User "SYSTEM" -RunLevel Highest
        Write-Output "Watchdog script installed and Scheduled Task created."
    } catch {
        Write-Warning "Failed to install watchdog: $_"
    }

    Write-Output "PostWindowsSetup completed successfully."
} catch {
    Write-Output "PostWindowsSetup encountered a fatal error: $_"
}

    # --- 10. Cleanup ---
    try {
        Unregister-ScheduledTask -TaskName "PostWindowsSetup" -Confirm:$false -ErrorAction SilentlyContinue
        if ($helperPath) {
            Remove-Item -Path "$helperPath" -Force -ErrorAction SilentlyContinue
            Write-Output "Removed helper script: $helperPath"
        }
        Write-Output "Cleanup complete"
    } catch {
        Write-Warning "Cleanup failed: $_"
    }

    # --- Extend C: to use all unallocated space ---
    try {
        $cDisk = Get-Partition -DriveLetter C | Get-Disk
        $cPartition = Get-Partition -DriveLetter C

        # Only extend if there’s free/unallocated space
        $sizeRemaining = ($cDisk | Get-PartitionSupportedSize -PartitionNumber $cPartition.PartitionNumber)
        if ($sizeRemaining.SizeMax -gt $cPartition.Size) {
            Resize-Partition -DriveLetter C -Size $sizeRemaining.SizeMax
            Write-Output "C: drive extended to maximum available size."
        } else {
            Write-Output "No unallocated space to extend C: drive."
        }
    } catch {
        Write-Warning "Failed to extend C: drive: $_"
    }

    # --- Check for admin privileges ---
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "Not running as Administrator. Relaunching as admin..."
        $scriptPath = if ($MyInvocation.MyCommand.Definition) { $MyInvocation.MyCommand.Definition } else { $PSCommandPath }
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" -Verb RunAs -Wait
        exit
    }

    # --- Initialize logging ---
    $installLog = "C:\rds_install.log"
    Add-Content -Path $installLog -Value "RDS setup started at $(Get-Date)"

    # --- Notify webhook ---
    function Notify-Webhook {
        param($Status, $Step, $Message)
        # Replace this with your actual webhook call
        Add-Content -Path $installLog -Value "[$Status] [$Step] $Message"
    }

    # --- Install Remote Desktop Services Roles ---
    Notify-Webhook -Status "provisioning" -Step "install_rds" -Message "Installing RDS Roles"
    try {
        Install-WindowsFeature -Name RDS-RD-Server, RDS-Web-Access -IncludeManagementTools -Restart
        Notify-Webhook -Status "provisioning" -Step "rds_installed" -Message "RDS Roles installed successfully"
    } catch {
        Notify-Webhook -Status "failed" -Step "install_rds" -Message "RDS installation failed: $_"
        exit 1
    }

    # --- Optional: Configure self-signed SSL for Web Access ---
    try {
        $cert = New-SelfSignedCertificate -DnsName $env:COMPUTERNAME -CertStoreLocation "Cert:\LocalMachine\My"
        $thumbprint = $cert.Thumbprint
        # Bind certificate to IIS default site (RDS Web Access)
        New-Item -Path "IIS:\SslBindings\0.0.0.0!443" -Value $thumbprint
        Notify-Webhook -Status "provisioning" -Step "rds_ssl" -Message "RDS Web Access SSL configured"
    } catch {
        Notify-Webhook -Status "warning" -Step "rds_ssl" -Message "Failed to configure SSL: $_"
    }

    # --- Finalize ---
    Add-Content -Path $installLog -Value "RDS setup completed at $(Get-Date)"
    Write-Host "RDS setup finished. Check $installLog for details."

'@  # must be at column 0

try {
    $helperContent | Out-File -FilePath $helperPath -Encoding UTF8 -Force
    Add-Content -Path $installLog -Value "Wrote helper script to $helperPath"
    # Right after writing the helper script
    Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -File `"$helperPath`"" -Wait
} catch {
    Add-Content -Path $installLog -Value "Failed to write helper script: $_"
}

# Register scheduled task to run the helper once at startup
try {
    # Define the name of the scheduled task
    $taskName = "PostWindowsSetup"
    # Remove any existing task with the same name to avoid conflicts
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    # Define the action the scheduled task will perform: run PowerShell with the helper script
    $action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$helperPath`""
    # Set the trigger for the task: run at user AtStartup
    $trigger = New-ScheduledTaskTrigger -AtStartup
    # Define task settings with proper Windows version and description
    # Create a ScheduledTaskSettingsSet for Windows 10
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    # $settings.Description = "Post-Windows setup script: configures network, disables popups, and creates Windows Manager shortcut"
    # $settings.Author = "Windows 10 Developer"
    # Define the principal (user context) for the task:
    # RunLevel Highest runs with elevated privileges
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
    # Register (create) the scheduled task with the defined name, action, trigger, and principal
    # -Force ensures it overwrites any existing task with the same name
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force

    
} catch {
    # If anything fails, log the error message to the install log
    Add-Content -Path $installLog -Value "Failed to register scheduled task: $_"
}

# --Disable NlaSvc before reboot---
# Do NOT stop it immediately (causes timeout in provisioning)
Set-Service -Name "NlaSvc" -StartupType Disabled -ErrorAction SilentlyContinue


Add-Content -Path $installLog -Value "Setup script completed at $(Get-Date)"
'''
    # Dictionary of placeholders -> values to insert into the script.
    # You can add more entries here later if needed (e.g., __ADMIN_EMAIL__, __SERVER_NAME__).
    replacements = {
        "__WEBHOOK_URL__": WEBHOOK_URL or "",  # Replace with passed value or empty string
    }

    # Loop through all placeholders and replace them in the script text
    for placeholder, value in replacements.items():
        script = script.replace(placeholder, value)

    # Return the final PowerShell script with replacements applied
    return script

    # --- HOW TO ADD MULTIPLE VALUES ---
    # 1. Add extra function parameters, e.g.:
    #    def generate_setup(WEBHOOK_URL: str = None, ADMIN_EMAIL: str = None, SERVER_NAME: str = None) -> str:
    #
    # 2. Add new entries in the dictionary:
    #    replacements = {
    #        "__WEBHOOK_URL__": WEBHOOK_URL or "",
    #        "__ADMIN_EMAIL__": ADMIN_EMAIL or "",
    #        "__SERVER_NAME__": SERVER_NAME or "",
    #    }
    #
    # 3. Place matching placeholders in your PowerShell script where needed:
    #    $env:ADMIN_EMAIL = "__ADMIN_EMAIL__"
    #    $env:SERVER_NAME = "__SERVER_NAME__"
    #
    # When the function runs, all placeholders get replaced automatically.
