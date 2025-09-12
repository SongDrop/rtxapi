# ============================================================
# Convert snapshot VHD → dynamic VHDX → shrink → compact → fixed VHD
# USB-safe and Azure-ready
# ============================================================

#region Parameters
$snapshotVHD   = "C:\Users\source\Downloads\sxshdjue3-snapshot-1757506900.vhd"   # Input snapshot
$dynamicVHDX   = "C:\Users\source\Downloads\sxshdjue3-dynamic-vhd.vhdx"          # Temp dynamic
$fixedAzureVHD = "C:\Users\source\Downloads\vhdusb\sxshdjue3-fixed-azure.vhd"   # Final fixed for USB/Azure
$OverwriteFixedVHD = $true
$toolsDir = "C:\Tools"
$targetSizeGB = 220  # Max size for USB
#endregion

# --- Ensure Admin & Hyper-V module
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run this script as Administrator."
    exit 1
}
try { Import-Module Hyper-V -ErrorAction Stop } catch {
    Write-Error "Hyper-V module not available. Install Hyper-V role first."
    exit 1
}

# --- Prepare tools (sdelete)
if (-not (Test-Path $toolsDir)) { New-Item -Path $toolsDir -ItemType Directory | Out-Null }
$sdeleteZip = Join-Path $toolsDir "SDelete.zip"
$sdeleteExtractDir = Join-Path $toolsDir "SDelete"
$sdeletePath = Join-Path $sdeleteExtractDir "sdelete.exe"
if (-not (Test-Path $sdeletePath)) {
    Write-Host "Downloading SDelete..."
    Invoke-WebRequest -Uri "https://download.sysinternals.com/files/SDelete.zip" -OutFile $sdeleteZip -UseBasicParsing
    Expand-Archive -Path $sdeleteZip -DestinationPath $toolsDir -Force
    $sdeletePath = Get-ChildItem -Path $toolsDir -Recurse -Filter "sdelete.exe" | Select-Object -First 1 -ExpandProperty FullName
}
Unblock-File -Path $sdeletePath

# --- Validate input
if (-not (Test-Path $snapshotVHD)) { Write-Error "Snapshot VHD not found"; exit 1 }
if ((Test-Path $fixedAzureVHD) -and $OverwriteFixedVHD) { Remove-Item $fixedAzureVHD -Force }

# ============================================================
# Step 1: Convert snapshot → dynamic VHDX
# ============================================================
try {
    Write-Host "Converting snapshot → dynamic VHDX..."
    Convert-VHD -Path $snapshotVHD -DestinationPath $dynamicVHDX -VHDType Dynamic -ErrorAction Stop
    Write-Host "Created dynamic VHDX: $dynamicVHDX"
} catch {
    Write-Error "Convert-VHD to dynamic failed: $_"
    exit 1
}

# ============================================================
# Step 2: Mount, shrink OS partition, zero free space, compact
# ============================================================
try {
    Write-Host "Mounting dynamic VHDX..."
    Mount-VHD -Path $dynamicVHDX -ErrorAction Stop
    Start-Sleep -Seconds 5

    $disk = Get-Disk | Where-Object { $_.Location -like "*$([System.IO.Path]::GetFileName($dynamicVHDX))*" } | Select-Object -First 1
    if (-not $disk) { throw "Could not find mounted disk for $dynamicVHDX" }

    # Find OS partition
    $osPartition = (Get-Partition -DiskNumber $disk.Number | Where-Object {
        $_.DriveLetter -and (Test-Path "$($_.DriveLetter):\Windows")
    } | Select-Object -First 1)
    if (-not $osPartition) { throw "Could not locate OS partition inside VHDX" }
    $osDrive = $osPartition.DriveLetter

    # Shrink partition to fit USB
    Write-Host "Resizing OS partition $($osPartition.PartitionNumber) to $targetSizeGB GB..."
    Resize-Partition -DiskNumber $disk.Number -PartitionNumber $osPartition.PartitionNumber -Size ($targetSizeGB * 1GB)
    Start-Sleep -Seconds 2

    # Zero free space
    Write-Host "Zeroing free space on $osDrive`:\ ..."
    $proc = Start-Process -FilePath $sdeletePath -ArgumentList @("-z", "$osDrive`:", "-accepteula") -NoNewWindow -Wait -PassThru
    if ($proc.ExitCode -ne 0) { 
        Write-Warning "sdelete failed, fallback to cipher"
        Start-Process cipher -ArgumentList "/w:$osDrive`:" -Wait
    }

} catch {
    Write-Error "Zeroing/shrink failed: $_"
} finally {
    Write-Host "Dismounting dynamic VHDX..."
    Dismount-VHD -Path $dynamicVHDX -ErrorAction SilentlyContinue
}

# Compact dynamic VHDX
try {
    Write-Host "Compacting dynamic VHDX..."
    Optimize-VHD -Path $dynamicVHDX -Mode Full -ErrorAction Stop
    Write-Host "Dynamic VHDX compacted."
} catch {
    Write-Warning "Optimize-VHD failed: $_"
}

# ============================================================
# Step 3: Convert compacted dynamic VHDX → fixed VHD (USB/Azure-ready)
# ============================================================
try {
    Write-Host "Converting dynamic VHDX → fixed Azure/USB VHD..."
    Convert-VHD -Path $dynamicVHDX -DestinationPath $fixedAzureVHD -VHDType Fixed -ErrorAction Stop
    $sizeGB = [math]::Round((Get-Item $fixedAzureVHD).Length / 1GB, 2)
    $hash = Get-FileHash -Path $fixedAzureVHD -Algorithm SHA256 | Select-Object -ExpandProperty Hash
    Write-Host "✅ Final VHD: $fixedAzureVHD"
    Write-Host "   Size  : $sizeGB GB"
    Write-Host "   SHA256: $hash"
} catch {
    Write-Error "Final convert to fixed failed: $_"
    exit 1
}

Write-Host "Script completed successfully 🎉"
