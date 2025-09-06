def generate_setup(WEBHOOK_URL: str = None, SNAPSHOT_URL: str = None, AZURE_SAS_TOKEN: str = None) -> str:
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
$env:SNAPSHOT_URL = "__SNAPSHOT_URL__"
$env:AZURE_SAS_TOKEN = "__AZURE_SAS_TOKEN__"

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
# Post-reboot setup script
try {
    # Force all current network profiles to Private
    Get-NetConnectionProfile | ForEach-Object { Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue }
    Restart-Service netprofm -Force -ErrorAction SilentlyContinue
    Restart-Service NlaSvc -Force -ErrorAction SilentlyContinue

    # Disable Network Discovery firewall rules
    Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled False -ErrorAction SilentlyContinue

    # Stop discovery-related services
    $servicesToDisable = @("FDResPub","FDHost","UPnPHost","SSDPSRV")
    foreach ($svc in $servicesToDisable) {
        Stop-Service $svc -Force -ErrorAction SilentlyContinue
        Set-Service $svc -StartupType Disabled -ErrorAction SilentlyContinue
    }

    # Disable network location wizard
    New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Network" -Name "NewNetworkWindowOff" -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_StdDomainUserSetLocation" -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections" -Name "NC_EnableNetSetupWizard" -Value 0 -PropertyType DWord -Force | Out-Null

    # Set existing network profiles to Private
    $profilesPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
    if (Test-Path $profilesPath) {
        Get-ChildItem $profilesPath | ForEach-Object {
            Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Force -ErrorAction SilentlyContinue
        }
    }

    # Disable Network Location Awareness service
    Stop-Service "NlaSvc" -Force -ErrorAction SilentlyContinue
    Set-Service "NlaSvc" -StartupType Disabled -ErrorAction SilentlyContinue

    # Disable Network Discovery globally
    Set-NetFirewallRule -Group "@FirewallAPI.dll,-32752" -Enabled False -ErrorAction SilentlyContinue
    Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled False -ErrorAction SilentlyContinue

    # Disable firewall notifications
    New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows Defender\Features" -Name "DisableAntiSpywareNotification" -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Security Center\Notifications" -Name "DisableNotifications" -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Notifications" -Name "DisableEnhancedNotifications" -Value 1 -PropertyType DWord -Force | Out-Null

    # Create Hyper-V Manager shortcut for all users
    $virt="$env:windir\System32\virtmgmt.msc"
    if (Test-Path $virt) {
        $users=Get-ChildItem "C:\Users" -Directory | Where-Object { Test-Path "$($_.FullName)\NTUSER.DAT" }
        foreach ($u in $users) {
            $desk=Join-Path $u.FullName "Desktop"
            if (-not (Test-Path $desk)) { New-Item -Path $desk -ItemType Directory -Force | Out-Null }
            $sc=Join-Path $desk "Hyper-V Manager.lnk"
            $wsh=New-Object -ComObject WScript.Shell
            $link=$wsh.CreateShortcut($sc)
            $link.TargetPath=$virt
            $link.IconLocation="$virt,0"
            $link.Save()
        }
    }

    # Cleanup
    Unregister-ScheduledTask -TaskName "PostHyperVSetup" -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -Path "$helperPath" -Force -ErrorAction SilentlyContinue
} catch { 
    Write-Output "PostHyperVSetup encountered an error: $_" 
}
'@

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
    # Set the trigger for the task: run at user logon
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    # Define task settings with proper Windows version and description
    # [Microsoft.PowerShell.ScheduledJob.TaskCompatibility] enum value, valid enum values are:
    # V1 – Windows XP / Server 2003
    # V2 – Windows Vista / Server 2008
    # V2_1 – Windows 7 / Server 2008 R2
    # V2_2 – Windows 8 / Server 2012
    # V2_3 – Windows 8.1 / Server 2012 R2
    # V2_4 – Windows 10 / Server 2016+
    $settings = New-ScheduledTaskSettingsSet -Compatibility V2_4 -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    $settings.Description = "Post-Hyper-V setup script: configures network, disables popups, and creates Hyper-V Manager shortcut"
    $settings.Author = "Windows 10 Developer"
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
            Get-NetConnectionProfile | ForEach-Object { Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue }
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

            # --- Extra Steps After Hyper-V ---
            if ("__SNAPSHOT_URL__" -ne "") {
                $userProfile = [Environment]::GetFolderPath("UserProfile")
                $snapshotDir = Join-Path $userProfile "Downloads"
                if (-not (Test-Path $snapshotDir)) { New-Item -Path $snapshotDir -ItemType Directory -Force | Out-Null }

                $snapshotPath = Join-Path $snapshotDir "azure-os-disk.vhd"
                $fixedVHD = Join-Path $snapshotDir "azure-os-disk_fixed.vhd"
                $azcopyZip = Join-Path $snapshotDir "AzCopyWin.zip"

                try {
                    ####STEP-1: DOWNLOAD SNAPSHOT
                    Notify-Webhook -Status "provisioning" -Step "snapshot_download" -Message "Downloading snapshot from __SNAPSHOT_URL__..."
                    Invoke-WebRequest -Uri "__SNAPSHOT_URL__" -OutFile $snapshotPath -UseBasicParsing
                    if (-not (Test-Path $snapshotPath)) { throw "Snapshot download failed" }
                    Notify-Webhook -Status "provisioning" -Step "snapshot_download" -Message "Snapshot downloaded to $snapshotPath"
                    ####STEP-2: CREATE BOOTABLE FIXED VHD
                    Notify-Webhook -Status "provisioning" -Step "hyperv_finalize" -Message "Creating bootable fixed VHD..."
                    Import-Module Hyper-V -ErrorAction Stop
                    Convert-VHD -Path $snapshotPath -DestinationPath $fixedVHD -VHDType Fixed
                    if (-not (Test-Path $fixedVHD)) { throw "Fixed VHD creation failed" }
                    Notify-Webhook -Status "provisioning" -Step "hyperv_finalize" -Message "Bootable fixed VHD created at $fixedVHD"
                     ####STEP-3: DOWNLOAD AZCOPY
                    Notify-Webhook -Status "provisioning" -Step "azcopy_download" -Message "Downloading AzCopy..."
                    Invoke-WebRequest -Uri "https://github.com/ProjectIGIRemakeTeam/azcopy-windows/releases/download/azcopy/AzCopyWin.zip" -OutFile $azcopyZip -UseBasicParsing
                    Expand-Archive -Path $azcopyZip -DestinationPath $snapshotDir -Force
                    Remove-Item $azcopyZip -Force
                    Notify-Webhook -Status "provisioning" -Step "azcopy_download" -Message "AzCopy downloaded and extracted"
                    ####STEP-4: UPLOAD FIXED VHD VIA AZCOPY
                    $azcopyExe = Join-Path $snapshotDir "AzCopy\azcopy.exe"
                    Notify-Webhook -Status "provisioning" -Step "vhd_upload" -Message "Uploading fixed VHD via AzCopy..."
                    # Run AzCopy using cmd.exe
                    $cmdArgs = "/c `"$azcopyExe copy `"$fixedVHD`" `$env:AZURE_SAS_TOKEN --recursive`""
                    Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -Wait -NoNewWindow
                    Notify-Webhook -Status "provisioning" -Step "vhd_upload" -Message "Fixed VHD uploaded successfully"
                    ####STEP-4: UPLOAD SUCCESSFULLY FINISHED 

                    #########################################
                    ### We turned our cloud based Windows 10
                    ### virtual machine into a fixed-size
                    ### bootable .vhd which can be downloaded
                    ### via a https link and ready to put it
                    ### on a usb pendrive
                    ######################################### 

                    Notify-Webhook -Status "success" -Step "setup_finished" -Message "Hyper-V setup and VHD upload completed successfully"
                } catch {
                    Notify-Webhook -Status "failed" -Step "hyperv_process" -Message "Post-Hyper-V steps failed: $_"
                    exit 1
                }
            }
        } catch { 
            Write-Warning "Failed to run helper immediately: $_" 
        }
    }
} catch {
    Notify-Webhook -Status "failed" -Step "hyperv_enable" -Message "Hyper-V installation failed: $_"
    exit 1
}

Add-Content -Path $installLog -Value "Setup script completed at $(Get-Date)"

Notify-Webhook -Status "provisioning" -Step "windows_setup_completed" -Message "Setup script completed at $(Get-Date)"

'''
    # Dictionary of placeholders -> values to insert into the script.
    # You can add more entries here later if needed (e.g., __ADMIN_EMAIL__, __SERVER_NAME__).
    replacements = {
        "__WEBHOOK_URL__": WEBHOOK_URL or "",  # Replace with passed value or empty string
        "__SNAPSHOT_URL__": SNAPSHOT_URL or "",
        "__AZURE_SAS_TOKEN__": AZURE_SAS_TOKEN or ""
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
