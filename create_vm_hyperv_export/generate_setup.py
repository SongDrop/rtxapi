def generate_setup(WEBHOOK_URL: str = None, SNAPSHOT_URL: str = None, AZURE_SAS_TOKEN: str = None, VHD_SNAPSHOT_NAME: str = None) -> str:
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
$env:VHD_SNAPSHOT_NAME = "__VHD_SNAPSHOT_NAME__"


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
try {
    Write-Output "Starting PostHyperVSetup..."

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

    # --- 8. Create Hyper-V Manager shortcut for all users ---
    try {
        $virt = "$env:windir\System32\virtmgmt.msc"
        $publicDesktop = "C:\Users\Public\Desktop"
        if (Test-Path $virt) {
            if (-not (Test-Path $publicDesktop)) { New-Item -Path $publicDesktop -ItemType Directory -Force | Out-Null }
            $shortcutPath = Join-Path $publicDesktop "Hyper-V Manager.lnk"
            $wsh = New-Object -ComObject WScript.Shell
            $sc = $wsh.CreateShortcut($shortcutPath)
            $sc.TargetPath = $virt
            $sc.IconLocation = "$virt,0"
            $sc.Save()
            Write-Output "Created Hyper-V Manager shortcut in Public Desktop"
        }
    } catch {
        Write-Warning "Failed to create Hyper-V shortcut: $_"
    }

    # --- 9. Safely restart NlaSvc to enforce Private profiles ---
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

    # --- 10. Install watchdog script to enforce Private profiles ---
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

    Write-Output "PostHyperVSetup completed successfully."
} catch {
    Write-Output "PostHyperVSetup encountered a fatal error: $_"
}

    # --- 12. Cleanup ---
    try {
        Unregister-ScheduledTask -TaskName "PostHyperVSetup" -Confirm:$false -ErrorAction SilentlyContinue
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

    # -----------------------------
    # Post-Hyper-V Snapshot & VHD Automation
    # -----------------------------
    if ($env:SNAPSHOT_URL -and $env:SNAPSHOT_URL.Trim() -ne "") {

        # --- Folders Setup ---
        $userProfile = [Environment]::GetFolderPath("UserProfile")
        $snapshotDir = Join-Path $userProfile "Downloads"
        if (-not (Test-Path $snapshotDir)) { New-Item -Path $snapshotDir -ItemType Directory -Force | Out-Null }

        $vhdUSBDir = Join-Path $snapshotDir "vhdusb"
        if (-not (Test-Path $vhdUSBDir)) { New-Item -Path $vhdUSBDir -ItemType Directory -Force | Out-Null }

        # --- Snapshot / Fixed VHD Naming ---
        if ($env:VHD_SNAPSHOT_NAME -and $env:VHD_SNAPSHOT_NAME.Trim() -ne "") {
            $snapshotName = "$($env:VHD_SNAPSHOT_NAME).vhd"
            $fixedName    = "$($env:VHD_SNAPSHOT_NAME)_fixed_bootable236gb.vhd"
        } else {
            $snapshotName = "azure-os-disk.vhd"
            $fixedName    = "azure-os-disk_fixed_bootable236gb.vhd"
        }

        $snapshotVHD = Join-Path $snapshotDir $snapshotName
        $fixedVHD    = Join-Path $vhdUSBDir $fixedName

        Write-Host "Snapshot VHD path: $snapshotVHD"
        Write-Host "Fixed VHD path:    $fixedVHD"
        Write-Host "Fixed VHD folder:  $vhdUSBDir"

        # --- Tool URLs ---
        $azcopyURL  = "https://github.com/ProjectIGIRemakeTeam/azcopy-windows/releases/download/azcopy/AzCopyWin.zip"
        $sdeleteURL = "https://download.sysinternals.com/files/SDelete.zip"

        $downloadUrl  = $env:SNAPSHOT_URL
        $uploadUrl    = $env:AZURE_SAS_TOKEN
        $downloadPath = $snapshotVHD

        try {
            # -----------------------------
            # STEP 1: Download Snapshot (resumable)
            # -----------------------------
            Notify-Webhook -Status "provisioning" -Step "snapshot_download" -Message "Starting snapshot download"

            # Ensure wget is installed
            if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
                Write-Host "Installing Chocolatey..."
                Set-ExecutionPolicy Bypass -Scope Process -Force
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-Expression ((New-Object Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
                $env:PATH += ";C:\ProgramData\chocolatey\bin"
            }

            $wgetPath = "C:\ProgramData\chocolatey\bin\wget.exe"
            if (-not (Test-Path $wgetPath)) {
                Write-Host "Installing wget..."
                choco install wget -y
            }
            while (-not (Test-Path $wgetPath)) { Start-Sleep -Seconds 2 }

            # Download snapshot with retries
            $maxRetries = 50
            $retryDelay = 5
            $downloadSucceeded = $false

            for ($i=1; $i -le $maxRetries; $i++) {
                Write-Host "Download attempt $i/$maxRetries..."
                Notify-Webhook -Status "provisioning" -Step "snapshot_download" -Message "Download attempt $i"
                try {
                    & $wgetPath -c $downloadUrl -O $downloadPath
                    if (Test-Path $downloadPath) { $downloadSucceeded = $true; break }
                } catch { Write-Warning "wget attempt $i failed: $_" }
                Start-Sleep -Seconds $retryDelay
            }
            if (-not $downloadSucceeded) { throw "Failed to download snapshot after $maxRetries attempts." }

            Notify-Webhook -Status "provisioning" -Step "snapshot_download" -Message "Snapshot downloaded successfully"
            Write-Host "Snapshot downloaded to $downloadPath"

            # -----------------------------
            # STEP 2: Download & Extract AzCopy (custom URL, flattened to C:\Tools)
            # -----------------------------
            # Ensure admin
            If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
                [Security.Principal.WindowsBuiltInRole]::Administrator)) {
                Write-Warning "This script must be run as Administrator. Relaunching..."
                Start-Process powershell -Verb runAs -ArgumentList "-File `"$PSCommandPath`""
                Exit
            }

            $azCopyDir   = "C:\Tools"
            $azCopyExe   = Join-Path $azCopyDir "azcopy.exe"
            $tempZip     = Join-Path $env:TEMP ("AzCopyWin_{0}.zip" -f ([guid]::NewGuid().ToString()))
            $downloadUrl = "https://github.com/ProjectIGIRemakeTeam/azcopy-windows/releases/download/azcopy/AzCopyWin.zip"

            # Prepare folder
            if (-not (Test-Path $azCopyDir)) { New-Item -ItemType Directory -Path $azCopyDir -Force | Out-Null }

            # Download
            try {
                Write-Host "Downloading AzCopy..."
                $wc = New-Object System.Net.WebClient
                $wc.DownloadFile($downloadUrl, $tempZip)
                $wc.Dispose()
            } catch {
                Write-Error "Failed to download AzCopy: $_"
                Exit 1
            }

            # Extract & flatten
            try {
                Write-Host "Extracting AzCopy to $azCopyDir..."
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                $zip = [System.IO.Compression.ZipFile]::OpenRead($tempZip)

                foreach ($entry in $zip.Entries) {
                    # Strip top folder
                    $relativePath = $entry.FullName -replace "^[^/]+/", ""
                    if ([string]::IsNullOrWhiteSpace($relativePath)) { continue }

                    $destPath = Join-Path $azCopyDir $relativePath
                    $destDir  = Split-Path $destPath -Parent

                    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }

                    if ($entry.Name) {
                        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
                    }
                }

                $zip.Dispose()

                if (-not (Test-Path $azCopyExe)) { throw "azcopy.exe not found after extraction." }

                # Add to PATH if missing
                $currentPath = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::Machine)
                if ($currentPath -notlike "*$azCopyDir*") {
                    $newPath = "$currentPath;$azCopyDir"
                    [Environment]::SetEnvironmentVariable("PATH", $newPath, [EnvironmentVariableTarget]::Machine)
                }

                Write-Host "✅ AzCopy installed successfully at $azCopyExe"
                & $azCopyExe --version
            } catch {
                Write-Error "Extraction / Installation failed: $_"
            } finally {
                if ($zip) { $zip.Dispose() }
                if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
            }

            # -----------------------------
            # STEP 3: Install & Prepare sdelete
            # -----------------------------
            $toolsDir = "C:\Tools"
            if (-not (Test-Path $toolsDir)) { New-Item -Path $toolsDir -ItemType Directory | Out-Null }
            $sdeleteZip = Join-Path $toolsDir "SDelete.zip"
            Invoke-WebRequest -Uri $sdeleteURL -OutFile $sdeleteZip -UseBasicParsing
            Expand-Archive -Path $sdeleteZip -DestinationPath $toolsDir -Force
            Remove-Item $sdeleteZip -Force

            $sdeletePath = Get-ChildItem -Path $toolsDir -Recurse -Filter "sdelete.exe" | Select-Object -First 1 -ExpandProperty FullName
            # ✅ Unblock to avoid the manual click
            Unblock-File -Path $sdeletePath
            if (-not (Test-Path $sdeletePath)) { throw "sdelete.exe not found" }
            Write-Host "sdelete installed at: $sdeletePath"

            # -----------------------------
            # STEP 4: Ensure Admin & Hyper-V Module
            # -----------------------------
            if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
                throw "Script must be run as Administrator"
            }
            Import-Module Hyper-V -ErrorAction Stop

            # -----------------------------
            # STEP 5: Validate VHDs
            # -----------------------------
            if (-not (Test-Path $snapshotVHD)) { throw "Snapshot VHD not found: $snapshotVHD" }
            if (Test-Path $fixedVHD) { Remove-Item $fixedVHD -Force }

            # -----------------------------
            # STEP 6: Convert to Fixed VHD
            # -----------------------------
            Write-Host "Converting snapshot to fixed VHD..."
            Convert-VHD -Path $snapshotVHD -DestinationPath $fixedVHD -VHDType Fixed -ErrorAction Stop
            if (-not (Test-Path $fixedVHD)) { throw "Convert-VHD did not produce output file" }
            Write-Host "Created fixed VHD: $fixedVHD"

            # -----------------------------
            # STEP 7: Mount VHD & Assign Drive Letters
            # -----------------------------
            Mount-VHD -Path $fixedVHD -ErrorAction Stop
            Start-Sleep -Seconds 5

            $vhdInfo = Get-VHD -Path $fixedVHD
            $diskNumber = $vhdInfo.DiskNumber
            $disk = Get-Disk -Number $diskNumber

            Set-Disk -Number $diskNumber -IsOffline $false -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2

            $partitions = Get-Partition -DiskNumber $diskNumber
            if (-not $partitions) { throw "No partitions found on mounted VHD" }

            $assignedLetters = @()
            function Get-FreeDriveLetter {
                $used = (Get-Volume | Where-Object DriveLetter).DriveLetter
                foreach ($letter in [char[]](90..68)) { if ($letter -notin $used) { return $letter } }
                throw "No free drive letters"
            }

            foreach ($partition in $partitions) {
                if (-not $partition.DriveLetter) {
                    $letter = Get-FreeDriveLetter
                    Set-Partition -DiskNumber $diskNumber -PartitionNumber $partition.PartitionNumber -NewDriveLetter $letter
                    $assignedLetters += @{DiskNumber=$diskNumber; PartitionNumber=$partition.PartitionNumber; DriveLetter=$letter}
                }
            }

            # Detect OS partition
            $osDrive = ($partitions | Where-Object { $_.DriveLetter -and (Test-Path ("$($_.DriveLetter):\Windows")) }).DriveLetter
            if (-not $osDrive) { $osDrive = ($partitions | Where-Object DriveLetter | Select-Object -First 1).DriveLetter }
            $drivePath = "$osDrive:\"
            Write-Host "OS partition detected on drive $drivePath"

            # -----------------------------
            # STEP 8: Zero Free Space
            # -----------------------------
            if (Test-Path $sdeletePath) {
                Write-Host "Zeroing free space with sdelete..."
                $proc = Start-Process -FilePath $sdeletePath -ArgumentList "-z", "$osDrive:"  "-accepteula" -NoNewWindow -Wait -PassThru
                if ($proc.ExitCode -ne 0) { Write-Warning "sdelete failed, falling back to cipher"; Start-Process cipher.exe -ArgumentList "/w:$drivePath" -NoNewWindow -Wait }
            } else {
                Start-Process cipher.exe -ArgumentList "/w:$drivePath" -NoNewWindow -Wait
            }

            # -----------------------------
            # STEP 9: Cleanup - Remove Drive Letters & Dismount
            # -----------------------------
            foreach ($assignment in $assignedLetters) {
                Remove-PartitionAccessPath -DiskNumber $assignment.DiskNumber -PartitionNumber $assignment.PartitionNumber -AccessPath "$($assignment.DriveLetter):\" -ErrorAction SilentlyContinue
            }
            Dismount-VHD -Path $fixedVHD -ErrorAction SilentlyContinue

            # -----------------------------
            # STEP 10: Compact VHD
            # -----------------------------
            Write-Host "Compacting VHD..."
            Optimize-VHD -Path $fixedVHD -Mode Full -ErrorAction SilentlyContinue

            # -----------------------------
            # STEP 11: Report Size
            # -----------------------------
            $sizeGB = [math]::Round((Get-Item $fixedVHD).Length / 1GB, 2)
            Write-Host "Final VHD size: $sizeGB GB"
            Write-Host "Output file: $fixedVHD"

            # -----------------------------
            # STEP 12: Upload via AzCopy
            # -----------------------------
            Notify-Webhook -Status "provisioning" -Step "vhd_upload" -Message "Uploading fixed VHD via AzCopy..."
            # -----------------------------
            # Upload VHD to Azure Storage with AzCopy (via cmd.exe)
            # -----------------------------

            # Ensure script runs as admin
            If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
                Write-Warning "This script must be run as Administrator. Relaunching..."
                Start-Process powershell -Verb runAs -ArgumentList "-File `"$PSCommandPath`""
                Exit
            }

            # Path to local VHD (localVHD has to be inside a FOLDER as azcopy upload --recursive)
            $localVHD = "$fixedVHD"

            # Destination (example: storage account container with SAS token)
            $destinationUrl = "$AZURE_SAS_TOKEN"

            # AzCopy directory (flattened to Tools)
            $azCopyDir = "C:\Tools"
            $azCopyExe = Join-Path $azCopyDir "azcopy.exe"

            # Validate paths
            if (-not (Test-Path $localVHD)) {
                Write-Error "❌ Local VHD not found: $localVHD"
                Exit 1
            }
            if (-not (Test-Path $azCopyExe)) {
                Write-Error "❌ AzCopy not installed. Run download-azcopy-github.ps1 first."
                Exit 1
            }

            Write-Host "🚀 Starting upload of $localVHD to Azure with AzCopy (cmd.exe)..."

            try {
                # Build AzCopy command
                $cmd = "cd `"$azCopyDir`" && azcopy.exe copy `"$localVHD`" `"$destinationUrl`" --recursive"

                # Run inside cmd.exe
                $process = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -Wait -PassThru -NoNewWindow

                if ($process.ExitCode -eq 0) {
                    Write-Host "✅ Upload completed successfully."
                } else {
                    Write-Error "❌ AzCopy exited with code $($process.ExitCode). Upload failed."
                }
            } catch {
                Write-Error "❌ Upload failed: $_"
            }
            Notify-Webhook -Status "success" -Step "setup_finished" -Message "Hyper-V setup and VHD processing completed successfully"

            # -----------------------------
            # STEP 0: Download and install rclone (optional)
            # -----------------------------
            # $toolsDir = "C:\Tools"
            # if (-not (Test-Path $toolsDir)) { New-Item -Path $toolsDir -ItemType Directory | Out-Null }

            # $rcloneZip = Join-Path $toolsDir "rclone.zip"
            # $rcloneUrl = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"

            # Write-Host "Downloading rclone..."
            # Invoke-WebRequest -Uri $rcloneUrl -OutFile $rcloneZip -UseBasicParsing

            # Write-Host "Extracting rclone..."
            # Expand-Archive -Path $rcloneZip -DestinationPath $toolsDir -Force

            # $rclonePath = Get-ChildItem -Path $toolsDir -Recurse -Filter "rclone.exe" | Select-Object -First 1 -ExpandProperty FullName
            # if (-not (Test-Path $rclonePath)) { Write-Error "rclone installation failed"; exit 1 }
            # Write-Host "✅ rclone installed successfully at: $rclonePath"

            # # -----------------------------
            # # STEP 1: Configure Backblaze B2 remote automatically
            # # -----------------------------
            # $remoteName = "b2remote"
            # $bucketName = "my-bucket-name"        # Change this to your bucket
            # $appKeyId   = "YOUR_APP_KEY_ID"       # Replace with your key ID
            # $appKey     = "YOUR_APP_KEY"          # Replace with your application key

            # # Create rclone config file if it doesn't exist
            # $rcloneConfigDir = "$env:USERPROFILE\.config\rclone"
            # if (-not (Test-Path $rcloneConfigDir)) { New-Item -Path $rcloneConfigDir -ItemType Directory | Out-Null }
            # $rcloneConfigFile = Join-Path $rcloneConfigDir "rclone.conf"

            # # Add B2 remote configuration
            # $configText = @"
            # [$remoteName]
            # type = b2
            # account = $appKeyId
            # key = $appKey
            # endpoint =
            # "@

            # # If config exists, append or replace the remote
            # if (Test-Path $rcloneConfigFile) {
            #     # Remove old remote if exists
            #     (Get-Content $rcloneConfigFile) -notmatch "^\[$remoteName\]" | Set-Content $rcloneConfigFile
            #     Add-Content -Path $rcloneConfigFile -Value $configText
            # } else {
            #     $configText | Out-File -FilePath $rcloneConfigFile -Encoding ASCII
            # }
            # Write-Host "✅ Backblaze B2 remote '$remoteName' configured successfully."

            # # -----------------------------
            # # STEP 2: Upload file to B2
            # # -----------------------------
            # $remotePath = "$remoteName:$bucketName/vhds/"

            # Write-Host "Uploading $fixedVHD to Backblaze B2..."
            # $cmd = "`"$rclonePath`" copy `"$fixedVHD`" `"$remotePath`" --progress"
            # $proc = Start-Process -FilePath cmd.exe -ArgumentList "/c $cmd" -Wait -PassThru -NoNewWindow

            # if ($proc.ExitCode -eq 0) {
            #     Write-Host "✅ Upload to B2 completed successfully."
            # } else {
            #     Write-Error "❌ rclone upload to B2 failed with code $($proc.ExitCode)"
            # }
        } catch {
            Write-Error "Post-Hyper-V steps failed: $_"
            Notify-Webhook -Status "failed" -Step "hyperv_process" -Message "Post-Hyper-V steps failed: $_"
            exit 1
        }

    } else {
        Write-Output "No snapshot URL provided, skipping VHD processing"
        Notify-Webhook -Status "provisioning" -Step "no_snapshot" -Message "No snapshot URL provided"
    }

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
        "__SNAPSHOT_URL__": SNAPSHOT_URL or "",
        "__AZURE_SAS_TOKEN__": AZURE_SAS_TOKEN or "",
        "__VHD_SNAPSHOT_NAME__": VHD_SNAPSHOT_NAME or "",
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
