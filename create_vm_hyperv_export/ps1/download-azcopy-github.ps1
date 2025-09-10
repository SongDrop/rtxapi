# -----------------------------
# Download & Install AzCopy (GitHub latest release)
# -----------------------------
# Ensure script runs as admin
If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script must be run as Administrator. Relaunching..."
    Start-Process powershell -Verb runAs -ArgumentList "-File `"$PSCommandPath`""
    Exit
}

$azCopyDir = "C:\Program Files\AzCopy"
$azCopyExe = Join-Path $azCopyDir "azcopy.exe"
$tempZip   = "$env:TEMP\azcopy.zip"

# Create destination folder
if (-not (Test-Path $azCopyDir)) {
    New-Item -ItemType Directory -Path $azCopyDir -Force | Out-Null
}

# -----------------------------
# Download latest AzCopy from GitHub
# -----------------------------
try {
    Write-Host "Fetching latest AzCopy release info from GitHub..."
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/Azure/azure-storage-azcopy/releases/latest"
    $asset   = $release.assets | Where-Object { $_.name -match "windows.*zip" } | Select-Object -First 1
    if (-not $asset) { throw "Could not find AzCopy Windows zip asset in GitHub release." }

    Write-Host "Downloading AzCopy from $($asset.browser_download_url)"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tempZip -UseBasicParsing
} catch {
    Write-Error "Failed to download AzCopy from GitHub: $_"
    Exit 1
}

# -----------------------------
# Extract and install
# -----------------------------
try {
    Write-Host "Extracting AzCopy to $azCopyDir..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($tempZip, $azCopyDir, $true)

    if (-not (Test-Path $azCopyExe)) { throw "azcopy.exe not found after extraction." }

    # Add to PATH
    $env:PATH += ";$azCopyDir"
    [Environment]::SetEnvironmentVariable("PATH", $env:PATH, [EnvironmentVariableTarget]::Machine)

    Write-Host "AzCopy installed successfully at $azCopyExe"
} catch {
    Write-Error "Installation failed: $_"
} finally {
    if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
}
