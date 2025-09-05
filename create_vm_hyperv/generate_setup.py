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
        $msg = ("Failed to set registry value {{0}}\\\\{{1}}: {{2}}" -f $Path, $Name, $_)
        Write-Warning $msg
        Add-Content -Path $installLog -Value $msg
    }}
}}

# --- SYSTEM CLEANUP & DEBLOAT (HKLM + SYSTEM) ---
$systemKeys = @{{ 
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Setup\\State" = @{{ "ImageState" = 7; "OOBEInProgress" = 0; "SetupPhase" = 0; "SystemSetupInProgress" = 0 }}
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\OOBE" = @{{ "PrivacyConsentStatus" = 1; "DisablePrivacyExperience" = 1; "SkipMachineOOBE" = 1; "SkipUserOOBE" = 1 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\OOBE" = @{{ "DisablePrivacyExperience" = 1 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search" = @{{ "AllowCortana" = 0 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge" = @{{ "HideFirstRunExperience" = 1 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU" = @{{ "NoAutoUpdate" = 1 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" = @{{ "NoConnectedUser" = 3 }}
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" = @{{ "AllowTelemetry" = 0 }}
    "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Remote Assistance" = @{{ "fAllowToGetHelp" = 0 }}
    "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Network Connections" = @{{ "NC_ShowSharedAccessUI" = 0 }}
    "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Network" = @{{ "NewNetworkWindowOff" = 1; "Category" = 1 }}
}}

# Force networks to Private where possible
try {{
    Get-NetConnectionProfile | ForEach-Object {{
        try {{ Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue }} catch {{ }}
    }}
}} catch {{ }}

# Apply systemKeys to registry
foreach ($path in $systemKeys.Keys) {{
    foreach ($kv in $systemKeys[$path].GetEnumerator()) {{
        Set-RegistryValue -Path $path -Name $kv.Key -Value $kv.Value
    }}
}}

# Stop SYSTEM services
$services = @("WSearch","DiagTrack","WerSvc")
foreach ($svc in $services) {{
    try {{ Stop-Service $svc -Force -ErrorAction SilentlyContinue }} catch {{ }}
    try {{ Set-Service $svc -StartupType Disabled }} catch {{ }}
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
            }} catch {{ }}
        }}
    }}
}}

# --- Post-reboot helper script ---
$helperPath = "C:\\ProgramData\\PostHyperVSetup.ps1"
$helperContent = @'
try {{
    # --- NETWORK: FORCE PRIVATE & SILENT ---
    Get-NetConnectionProfile | ForEach-Object {{
        Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private -ErrorAction SilentlyContinue
    }}
    # Disable Network Discovery firewall rules
    Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled False -ErrorAction SilentlyContinue
    # Stop discovery services
    $servicesToDisable = @("FDResPub","FDHost","UPnPHost","SSDPSRV")
    foreach ($svc in $servicesToDisable) {{
        Stop-Service $svc -Force -ErrorAction SilentlyContinue
        Set-Service $svc -StartupType Disabled -ErrorAction SilentlyContinue
    }}
    # Registry to suppress network prompts
    $profilesPath = "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\NetworkList\\Profiles"
    if (Test-Path $profilesPath) {{
        Get-ChildItem $profilesPath | ForEach-Object {{
            Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Force -ErrorAction SilentlyContinue
        }}
    }}
    New-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Network" -Name "NewNetworkWindowOff" -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Network Connections" -Name "NC_ShowSharedAccessUI" -Value 0 -PropertyType DWord -Force | Out-Null

    # Suppress "Network location" prompt
    $profilesPath = "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\NetworkList\\Profiles"
    if (Test-Path $profilesPath) {{
        Get-ChildItem $profilesPath | ForEach-Object {{
            Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Force -ErrorAction SilentlyContinue
            New-ItemProperty -Path $_.PSPath -Name "NetworkCategory" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue
        }}
    }}

    # Disable "Network Discovery" globally
    Set-NetFirewallRule -Group "@FirewallAPI.dll,-32752" -Enabled False -ErrorAction SilentlyContinue
    Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled False -ErrorAction SilentlyContinue

    # Registry hardening
    New-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Network" -Name "NewNetworkWindowOff" -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Network Connections" -Name "NC_ShowSharedAccessUI" -Value 0 -PropertyType DWord -Force | Out-Null

    # --- Suppress network and system notifications ---
    New-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings" -Name "NOC_GLOBAL_SETTING_TOASTS_ENABLED" -Value 0 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name "EnableBalloonTips" -Value 0 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer" -Name "NoWelcomeScreen" -Value 1 -PropertyType DWord -Force | Out-Null

    # Create Hyper-V Manager shortcut
    $publicDesktop = "C:\\Users\\Public\\Desktop"
    if (-not (Test-Path $publicDesktop)) {{ New-Item -Path $publicDesktop -ItemType Directory -Force | Out-Null }}
    $shortcutPath = Join-Path $publicDesktop "Hyper-V Manager.lnk"
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($shortcutPath)
    $sc.TargetPath = "$env:windir\\System32\\virtmgmt.msc"
    $sc.IconLocation = "$env:windir\\System32\\virtmgmt.msc,0"
    $sc.Save()

    # Cleanup
    Unregister-ScheduledTask -TaskName "PostHyperVSetup" -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -Path "$helperPath" -Force -ErrorAction SilentlyContinue
}} catch {{ Write-Output "PostHyperVSetup encountered an error: $_" }}
'@

# Write helper script to disk
try {{
    $helperContent | Out-File -FilePath $helperPath -Encoding UTF8 -Force
    Add-Content -Path $installLog -Value "Wrote helper script to $helperPath"
}} catch {{
    Add-Content -Path $installLog -Value "Failed to write helper script: $_"
}}

# Register scheduled task to run the helper once at startup as SYSTEM
try {{
    $taskName = "PostHyperVSetup"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$helperPath`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
    Add-Content -Path $installLog -Value "Registered scheduled task $taskName to run $helperPath at startup"
}} catch {{
    Add-Content -Path $installLog -Value "Failed to register scheduled task: $_"
}}

# --- Enable Hyper-V ---
try {{
    $hyperVFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
    if ($hyperVFeature.State -ne "Enabled") {{
        Notify-Webhook -Status "provisioning" -Step "hyperv_enable" -Message "Enabling Hyper-V..."
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -All -NoRestart
        Notify-Webhook -Status "info" -Step "hyperv_enable" -Message "Scheduled post-reboot continuation."
        Notify-Webhook -Status "provisioning" -Step "hyperv_restart" -Message "Restarting computer to complete Hyper-V installation..."
        Restart-Computer -Force
        exit
    }} else {{
        Notify-Webhook -Status "provisioning" -Step "hyperv_enable" -Message "Hyper-V already enabled."
        # Create shortcut immediately if Hyper-V already enabled
        $publicDesktopNow = "C:\\Users\\Public\\Desktop"
        if (-not (Test-Path $publicDesktopNow)) {{ New-Item -Path $publicDesktopNow -ItemType Directory -Force | Out-Null }}
        $shortcutPathNow = Join-Path $publicDesktopNow "Hyper-V Manager.lnk"
        $targetNow = "$env:windir\\System32\\virtmgmt.msc"
        $wshNow = New-Object -ComObject WScript.Shell
        $scNow = $wshNow.CreateShortcut($shortcutPathNow)
        $scNow.TargetPath = $targetNow
        $scNow.IconLocation = "$env:windir\\System32\\virtmgmt.msc,0"
        $scNow.Save()
    }}
}} catch {{
    Notify-Webhook -Status "failed" -Step "hyperv_enable" -Message "Hyper-V installation failed: $_"
    exit 1
}}

Add-Content -Path $installLog -Value "Setup script completed at $(Get-Date)"
'''
    return script