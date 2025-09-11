# -----------------------------
# Upload folder (including VHD) to Azure Storage via AzCopy
# -----------------------------

# Ensure script runs as admin
If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script must be run as Administrator. Relaunching..."
    Start-Process powershell -Verb runAs -ArgumentList "-File `"$PSCommandPath`""
    Exit
}

# Path to local VHD (this can change each run)
$localVHD = "C:\Users\source\Downloads\vhdusb\sxshdjue3-snapshot-fixed-bootable.vhd"
# Dynamically get the folder containing the VHD
$localFolder = Split-Path -Path $localVHD -Parent
# Destination URL with SAS token
$destinationUrl = "https://vhdvm.blob.core.windows.net/vhdvm?se=2025-09-11T10%3A45%3A04Z&sp=rcwl&sv=2025-07-05&sr=c&sig=CTnbWDwwxfN4KBt%2B0Nb5Xs6uA8TjW0NL%2BGgv8a5/UuQ%3D"

# AzCopy executable
$azCopyExe = "C:\Tools\azcopy.exe"

# Validate paths
if (-not (Test-Path $localFolder)) {
    Write-Error "❌ Local folder not found: $localFolder"
    Exit 1
}
if (-not (Test-Path $azCopyExe)) {
    Write-Error "❌ AzCopy not installed. Run download-azcopy-github.ps1 first."
    Exit 1
}

Write-Host "🚀 Starting upload of folder '$localFolder' to Azure..."

# Build argument list safely
$args = @("copy", "$localFolder", $destinationUrl, "--recursive=true")

# Start process
$process = New-Object System.Diagnostics.Process
$process.StartInfo.FileName = $azCopyExe
$process.StartInfo.Arguments = $args -join " "
$process.StartInfo.RedirectStandardOutput = $true
$process.StartInfo.RedirectStandardError  = $true
$process.StartInfo.UseShellExecute = $false
$process.StartInfo.CreateNoWindow = $true

# Event handlers for real-time output
$process.OutputDataReceived += { if ($_ -and $_.Data) { Write-Host $_.Data } }
$process.ErrorDataReceived  += { if ($_ -and $_.Data) { Write-Host "Error: " + $_.Data } }

# Start process
$process.Start() | Out-Null
$process.BeginOutputReadLine()
$process.BeginErrorReadLine()
$process.WaitForExit()

if ($process.ExitCode -eq 0) {
    Write-Host "✅ Upload completed successfully."
} else {
    Write-Error "❌ AzCopy exited with code $($process.ExitCode). Upload failed."
}
