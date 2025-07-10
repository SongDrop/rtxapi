def generate_setup(PC_NAME: str, DOMAIN_NAME: str, SSL_EMAIL: str, PIN_CODE: str = "123456") -> str:
    safe_pc_name = PC_NAME.replace('"', '`"')
    safe_domain = DOMAIN_NAME.replace('"', '`"')
    safe_pin = PIN_CODE.replace('"', '`"')

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
Start-Transcript -Path "$env:TEMP\SetupScript.log" -Append

$NewComputerName = "{safe_pc_name}"
$DomainName = "{safe_domain}"

# Reset sunshine uuid 
try {{
    Write-Host "Running resetsunshine with Computer Name: $NewComputerName"
    $process = Start-Process -FilePath "C:\Windows\resetsunshine.exe" -Wait -PassThru
    if ($process.ExitCode -ne 0) {{
        throw "resetsunshine failed with exit code $($process.ExitCode)"
    }}
    Write-Host "resetsunshine completed successfully"
}} catch {{
    Write-Warning "Failed to run resetsunshine: $_"
}}

# Install VC++ Redistributable
try {{
    $vcRedistUrl = "https://github.com/SongDrop/dumbdropwindows/releases/download/windows/VC_redist.x64.exe"
    $vcRedistPath = "$env:TEMP\VC_redist.x64.exe"
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

# Download and install DumbDrop
try {{
    $dumbdropUrl = "https://github.com/SongDrop/dumbdropwindows/releases/download/windows/DumbDrop.exe"
    $dumbdropInstallDir = "C:\Program Files\DumbDrop"
    $dumbdropExePath = Join-Path -Path $dumbdropInstallDir -ChildPath "DumbDrop.exe"
    
    Write-Host "Downloading DumbDrop.exe..."
    Invoke-WebRequest -Uri $dumbdropUrl -OutFile "$env:TEMP\DumbDrop.exe" -UseBasicParsing
    
    Write-Host "Installing DumbDrop..."
    if (-not (Test-Path -Path $dumbdropInstallDir)) {{
        New-Item -Path $dumbdropInstallDir -ItemType Directory -Force | Out-Null
    }}
    Copy-Item -Path "$env:TEMP\DumbDrop.exe" -Destination $dumbdropExePath -Force
    
    # Create shortcut on desktop
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut("$env:Public\Desktop\DumbDrop.lnk")
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

# Rename computer
try {{
    if ($env:COMPUTERNAME -ne $NewComputerName) {{
        Write-Host "Renaming computer from $env:COMPUTERNAME to $NewComputerName"
        Rename-Computer -NewName $NewComputerName -Force
        
        Write-Host "Restarting computer to apply changes..."
        Start-Sleep -Seconds 5
        Restart-Computer -Force
    }} else {{
        Write-Host "Computer already has the correct name"
    }}
}} catch {{
    Write-Error "Failed to rename computer: $_"
    exit 1
}}

Stop-Transcript

'''
    return script
