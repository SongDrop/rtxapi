# -----------------------------
# Download & Install AzCopy (custom URL, flattened to C:\Tools)
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
