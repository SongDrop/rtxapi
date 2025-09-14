# ============================================================
# Optimized VHD Conversion with Defrag & Compact Techniques
# ============================================================

#region Parameters
$snapshotVHD    = "C:\Users\source\Downloads\sxshdjue3-snapshot-1757506900.vhd"
$dynamicVHDX    = "C:\Users\source\Downloads\sxshdjue3-dynamic-vhd.vhdx"
$fixedAzureVHD  = "C:\Users\source\Downloads\vhdusb\sxshdjue3-fixed-azure.vhd"
$OverwriteFixedVHD = $true
$targetSizeGB   = 220
#endregion

# --- Ensure Admin & Required Modules
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run this script as Administrator."
    exit 1
}

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