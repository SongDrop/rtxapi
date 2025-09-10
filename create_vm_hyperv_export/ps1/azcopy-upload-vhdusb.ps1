# -----------------------------
# Upload VHD to Azure Storage with AzCopy (via cmd.exe)
# -----------------------------
# Ensure script runs as admin
If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script must be run as Administrator. Relaunching..."
    Start-Process powershell -Verb runAs -ArgumentList "-File `"$PSCommandPath`""
    Exit
}

# Path to local VHD
$localVHD = "C:\Users\source\Downloads\vhdusb\sxshdjue3-snapshot-fixed-bootable.vhd"

# Destination (example: storage account container with SAS token)
$destinationUrl = "https://<storageaccount>.blob.core.windows.net/<container>/<vhdname>.vhd?<SAS_TOKEN>"

# AzCopy directory
$azCopyDir = "C:\Program Files\AzCopy"
$azCopyExe = Join-Path $azCopyDir "azcopy.exe"

# Validate paths
if (-not (Test-Path $localVHD)) {
    Write-Error "Local VHD not found: $localVHD"
    Exit 1
}
if (-not (Test-Path $azCopyExe)) {
    Write-Error "AzCopy not installed. Run download-azcopy-github.ps1 first."
    Exit 1
}

Write-Host "Starting upload of $localVHD to Azure with AzCopy (cmd.exe)..."

try {
    # Build AzCopy command
    $cmd = "cd `"$azCopyDir`" && azcopy.exe copy `"$localVHD`" `"$destinationUrl`" --recursive"

    # Run inside cmd.exe
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -Wait -PassThru -NoNewWindow

    if ($process.ExitCode -eq 0) {
        Write-Host "Upload completed successfully."
    } else {
        Write-Error "AzCopy exited with code $($process.ExitCode). Upload failed."
    }
} catch {
    Write-Error "Upload failed: $_"
}
