# -----------------------------
# Auto Download Script with Wget and Resume
# -----------------------------
# Set the download URL and output path
$downloadUrl = "https://md-bk2ctq4w2l35.z19.blob.storage.azure.net/wvvv4n5hpvhz/abcd?sv=2018-03-28&sr=b&si=b824311c-853b-4d89-8a5c-77693183dd31&sig=pJS3s0%2Bx3URIidAoTIa9pKwcC4wT02Dza%2FIB3SEs94o%3D"
$downloadPath = "$env:USERPROFILE\Downloads\sxshdjue3-snapshot-1757506900.vhd"

#region Parameters
$snapshotVHD    = "C:\Users\source\Downloads\sxshdjue3-snapshot-1757506900.vhd"
$dynamicVHDX    = "C:\Users\source\Downloads\sxshdjue3-snapshot-1757506900-dynamic-vhd.vhdx"
$fixedAzureVHD  = "C:\Users\source\Downloads\vhdusb\sxshdjue3-snapshot-1757506900-fixed-bootable.vhd"
$OverwriteFixedVHD = $true
$targetSizeGB   = 220

# Set the azcopy
$azCopyDir   = "C:\Tools"
$azCopyExe   = Join-Path $azCopyDir "azcopy.exe"
$tempZip     = Join-Path $env:TEMP ("AzCopyWin_{0}.zip" -f ([guid]::NewGuid().ToString()))
$downloadUrl = "https://github.com/ProjectIGIRemakeTeam/azcopy-windows/releases/download/azcopy/AzCopyWin.zip"

# Destination UPLOAD_URL_SAS_TOKEN (example: storage account container with SAS token)
$destinationUrl = "AZURE_SAS_TOKEN"


# Ensure script runs as admin
If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script must be run as Administrator. Relaunching..."
    Start-Process powershell -Verb runAs -ArgumentList "-File `"$PSCommandPath`""
    Exit
}


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
 
# ============================================================
# Optimized VHD Conversion with Defrag & Compact Techniques
# ============================================================

Import-Module Hyper-V -ErrorAction Stop

# --- Validate input
if (-not (Test-Path $snapshotVHD)) { Write-Error "Snapshot VHD not found"; exit 1 }
if ((Test-Path $fixedAzureVHD) -and $OverwriteFixedVHD) { Remove-Item $fixedAzureVHD -Force }

# ============================================================
# Step 1: Convert snapshot → dynamic VHDX
# ============================================================
try {
    Write-Host "[1/6] Converting snapshot → dynamic VHDX..."
    Convert-VHD -Path $snapshotVHD -DestinationPath $dynamicVHDX -VHDType Dynamic -ErrorAction Stop
    Write-Host "✓ Created dynamic VHDX"
} catch {
    Write-Error "Convert-VHD failed: $_"
    exit 1
}

# ============================================================
# Step 2: Mount VHDX for optimization
# ============================================================
try {
    Write-Host "[2/6] Mounting VHDX for optimization..."
    Mount-VHD -Path $dynamicVHDX -ErrorAction Stop
    Start-Sleep -Seconds 10

    $disk = Get-Disk | Where-Object { $_.Location -like "*$(Split-Path $dynamicVHDX -Leaf)*" } | Select-Object -First 1
    if (-not $disk) { throw "Could not find mounted disk" }

    $osPartition = Get-Partition -DiskNumber $disk.Number | Where-Object {
        $_.DriveLetter -and (Test-Path "$($_.DriveLetter):\Windows")
    } | Select-Object -First 1

    if (-not $osPartition) { throw "Could not locate OS partition" }
    
    $osDrive = $osPartition.DriveLetter
    Write-Host "✓ Mounted as drive $osDrive`:"

} catch {
    Write-Error "Mount failed: $_"
    exit 1
}

# ============================================================
# Step 3: Advanced Defragmentation Sequence (Community Method)
# ============================================================
try {
    Write-Host "[3/6] Running advanced defragmentation sequence..."
    
    # Sequence from community wisdom
    Write-Host "  Running defrag /x (free space consolidation)..."
    Start-Process -FilePath "defrag.exe" -ArgumentList "$osDrive`: /x" -Wait -NoNewWindow
    
    Write-Host "  Running defrag /k /l (SSD optimization)..."
    Start-Process -FilePath "defrag.exe" -ArgumentList "$osDrive`: /k /l" -Wait -NoNewWindow
    
    Write-Host "  Running defrag /x again..."
    Start-Process -FilePath "defrag.exe" -ArgumentList "$osDrive`: /x" -Wait -NoNewWindow
    
    Write-Host "  Running defrag /k (final optimization)..."
    Start-Process -FilePath "defrag.exe" -ArgumentList "$osDrive`: /k" -Wait -NoNewWindow
    
    Write-Host "✓ Defragmentation completed"

} catch {
    Write-Warning "Defragmentation failed: $($_.Exception.Message)"
}

# ============================================================
# Step 4: Shrink Partition (if needed)
# ============================================================
try {
    Write-Host "[4/6] Checking partition size..."
    $partitionInfo = Get-Partition -DiskNumber $disk.Number -PartitionNumber $osPartition.PartitionNumber
    $currentSizeGB = [math]::Round($partitionInfo.Size / 1GB, 2)
    
    if ($currentSizeGB -gt $targetSizeGB) {
        Write-Host "Shrinking partition from $currentSizeGB GB to $targetSizeGB GB..."
        Resize-Partition -DiskNumber $disk.Number -PartitionNumber $osPartition.PartitionNumber -Size ($targetSizeGB * 1GB) -ErrorAction Stop
        Write-Host "✓ Partition shrunk"
    } else {
        Write-Host "✓ Partition already at optimal size ($currentSizeGB GB)"
    }
} catch {
    Write-Warning "Partition shrink failed: $($_.Exception.Message)"
}

# ============================================================
# Step 5: Dismount and Compact
# ============================================================
try {
    Write-Host "[5/6] Dismounting and compacting VHDX..."
    Dismount-VHD -Path $dynamicVHDX -ErrorAction Stop
    
    # Full optimization
    Optimize-VHD -Path $dynamicVHDX -Mode Full -ErrorAction Stop
    Write-Host "✓ VHDX compacted"

} catch {
    Write-Error "Compact failed: $_"
    exit 1
}

# ============================================================
# Step 6: Convert to Fixed VHD (Hyper-V native - FAST)
# ============================================================
try {
    Write-Host "[6/6] Converting to fixed Azure VHD..."
    $destFolder = Split-Path -Path $fixedAzureVHD -Parent
    if (-not (Test-Path $destFolder)) { New-Item -Path $destFolder -ItemType Directory | Out-Null }

    # Use Hyper-V's native conversion (fast)
    Convert-VHD -Path $dynamicVHDX -DestinationPath $fixedAzureVHD -VHDType Fixed -ErrorAction Stop
    
    # Verify results
    $finalVhd = Get-Item $fixedAzureVHD
    $sizeGB = [math]::Round($finalVhd.Length / 1GB, 2)
    $hash = Get-FileHash -Path $fixedAzureVHD -Algorithm SHA256 | Select-Object -ExpandProperty Hash

    Write-Host "`n✅ CONVERSION COMPLETE"
    Write-Host "   Final VHD: $fixedAzureVHD"
    Write-Host "   Size: $sizeGB GB"
    Write-Host "   SHA256: $hash"

} catch {
    Write-Error "Convert to fixed VHD failed: $_"
    exit 1
}

# ============================================================
# Cleanup
# ============================================================
if (Test-Path $dynamicVHDX) {
    Remove-Item $dynamicVHDX -Force
    Write-Host "Cleaned up temporary VHDX file."
}

Write-Host "Script completed successfully 🎉"


# -----------------------------
# Download & Install AzCopy (custom URL, flattened to C:\Tools)
# -----------------------------

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

# -----------------------------
# Upload VHD to Azure Storage with AzCopy (via cmd.exe)
# -----------------------------

# Validate paths
if (-not (Test-Path $fixedAzureVHD)) {
    Write-Error "❌ Local VHD not found: $fixedAzureVHD"
    Exit 1
}
if (-not (Test-Path $azCopyExe)) {
    Write-Error "❌ AzCopy not installed. Run download-azcopy-github.ps1 first."
    Exit 1
}

Write-Host "🚀 Starting upload of $fixedAzureVHD to Azure with AzCopy (cmd.exe)..."

try {
    # Build AzCopy command
    $cmd = "cd `"$azCopyDir`" && azcopy.exe copy `"$fixedAzureVHD`" `"$destinationUrl`" --recursive"

    # Run inside cmd.exe
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -Wait -PassThru -NoNewWindow

    if ($process.ExitCode -eq 0) {
        Write-Host "✅ Upload completed successfully."
    } else {
        Write-Error "❌ AzCopy exited with code $($process.ExitCode). Upload failed."
    }
} catch {
    Write-Error "❌ Upload failed: $_"
}