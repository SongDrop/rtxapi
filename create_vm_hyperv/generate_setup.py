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
$installLog = "$logDir\setup_hyperv_log.txt"
try {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
} catch {
    Write-Warning "Failed to create log directory: $_"
}
Add-Content -Path $installLog -Value "=== Hyper-V Setup Script Started $(Get-Date) ==="

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
$helperPath = "C:\ProgramData\PostHyperVSetup.ps1"

# Create helper script content
$helperContent = @'
# Post-reboot Hyper-V setup script with watchdog for network profiles
# Post-reboot Hyper-V setup script with watchdog for network profiles
try {
    Write-Output "Starting PostHyperVSetup..."

# --- 0. Ensure script is running as Administrator ---
    if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Write-Warning "Script must be run as Administrator to modify protected registry keys."
        return
    }

# --- 1. Delay to allow system services to stabilize ---
    Start-Sleep -Seconds 5

# --- 2. Set all current network profiles to Private (API first) ---
    try {
        $profiles = @(Get-NetConnectionProfile | Select-Object InterfaceIndex, Name)
        foreach ($p in $profiles) {
            try {
                Set-NetConnectionProfile -InterfaceIndex $p.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue
                if ($p.Name) {
                    Write-Output "Set profile '$($p.Name)' to Private"
                } else {
                    Write-Output "Set unnamed profile (InterfaceIndex: $($p.InterfaceIndex)) to Private"
                }
            } catch { }
        }
    } catch {
        Write-Warning "Failed to set network profiles via Get-NetConnectionProfile: $_"
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

# --- 7. Set existing network profiles to Private via registry (fallback) ---
    try {
        $profilesPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
        if (Test-Path $profilesPath) {
            Get-ChildItem $profilesPath | ForEach-Object {
                try {
                    Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Force -ErrorAction SilentlyContinue
                    Write-Output "Forced registry profile to Private: $($_.PSChildName)"
                } catch { }
            }
        }
    } catch {
        Write-Warning "Failed to update registry network profiles: $_"
    }

# --- 8. Disable firewall notifications ---
    try {
        New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows Defender\Features" -Name "DisableAntiSpywareNotification" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
        New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Security Center\Notifications" -Name "DisableNotifications" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
        New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Notifications" -Name "DisableEnhancedNotifications" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
        Write-Output "Disabled firewall notifications (if permitted)"
    } catch {
        Write-Warning "Failed to update firewall notification settings: $_"
    }

# --- 9. Create Hyper-V Manager shortcut for all users ---
    try {
        $virt = "$env:windir\System32\virtmgmt.msc"
        if (Test-Path $virt) {
            $users = @(Get-ChildItem "C:\Users" -Directory | Where-Object { Test-Path "$($_.FullName)\NTUSER.DAT" })
            foreach ($u in $users) {
                $desk = Join-Path $u.FullName "Desktop"
                if (-not (Test-Path $desk)) { New-Item -Path $desk -ItemType Directory -Force | Out-Null }
                $sc = Join-Path $desk "Hyper-V Manager.lnk"
                $wsh = New-Object -ComObject WScript.Shell
                $link = $wsh.CreateShortcut($sc)
                $link.TargetPath = $virt
                $link.IconLocation = "$virt,0"
                $link.Save()
                Write-Output "Created shortcut for user: $($u.BaseName)"
            }
        }
    } catch {
        Write-Warning "Failed to create Hyper-V shortcut: $_"
    }

# --- 10. Safely enforce Private and restart NlaSvc if needed ---
    try {
        $profiles = @(Get-NetConnectionProfile | Select-Object InterfaceIndex, Name, NetworkCategory)
        $needRestartNla = $false
        foreach ($p in $profiles) {
            if ($p.NetworkCategory -ne "Private") { $needRestartNla = $true }
            try { Set-NetConnectionProfile -InterfaceIndex $p.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue } catch { }
        }

        $profilesPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
        if (Test-Path $profilesPath) {
            Get-ChildItem $profilesPath | ForEach-Object {
                try { Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Force -ErrorAction SilentlyContinue } catch { }
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
        Write-Warning "Failed to finalize network profiles or restart NlaSvc: $_"
    }

# --- 11. Install watchdog script for network enforcement ---
    try {
        $watchdogPath = "C:\ProgramData\EnforcePrivateNetworks.ps1"

        $watchdogContent = @"
# Enforce all network profiles to Private and disable NlaSvc safely
try {
    Write-Output 'Starting EnforcePrivateNetworks script...'

    # 1. Get all network profiles
    $profiles = Get-NetConnectionProfile | Select-Object -Property Name, InterfaceIndex
    foreach ($p in $profiles) {
        try {
            Set-NetConnectionProfile -InterfaceIndex $p.InterfaceIndex -NetworkCategory Private -ErrorAction Stop
            Write-Output "Set profile '$($p.Name)' to Private"
        } catch {
            Write-Warning "Failed to set profile '$($p.Name)': $_"
        }
    }

    # 2. Force all registry profiles to Private
    $profilesPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
    if (Test-Path $profilesPath) {
        Get-ChildItem $profilesPath | ForEach-Object {
            try {
                Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Force
                Write-Output "Registry forced Private for profile $($_.PSChildName)"
            } catch {
                Write-Warning "Failed to update registry for $($_.PSChildName): $_"
            }
        }
    }

    # 3. Stop and disable NlaSvc
    $nla = Get-Service "NlaSvc" -ErrorAction SilentlyContinue
    if ($nla) {
        try {
            Stop-Service "NlaSvc" -Force -ErrorAction Stop
            Set-Service "NlaSvc" -StartupType Disabled
            Write-Output "Stopped and disabled NlaSvc service"
        } catch {
            Write-Warning "Failed to stop or disable NlaSvc: $_"
        }
    } else {
        Write-Output "NlaSvc service not found"
    }

    Write-Output "EnforcePrivateNetworks script completed successfully."
} catch {
    Write-Warning "Script failed: $_"
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

# --- 12. Cleanup ---
    try {
        Unregister-ScheduledTask -TaskName "PostHyperVSetup" -Confirm:$false -ErrorAction SilentlyContinue
        if ($helperPath) { Remove-Item -Path "$helperPath" -Force -ErrorAction SilentlyContinue; Write-Output "Removed helper script: $helperPath" }
        Write-Output "Cleanup complete"
    } catch {
        Write-Warning "Cleanup failed: $_"
    }

    Write-Output "PostHyperVSetup completed successfully."
} catch {
    Write-Output "PostHyperVSetup encountered a fatal error: $_"
}
'@  # must be at column 0

try {
    $helperContent | Out-File -FilePath $helperPath -Encoding UTF8 -Force
    Add-Content -Path $installLog -Value "Wrote helper script to $helperPath"
} catch {
    Add-Content -Path $installLog -Value "Failed to write helper script: $_"
}

# Register scheduled task to run the helper once at startup
try {
    # Define the name of the scheduled task
    $taskName = "PostHyperVSetup"
    # Remove any existing task with the same name to avoid conflicts
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    # Define the action the scheduled task will perform: run PowerShell with the helper script
    $action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$helperPath`""
    # Set the trigger for the task: run at user AtStartup
    $trigger = New-ScheduledTaskTrigger -AtStartup
    # Define task settings with proper Windows version and description
    # Create a ScheduledTaskSettingsSet for Windows 10
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    # $settings.Description = "Post-Hyper-V setup script: configures network, disables popups, and creates Hyper-V Manager shortcut"
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

Notify-Webhook -Status "provisioning" -Step "enabling_hyperv" -Message "Enabling Windows Hyper-v"

# --Disable NlaSvc before reboot---
# Do NOT stop it immediately (causes timeout in provisioning)
Set-Service -Name "NlaSvc" -StartupType Disabled -ErrorAction SilentlyContinue

# --- Enable Hyper-V ---
try {
    $hyperVFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
    if ($hyperVFeature.State -ne "Enabled") {
        Notify-Webhook -Status "provisioning" -Step "hyperv_enable" -Message "Enabling Hyper-V..."
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -All -NoRestart
        Notify-Webhook -Status "info" -Step "hyperv_enable" -Message "Scheduled post-reboot continuation."
        Notify-Webhook -Status "provisioning" -Step "hyperv_restart" -Message "Restarting computer to complete Hyper-V installation..."
        Restart-Computer -Force
        exit
    } else {
        # --- RUN POST-HYPER-V HELPER IMMEDIATELY ---
        try {
            # Correctly get the collection of network profiles
            $profiles = Get-NetConnectionProfile
            # Set each profile to Private
            foreach ($profile in $profiles) {
                Set-NetConnectionProfile -InterfaceIndex $profile.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue
            }
            Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled False -ErrorAction SilentlyContinue
            $servicesToDisable = @("FDResPub","FDHost","UPnPHost","SSDPSRV","NlaSvc")
            foreach ($svc in $servicesToDisable) { Stop-Service $svc -Force -ErrorAction SilentlyContinue; Set-Service $svc -StartupType Disabled -ErrorAction SilentlyContinue }
            New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Network" -Name "NewNetworkWindowOff" -Value 1 -PropertyType DWord -Force | Out-Null
            New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_StdDomainUserSetLocation" -Value 1 -PropertyType DWord -Force | Out-Null
            New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_EnableNetSetupWizard" -Value 0 -PropertyType DWord -Force | Out-Null
            # Create Hyper-V Manager shortcut in Public Desktop (visible to all)
            $publicDesktop = "C:\Users\Public\Desktop"
            if (-not (Test-Path $publicDesktop)) { New-Item -Path $publicDesktop -ItemType Directory -Force | Out-Null }
            $shortcutPath = Join-Path $publicDesktop "Hyper-V Manager.lnk"
            $wsh = New-Object -ComObject WScript.Shell
            $sc = $wsh.CreateShortcut($shortcutPath)
            $sc.TargetPath = "$env:windir\System32\virtmgmt.msc"
            $sc.IconLocation = "$env:windir\System32\virtmgmt.msc,0"
            $sc.Save()
        } catch { Write-Warning "Failed to run helper immediately: $_" }
    }
} catch {
    Notify-Webhook -Status "failed" -Step "hyperv_enable" -Message "Hyper-V installation failed: $_"
    exit 1
}

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
