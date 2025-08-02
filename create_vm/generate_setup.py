def generate_setup(PC_NAME: str, DOMAIN_NAME: str, SSL_EMAIL: str, PIN_CODE: str = "123456", NEW_PASSWORD: str = None) -> str:
    safe_pc_name = PC_NAME.replace('"', '`"')
    safe_domain = DOMAIN_NAME.replace('"', '`"')
    safe_pin = PIN_CODE.replace('"', '`"')
    safe_password = NEW_PASSWORD.replace('"', '`"') if NEW_PASSWORD and NEW_PASSWORD.strip() != "" else None
    #
    superf4_url = "https://github.com/SongDrop/SuperF4/releases/download/1.0/SuperF4.zip"
    vc_redist_url = "https://github.com/SongDrop/dumbdropwindows/releases/download/windows/VC_redist.x64.exe"
    reset_sunshine_url = "https://github.com/SongDrop/resetsunshine/releases/download/v1.0/resetsunshine.exe"
    dumbdrop_url = "https://github.com/SongDrop/dumbdropwindows/releases/download/windows/DumbDrop.exe"

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
    }}
    else {{
        $changePasswordOutput = net user $UserName $NewPassword 2>&1
        Write-Host "net user output: $changePasswordOutput"
        if ($LASTEXITCODE -ne 0) {{
            Write-Warning "Password change failed with exit code $LASTEXITCODE"
            throw "Password change failed"
        }}
        else {{
            Write-Host "Password changed successfully using net user."
        }}
    }}
}}
catch {{
    Write-Warning "Failed to change password: $_"
    throw
}}
'''
    else:
        password_change_script = ""

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

# Set error handling
$ErrorActionPreference = "Stop"
Start-Transcript -Path "$env:TEMP\\SetupScript.log" -Append

$NewComputerName = "{safe_pc_name}"
$DomainName = "{safe_domain}"

# Install VC++ Redistributable
try {{
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
    }}
}} catch {{
    Write-Warning "VC++ Redist installation failed: $_"
}}

# Download and install resetsunshine
try {{
    $sunshineUrl = "{reset_sunshine_url}"
    $sunshineInstallDir = "C:\\Program Files\\Sunshine"
    $sunshineExePath = Join-Path -Path $sunshineInstallDir -ChildPath "resetsunshine.exe"

    Write-Host "Downloading resetsunshine.exe..."
    if (-not (Test-Path -Path $sunshineInstallDir)) {{
        New-Item -Path $sunshineInstallDir -ItemType Directory -Force | Out-Null
    }}
    Invoke-WebRequest -Uri $sunshineUrl -OutFile $sunshineExePath -UseBasicParsing

    Write-Host "Running resetsunshine.exe from $sunshineExePath"
    $process = Start-Process -FilePath $sunshineExePath -Wait -PassThru
    if ($process.ExitCode -ne 0) {{
        throw "resetsunshine failed with exit code $($process.ExitCode)"
    }}
    Write-Host "resetsunshine completed successfully"
}} catch {{
    Write-Warning "Failed to download or run resetsunshine: $_"
}}

# Download and install DumbDrop
try {{
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
    
    # Schedule DumbDrop to run once at next login
    Write-Host "Scheduling DumbDrop to run at next user login..."
    $action = New-ScheduledTaskAction -Execute $dumbdropExePath -Argument "{safe_pin}"
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName "RunDumbDropOnce" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -RunLevel Highest -Force
    Write-Host "DumbDrop will start at next login."

}} catch {{
    Write-Warning "DumbDrop installation failed: $_"
}}

# Download and install SuperF4
try {{
    $superf4Url = "{superf4_url}"
    $superf4InstallDir = "C:\Program Files\SuperF4"
    $superf4ZipPath = "$env:TEMP\SuperF4.zip"
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
        Write-Warning "SuperF4.init not found in the extracted files (this might be expected)"
    }}
    
    # Create desktop shortcut
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut("$env:Public\Desktop\SuperF4.lnk")
    $Shortcut.TargetPath = $superf4ExePath
    $Shortcut.WorkingDirectory = $superf4InstallDir
    $Shortcut.Save()
    Write-Host "SuperF4 shortcut created on Desktop."
    
    # Schedule SuperF4 to run at startup
    $taskAction = New-ScheduledTaskAction -Execute $superf4ExePath
    $taskTrigger = New-ScheduledTaskTrigger -AtLogOn
    Register-ScheduledTask -TaskName "SuperF4" -Action $taskAction -Trigger $taskTrigger -RunLevel Highest -Force
    Write-Host "SuperF4 will start automatically at login."
    
    # Clean up temporary files
    Remove-Item -Path $superf4ZipPath -Force -ErrorAction SilentlyContinue

}}catch {{
    Write-Warning "SuperF4 installation failed: $_"
}}

$needRestart = $false

{password_change_script}

# Rename computer
try {{
    if ($env:COMPUTERNAME -ne $NewComputerName) {{
        Write-Host "Renaming computer from $env:COMPUTERNAME to $NewComputerName"
        Rename-Computer -NewName $NewComputerName -Force
        $needRestart = $true
    }} else {{
        Write-Host "Computer already has the correct name"
    }}
}} catch {{
    Write-Error "Failed to rename computer: $_"
    exit 1
}}

if ($needRestart) {{
    Write-Host "Restarting computer to apply changes..."
    Start-Sleep -Seconds 5
    Restart-Computer -Force
}}

Stop-Transcript
'''

    return script