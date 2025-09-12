# -----------------------------
# Auto Download Script with Wget and Resume
# -----------------------------

# Ensure script runs as admin
If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script must be run as Administrator. Relaunching..."
    Start-Process powershell -Verb runAs -ArgumentList "-File `"$PSCommandPath`""
    Exit
}

# Set the download URL and output path
$downloadUrl = "https://md-bk2ctq4w2l35.z19.blob.storage.azure.net/wvvv4n5hpvhz/abcd?sv=2018-03-28&sr=b&si=b824311c-853b-4d89-8a5c-77693183dd31&sig=pJS3s0%2Bx3URIidAoTIa9pKwcC4wT02Dza%2FIB3SEs94o%3D"
$downloadPath = "$env:USERPROFILE\Downloads\sxshdjue3-snapshot-1757506900.vhd"

# -----------------------------
# Install Chocolatey if not present
# -----------------------------
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
}

# Ensure Chocolatey commands are on the path
$env:PATH += ";C:\ProgramData\chocolatey\bin"

# -----------------------------
# Install Wget if not present
# -----------------------------
$wgetPath = "C:\ProgramData\chocolatey\bin\wget.exe"
if (-not (Test-Path $wgetPath)) {
    Write-Host "Installing wget..."
    choco install wget -y
}

# Wait until wget exists
while (-not (Test-Path $wgetPath)) {
    Write-Host "Waiting for wget to be installed..."
    Start-Sleep -Seconds 2
}

# -----------------------------
# Download with resume and retries
# -----------------------------
if (Test-Path $downloadPath) {
    Write-Host "Resuming existing download..."
} else {
    Write-Host "Starting new download..."
}

$maxRetries = 500
$retryDelay = 5 # seconds

for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
    Write-Host "Attempt $attempt of $maxRetries..."
    try {
        $process = Start-Process $wgetPath -ArgumentList "-c `"$downloadUrl`" -O `"$downloadPath`"" -Wait -PassThru
        if ($process.ExitCode -eq 0) {
            Write-Host "Download completed successfully."
            break
        } else {
            Write-Warning "Download failed on attempt $attempt. Retrying in $retryDelay seconds..."
            Start-Sleep -Seconds $retryDelay
        }
    } catch {
        Write-Warning "Error on attempt $attempt $_. Retrying in $retryDelay seconds..."
        Start-Sleep -Seconds $retryDelay
    }
}

if (-not (Test-Path $downloadPath)) {
    Write-Error "Download failed after $maxRetries attempts."
}
 
