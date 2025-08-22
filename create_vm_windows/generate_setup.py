def generate_setup(PC_NAME: str, DOMAIN_NAME: str, SSL_EMAIL: str, PIN_CODE: str = "123456", NEW_PASSWORD: str = None) -> str:
    safe_pc_name = PC_NAME.replace('"', '`"')
    safe_domain = DOMAIN_NAME.replace('"', '`"')
    safe_pin = PIN_CODE.replace('"', '`"')
    safe_password = NEW_PASSWORD.replace('"', '`"') if NEW_PASSWORD and NEW_PASSWORD.strip() != "" else None
    
    superf4_url = "https://github.com/SongDrop/SuperF4/releases/download/1.0/SuperF4.zip"
    vc_redist_url = "https://github.com/SongDrop/dumbdropwindows/releases/download/windows/VC_redist.x64.exe"
    reset_sunshine_url = "https://github.com/SongDrop/resetsunshine/releases/download/v1.0/resetsunshine.exe"
    dumbdrop_url = "https://github.com/SongDrop/dumbdropwindows/releases/download/windows/DumbDrop.exe"
    
    # New URLs for the images to replace
    force_quit_img_url = "https://github.com/SongDrop/win10dev/raw/main/forcequit.png"
    restart_img_url = "https://github.com/SongDrop/win10dev/raw/main/restart.png"

    # --- NEW: Caddy Downloads ---
    caddy_url = "https://github.com/caddyserver/caddy/releases/download/v2.7.6/caddy_2.7.6_windows_amd64.zip"
    winsw_url = "https://github.com/winsw/winsw/releases/download/v3.0.0-alpha.11/WinSW-x64.exe"

    password_change_script = ""
    if safe_password:
        password_change_script = f'''
        try {{
            $UserName = "source"
            Write-Host "Changing password for user $UserName"

            $NewPassword = "{safe_password}"

            if (Get-Command Set-LocalUser -ErrorAction SilentlyContinue) {{
                $securePass = ConvertTo-SecureString $NewPassword -AsPlainText -Force
                Set-LocalUser -Name $UserName -Password $securePass
                Write-Host "Password changed successfully using Set-LocalUser."
                Add-Content -Path "C:\\Program Files\\Logs\\install_log.txt" -Value "[SUCCESS] Password for user '$UserName' changed."
            }}
            else {{
                $changePasswordOutput = net user $UserName $NewPassword 2>&1
                Write-Host "net user output: $changePasswordOutput"
                if ($LASTEXITCODE -ne 0) {{
                    Write-Warning "Password change failed with exit code $LASTEXITCODE"
                    Add-Content -Path "C:\\Program Files\\Logs\\install_log.txt" -Value "[ERROR] Password change failed with exit code $LASTEXITCODE"
                    throw "Password change failed"
                }}
                else {{
                    Write-Host "Password changed successfully using net user."
                    Add-Content -Path "C:\\Program Files\\Logs\\install_log.txt" -Value "[SUCCESS] Password for user '$UserName' changed via net user."
                }}
            }}
        }}
        catch {{
            Write-Warning "Failed to change password: $_"
            Add-Content -Path "C:\\Program Files\\Logs\\install_log.txt" -Value "[ERROR] Password change failed: $_"
            throw
        }}
        '''
    else:
        password_change_script = ""

    # --- NEW: Caddy Configuration String ---
    caddy_config = f'''
    # Caddyfile for {safe_pc_name}.{safe_domain}
    # HTTP to HTTPS redirect for all hosts
    {{
        email {SSL_EMAIL}
        auto_https disable_redirects
    }}

    # Route for DumbDrop
    drop.{safe_pc_name}.{safe_domain} {{
        reverse_proxy localhost:3475
        log {{
            output file "C:\\Caddy\\logs\\dumbdrop.log"
        }}
    }}

    # Route for Sunshine PIN and UI
    pin.{safe_pc_name}.{safe_domain} {{
        reverse_proxy localhost:47990
        log {{
            output file "C:\\Caddy\\logs\\sunshine.log"
        }}
    }}
    '''
    
    script = f'''# Check for admin privileges and relaunch as admin if needed
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    Write-Host "Not running as Administrator. Relaunching as admin..."
    $scriptPath = if ($MyInvocation.MyCommand.Definition) {{
        $MyInvocation.MyCommand.Definition
    }} else {{
        $PSCommandPath
    }}
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"{0}`"" -f $scriptPath
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -Verb RunAs -PassThru -Wait
    exit $process.ExitCode
}}

# Set error handling and logging
$ErrorActionPreference = "Stop"
$logDir = "C:\\Program Files\\Logs"
$installLog = "$logDir\\install_log.txt"
$transcriptLog = "$env:TEMP\\SetupScript.log"

# Create log directory
New-Item -Path $logDir -ItemType Directory -Force -ErrorAction SilentlyContinue | Out-Null
Start-Transcript -Path $transcriptLog -Append
Write-Host "SCRIPT STARTED. Params: PC=${{NewComputerName}}, Domain=${{DomainName}}"
Add-Content -Path $installLog -Value "=== Setup Script Started $(Get-Date) ==="
Add-Content -Path $installLog -Value "Target Computer Name: {safe_pc_name}"
Add-Content -Path $installLog -Value "Target Domain: {safe_domain}"

$NewComputerName = "{safe_pc_name}"
$DomainName = "{safe_domain}"

# Install VC++ Redistributable
try {{
    Add-Content -Path $installLog -Value "Starting VC++ Redist installation..."
    $vcRedistUrl = "{vc_redist_url}"
    $vcRedistPath = "$env:TEMP\\VC_redist.x64.exe"
    Write-Host "Downloading VC_redist.x64.exe..."
    Invoke-WebRequest -Uri $vcRedistUrl -OutFile $vcRedistPath -UseBasicParsing
    
    Write-Host "Installing VC_redist.x64.exe..."
    $installArgs = @(
        "/install",
        "/quiet",
        "/norestart"
    )
    $process = Start-Process -FilePath $vcRedistPath -ArgumentList $installArgs -Wait -PassThru
    if ($process.ExitCode -ne 0) {{
        Write-Warning "VC++ installation returned exit code $($process.ExitCode)"
        Add-Content -Path $installLog -Value "[WARNING] VC++ install exit code: $($process.ExitCode)"
    }} else {{
        Add-Content -Path $installLog -Value "[SUCCESS] VC++ Redist installed."
    }}
}} catch {{
    Write-Warning "VC++ Redist installation failed: $_"
    Add-Content -Path $installLog -Value "[ERROR] VC++ Redist install failed: $_"
}}

# --- NEW: INSTALL AND CONFIGURE CADDY ---
try {{
    Add-Content -Path $installLog -Value "Starting Caddy installation..."
    $caddyDir = "C:\\Caddy"
    $caddyZipPath = "$env:TEMP\\caddy.zip"
    $caddyExePath = "$caddyDir\\caddy.exe"
    $winswExePath = "$caddyDir\\caddy-service.exe"
    $caddyfilePath = "$caddyDir\\Caddyfile"
    $winswConfigPath = "$caddyDir\\caddy-service.xml"

    Write-Host "Creating Caddy directory..."
    New-Item -Path $caddyDir -ItemType Directory -Force -ErrorAction Stop | Out-Null

    Write-Host "Downloading Caddy..."
    Invoke-WebRequest -Uri "{caddy_url}" -OutFile $caddyZipPath -UseBasicParsing

    Write-Host "Downloading WinSW..."
    Invoke-WebRequest -Uri "{winsw_url}" -OutFile $winswExePath -UseBasicParsing

    Write-Host "Extracting Caddy..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($caddyZipPath, $caddyDir)

    Write-Host "Creating Caddyfile..."
    @'
{caddy_config}
'@ | Out-File -FilePath $caddyfilePath -Encoding utf8

    Write-Host "Creating WinSW XML configuration..."
    @'
<service>
  <id>caddy</id>
  <name>Caddy Web Server</name>
  <description>Fast and extensible multi-platform web server with automatic HTTPS.</description>
  <executable>C:\Caddy\caddy.exe</executable>
  <arguments>run --config C:\Caddy\Caddyfile --adapter caddyfile</arguments>
  <log mode="roll"></log>
  <workingdirectory>C:\Caddy</workingdirectory>
</service>
'@ | Out-File -FilePath $winswConfigPath -Encoding utf8

    Write-Host "Installing Caddy service..."
    & $winswExePath install
    Start-Sleep -Seconds 2

    Write-Host "Starting Caddy service..."
    & $winswExePath start
    Start-Sleep -Seconds 3 # Give it a moment to start

    # Check if service is running
    $service = Get-Service -Name "caddy" -ErrorAction SilentlyContinue
    if ($service.Status -eq 'Running') {{
        Write-Host "Caddy service installed and started successfully."
        Add-Content -Path $installLog -Value "[SUCCESS] Caddy service is running."
    }} else {{
        Write-Warning "Caddy service may not have started correctly. Status: $($service.Status)"
        Add-Content -Path $installLog -Value "[WARNING] Caddy service status: $($service.Status)"
    }}

    # Open necessary firewall ports
    Write-Host "Configuring Windows Firewall for Caddy (HTTP/HTTPS)..."
    netsh advfirewall firewall add rule name="Caddy HTTP (80)" dir=in action=allow protocol=TCP localport=80
    netsh advfirewall firewall add rule name="Caddy HTTPS (443)" dir=in action=allow protocol=TCP localport=443
    Add-Content -Path $installLog -Value "Firewall rules added for ports 80 and 443."

}} catch {{
    Write-Warning "Caddy installation failed: $_"
    Add-Content -Path $installLog -Value "[ERROR] Caddy install failed: $_"
}}
# --- END CADDY INSTALLATION ---

# Download and install resetsunshine
try {{
    Add-Content -Path $installLog -Value "Starting Sunshine reset process..."
    $sunshineUrl = "{reset_sunshine_url}"
    $sunshineInstallDir = "C:\\Program Files\\Sunshine"
    $sunshineExePath = Join-Path -Path $sunshineInstallDir -ChildPath "resetsunshine.exe"

    # Delete existing resetsunshine.exe if it exists
    if (Test-Path -Path $sunshineExePath) {{
        Write-Host "Deleting existing resetsunshine.exe..."
        Remove-Item -Path $sunshineExePath -Force -ErrorAction SilentlyContinue
    }}

    Write-Host "Downloading resetsunshine.exe..."
    if (-not (Test-Path -Path $sunshineInstallDir)) {{
        New-Item -Path $sunshineInstallDir -ItemType Directory -Force | Out-Null
    }}
    Invoke-WebRequest -Uri $sunshineUrl -OutFile $sunshineExePath -UseBasicParsing

    Write-Host "Running resetsunshine.exe from $sunshineExePath"
    & $sunshineExePath 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) {{
        throw "resetsunshine failed with exit code $LASTEXITCODE"
    }}
    Write-Host "resetsunshine completed successfully"
    Add-Content -Path $installLog -Value "[SUCCESS] resetsunshine executed."
}} catch {{
    Write-Warning "Failed to download or run resetsunshine: $_"
    Add-Content -Path $installLog -Value "[ERROR] resetsunshine failed: $_"
}}

# Replace Sunshine web assets
try {{
    Add-Content -Path $installLog -Value "Starting Sunshine asset replacement..."
    $sunshineAssetsDir = "C:\\Program Files\\Sunshine\\assets"
    $forceQuitPath = Join-Path -Path $sunshineAssetsDir -ChildPath "forcequit.png"
    $restartPath = Join-Path -Path $sunshineAssetsDir -ChildPath "restart.png"

    Write-Host "Replacing Sunshine web assets..."

    # Ensure assets directory exists
    if (-not (Test-Path -Path $sunshineAssetsDir)) {{
        New-Item -Path $sunshineAssetsDir -ItemType Directory -Force | Out-Null
        Add-Content -Path $installLog -Value "Created assets directory: $sunshineAssetsDir"
    }}

    # Download and replace forcequit.png
    Invoke-WebRequest -Uri "{force_quit_img_url}" -OutFile $forceQuitPath -UseBasicParsing
    Add-Content -Path $installLog -Value "Downloaded/Replaced: $forceQuitPath"

    # Download and replace restart.png
    Invoke-WebRequest -Uri "{restart_img_url}" -OutFile $restartPath -UseBasicParsing
    Add-Content -Path $installLog -Value "Downloaded/Replaced: $restartPath"

    Write-Host "Sunshine assets replaced successfully."
    Add-Content -Path $installLog -Value "[SUCCESS] Sunshine web assets replaced."

}} catch {{
    Write-Warning "Failed to replace Sunshine assets: $_"
    Add-Content -Path $installLog -Value "[ERROR] Sunshine asset replacement failed: $_"
}}

# Stop DumbDrop if it's already running
try {{
    $processes = Get-Process -Name "DumbDrop" -ErrorAction SilentlyContinue
    if ($processes) {{
        Write-Host "Stopping existing DumbDrop processes..."
        Stop-Process -Name "DumbDrop" -Force -ErrorAction SilentlyContinue
        Write-Host "DumbDrop processes stopped."
    }} else {{
        Write-Host "No existing DumbDrop process found."
    }}
}} catch {{
    Write-Warning "Failed to stop DumbDrop: $_"
}}

# Download and install DumbDrop
try {{
    Add-Content -Path $installLog -Value "Starting DumbDrop installation..."
    $dumbdropUrl = "{dumbdrop_url}"
    $dumbdropInstallDir = "C:\\Program Files\\DumbDrop"
    $dumbdropExePath = Join-Path -Path $dumbdropInstallDir -ChildPath "DumbDrop.exe"
    
    Write-Host "Downloading DumbDrop.exe..."
    Invoke-WebRequest -Uri $dumbdropUrl -OutFile "$env:TEMP\\DumbDrop.exe" -UseBasicParsing
    
    Write-Host "Installing DumbDrop..."
    if (-not (Test-Path -Path $dumbdropInstallDir)) {{
        New-Item -Path $dumbdropInstallDir -ItemType Directory -Force | Out-Null
    }}
    Copy-Item -Path "$env:TEMP\\DumbDrop.exe" -Destination $dumbdropExePath -Force
    
    # Create shortcut on desktop
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut("$env:Public\\Desktop\\DumbDrop.lnk")
    $Shortcut.TargetPath = $dumbdropExePath
    $Shortcut.Arguments = "{safe_pin}"
    $Shortcut.WorkingDirectory = $dumbdropInstallDir
    $Shortcut.WindowStyle = 1
    $Shortcut.Description = "DumbDrop"
    $Shortcut.Save()
    Write-Host "Shortcut created on Desktop."
    Add-Content -Path $installLog -Value "DumbDrop shortcut created."
    
    # Schedule DumbDrop to run once at next login - USING SYSTEM ACCOUNT FOR RELIABILITY
    Write-Host "Scheduling DumbDrop to run at next user login..."
    $taskName = "RunDumbDropOnce"
    Write-Host "Configuring scheduled task: $taskName"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    $action = New-ScheduledTaskAction -Execute $dumbdropExePath -Argument "{safe_pin}"
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Runs DumbDrop once at user logon" -Force
    Write-Host "DumbDrop scheduled task recreated successfully."
    Add-Content -Path $installLog -Value "[SUCCESS] DumbDrop scheduled task created (SYSTEM account)."

}} catch {{
    Write-Warning "DumbDrop installation failed: $_"
    Add-Content -Path $installLog -Value "[ERROR] DumbDrop install failed: $_"
}}

# Stop SuperF4 if it's already running
try {{
    $processes = Get-Process -Name "SuperF4" -ErrorAction SilentlyContinue
    if ($processes) {{
        Write-Host "Stopping existing SuperF4 processes..."
        Stop-Process -Name "SuperF4" -Force -ErrorAction SilentlyContinue
        Write-Host "SuperF4 processes stopped."
    }} else {{
        Write-Host "No existing SuperF4 process found."
    }}
}} catch {{
    Write-Warning "Failed to stop SuperF4: $_"
}}

# Download and install SuperF4
try {{
    Add-Content -Path $installLog -Value "Starting SuperF4 installation..."
    $superf4Url = "{superf4_url}"
    $superf4InstallDir = "C:\\Program Files\\SuperF4"
    $superf4ZipPath = "$env:TEMP\\SuperF4.zip"
    $superf4ExePath = Join-Path -Path $superf4InstallDir -ChildPath "SuperF4.exe"
    $superf4IniPath = Join-Path -Path $superf4InstallDir -ChildPath "SuperF4.ini"
    
    Write-Host "Downloading SuperF4 ZIP package..."
    Invoke-WebRequest -Uri $superf4Url -OutFile $superf4ZipPath -UseBasicParsing
    
    # Create installation directory if it doesn't exist
    if (-not (Test-Path -Path $superf4InstallDir)) {{
        New-Item -Path $superf4InstallDir -ItemType Directory -Force | Out-Null
    }}
    
    # Extract ZIP contents
    Write-Host "Extracting SuperF4 files..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($superf4ZipPath, $superf4InstallDir)
    
    # Verify both files were extracted
    if (-not (Test-Path -Path $superf4ExePath)) {{
        throw "SuperF4.exe not found in the extracted files"
    }}
    if (-not (Test-Path -Path $superf4IniPath)) {{
        Write-Warning "SuperF4.ini not found in the extracted files (this might be expected)"
        Add-Content -Path $installLog -Value "[INFO] SuperF4.ini was not in the package."
    }}
    
    # Create desktop shortcut
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut("$env:Public\\Desktop\\SuperF4.lnk")
    $Shortcut.TargetPath = $superf4ExePath
    $Shortcut.WorkingDirectory = $superf4InstallDir
    $Shortcut.Save()
    Write-Host "SuperF4 shortcut created on Desktop."
    Add-Content -Path $installLog -Value "SuperF4 shortcut created."
    
    # Schedule SuperF4 to run at startup - USING SYSTEM ACCOUNT FOR RELIABILITY
    $taskName = "SuperF4"
    Write-Host "Configuring scheduled task: $taskName"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    $taskAction = New-ScheduledTaskAction -Execute $superf4ExePath
    $taskTrigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $taskTrigger -Principal $principal -Settings $settings -Description "Runs SuperF4 on user logon" -Force
    Write-Host "SuperF4 scheduled task recreated successfully."
    Add-Content -Path $installLog -Value "[SUCCESS] SuperF4 scheduled task created (SYSTEM account)."
    
    # Clean up temporary files
    Remove-Item -Path $superf4ZipPath -Force -ErrorAction SilentlyContinue
    Add-Content -Path $installLog -Value "[SUCCESS] SuperF4 installed."

}}catch {{
    Write-Warning "SuperF4 installation failed: $_"
    Add-Content -Path $installLog -Value "[ERROR] SuperF4 install failed: $_"
}}

$needRestart = $false

{password_change_script}

# Rename computer
try {{
    if ($env:COMPUTERNAME -ne $NewComputerName) {{
        Write-Host "Renaming computer from $env:COMPUTERNAME to $NewComputerName"
        Add-Content -Path $installLog -Value "Renaming computer from $env:COMPUTERNAME to $NewComputerName"
        Rename-Computer -NewName $NewComputerName -Force
        $needRestart = $true
        Add-Content -Path $installLog -Value "[SUCCESS] Computer rename scheduled. Restart required."
    }} else {{
        Write-Host "Computer already has the correct name"
        Add-Content -Path $installLog -Value "Computer name already correct: $NewComputerName"
    }}
}} catch {{
    Write-Error "Failed to rename computer: $_"
    Add-Content -Path $installLog -Value "[ERROR] Failed to rename computer: $_"
    exit 1
}}

# Final log entry and transcript stop
Add-Content -Path $installLog -Value "=== Setup Script Finished $(Get-Date) ==="
Add-Content -Path $installLog -Value "Need Restart: $needRestart"
Write-Host "Installation log saved to: $installLog"
Stop-Transcript

if ($needRestart) {{
    Write-Host "Restarting computer to apply changes..."
    Add-Content -Path $installLog -Value "Initiating system restart..."
    Start-Sleep -Seconds 2
    Restart-Computer -Force
}}
'''

    return script