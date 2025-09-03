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

# --- Log setup ---
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

    if (-not (Test-Path $Path)) {{
        try {{
            New-Item -Path $Path -Force | Out-Null
        }} catch {{
            $msg = ("Failed to create registry path {{0}}: {{1}}" -f $Path, $_)
            Write-Warning $msg
            Add-Content -Path $installLog -Value $msg
            return
        }}
    }}

    try {{
        New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType $Type -Force | Out-Null
    }} catch {{
        $msg = ("Failed to set registry value {{0}}\\{{1}}: {{2}}" -f $Path, $Name, $_)
        Write-Warning $msg
        Add-Content -Path $installLog -Value $msg
    }}
}}

# --- SYSTEM CLEANUP & DEBLOAT (HKLM + SYSTEM) ---
$systemKeys = @{{ 
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Setup\\State" = @{{ 
        "ImageState" = 7
        "OOBEInProgress" = 0
        "SetupPhase" = 0
        "SystemSetupInProgress" = 0
    }}
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\OOBE" = @{{ 
        "PrivacyConsentStatus" = 1
        "DisablePrivacyExperience" = 1
        "SkipMachineOOBE" = 1
        "SkipUserOOBE" = 1
    }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\OOBE" = @{{ 
        "DisablePrivacyExperience" = 1
    }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search" = @{{ "AllowCortana" = 0 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge" = @{{ "HideFirstRunExperience" = 1 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU" = @{{ "NoAutoUpdate" = 1 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" = @{{ "NoConnectedUser" = 3 }}
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" = @{{ "AllowTelemetry" = 0 }}
    "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Remote Assistance" = @{{ "fAllowToGetHelp" = 0 }}

    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Network Connections" = @{{ "NC_ShowSharedAccessUI" = 0 }}
    "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Network\\NewNetworkWindowOff" = @{{}}
    "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Network" = @{{ "Category" = 1 }}

}}

Get-NetConnectionProfile | ForEach-Object {{
    try {{
        Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue
    }} catch {{}}
}}

foreach ($path in $systemKeys.Keys) {{
    foreach ($kv in $systemKeys[$path].GetEnumerator()) {{
        Set-RegistryValue -Path $path -Name $kv.Key -Value $kv.Value
    }}
}}

# Stop SYSTEM services
$services = @("WSearch","DiagTrack","WerSvc")
foreach ($svc in $services) {{
    try {{ Stop-Service $svc -Force -ErrorAction SilentlyContinue }} catch {{}}
    try {{ Set-Service $svc -StartupType Disabled }} catch {{}}
}}

# --- USER CLEANUP & DEBLOAT (HKCU) ---
$hkcuProfiles = Get-ChildItem "C:\\Users" -Directory | Where-Object {{ Test-Path "$($_.FullName)\\NTUSER.DAT" }}

$userKeys = @(
    @{{Path="Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager"; Values=@{{"RotatingLockScreenEnabled"=0;"RotatingLockScreenOverlayEnabled"=0;"SubscribedContent-338388Enabled"=0;"SubscribedContent-310093Enabled"=0;"SystemPaneSuggestionsEnabled"=0;"SubscribedContent-SettingsEnabled"=0;"SubscribedContent-AppsEnabled"=0;"SubscribedContent-338387Enabled"=0}}}},
    @{{Path="Software\\Microsoft\\OneDrive"; Values=@{{"DisableFirstRun"=1}}}},
    @{{Path="Software\\Microsoft\\Xbox"; Values=@{{"ShowFirstRunUI"=0}}}},
    @{{Path="Software\\Microsoft\\GameBar"; Values=@{{"ShowStartupPanel"=0}}}},
    @{{Path="Software\\Microsoft\\Office\\16.0\\Common\\General"; Values=@{{"ShownFirstRunOptIn"=1}}}},
    @{{Path="Software\\Microsoft\\Office\\16.0\\Common\\Internet"; Values=@{{"SignInOptions"=3}}}},
    @{{Path="Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\feedbackhub"; Values=@{{"Value"=2}}}},
    @{{Path="Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer"; Values=@{{"PeopleBand"=0}}}},
    @{{Path="Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced"; Values=@{{"TaskbarDa"=0;"EnableBalloonTips"=0}}}},
    @{{Path="Software\\Microsoft\\Windows\\CurrentVersion\\Pen"; Values=@{{"PenWorkspaceButton"=0}}}},
    @{{Path="Software\\Microsoft\\Windows\\CurrentVersion\\Appx"; Values=@{{"DisabledByPolicy"=1}}}},
    @{{Path="Software\\Policies\\Microsoft\\WindowsStore"; Values=@{{"AutoDownload"=2}}}},
    @{{Path="Software\\Microsoft\\Windows\\CurrentVersion\\PushNotifications"; Values=@{{"NoToastApplicationNotification"=1}}}}
)

foreach ($profile in $hkcuProfiles) {{
    foreach ($key in $userKeys) {{
        foreach ($kv in $key.Values.GetEnumerator()) {{
            try {{
                $fullPath = "HKU:\\$($profile.SID)\\$($key.Path)"
                if (-not (Test-Path $fullPath)) {{ New-Item -Path $fullPath -Force | Out-Null }}
                Set-RegistryValue -Path $fullPath -Name $kv.Key -Value $kv.Value
            }} catch {{}}
        }}
    }}
}}

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
        Notify-Webhook -Status "provisioning" -Step "hyperv_enable" -Message "Hyper-V already enabled."
    }}
}} catch {{
    Notify-Webhook -Status "failed" -Step "hyperv_enable" -Message "Hyper-V installation failed: $_"
    exit 1
}}
# --- Create Hyper-V Manager shortcut on desktop ---
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Hyper-V Manager.lnk"
$targetPath = "$env:windir\\System32\\virtmgmt.msc"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.IconLocation = "$env:windir\\System32\\virtmgmt.msc,0"
$shortcut.Save()
'''
    return script
