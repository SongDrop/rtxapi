#Convert a downloaded snapshot VHD to a fixed VHD, zero free space in the guest OS partition,
#then compact the VHD so its file size is reduced.

#region Parameters (edit if needed)
# Path to the downloaded snapshot VHD (input)
$snapshotVHD = "C:\Users\source\Downloads\sxshdjue3-snapshot-1757506900.vhd"

# Path for the fixed-size VHD to create (output)
$fixedVHD = "C:\Users\source\Downloads\vhdusb\sxshdjue3-snapshot-fixed-bootable.vhd"

# Overwrite existing $fixedVHD if present?
$OverwriteFixedVHD = $true

# Create tools directory if it doesn't exist
$toolsDir = "C:\Tools"
if (-not (Test-Path $toolsDir)) {
    New-Item -Path $toolsDir -ItemType Directory | Out-Null
}

# Download sdelete
$sdeleteZip = Join-Path $toolsDir "SDelete.zip"
Invoke-WebRequest -Uri "https://download.sysinternals.com/files/SDelete.zip" -OutFile $sdeleteZip -UseBasicParsing

# Extract the ZIP
$sdeleteExtractDir = Join-Path $toolsDir "SDelete"
Expand-Archive -Path $sdeleteZip -DestinationPath $toolsDir -Force

# Check if sdelete.exe exists
$sdeletePath = Join-Path $sdeleteExtractDir "sdelete.exe"

# Sometimes the ZIP extracts directly into C:\Tools\, so check there too
if (-not (Test-Path $sdeletePath)) {
    $sdeletePath = Get-ChildItem -Path $toolsDir -Recurse -Filter "sdelete.exe" | Select-Object -First 1 -ExpandProperty FullName
}

if (Test-Path $sdeletePath) {
    Write-Host "✅ sdelete installed successfully at: $sdeletePath"
} else {
    Write-Error "❌ sdelete extraction failed - no sdelete.exe found."
    # Debug: list all files extracted
    Get-ChildItem $toolsDir -Recurse | ForEach-Object { Write-Host "Found: $($_.FullName)" }
    exit 1
}

# ✅ Unblock to avoid the manual click
Unblock-File -Path $sdeletePath
# If sdelete (Sysinternals) exists, it will be used for zeroing free space (recommended). Otherwise 'cipher /w' is used.
#endregion

# --- Ensure admin & Hyper-V module
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Script must be run as Administrator. Rerun this script from an elevated PowerShell session."
    exit 1
}

try {
    Import-Module Hyper-V -ErrorAction Stop
} catch {
    Write-Error "Hyper-V module not available. Ensure Hyper-V role is installed."
    exit 1
}

# --- Validate input
if (-not (Test-Path $snapshotVHD)) {
    Write-Error "Input snapshot VHD not found: $snapshotVHD"
    exit 1
}

if (Test-Path $fixedVHD) {
    if ($OverwriteFixedVHD) {
        Write-Host "Removing existing fixed VHD: $fixedVHD"
        Remove-Item -Path $fixedVHD -Force -ErrorAction SilentlyContinue
    } else {
        Write-Error "Fixed VHD already exists and overwrite is disabled. Exiting."
        exit 1
    }
}

# --- Step 1: Convert to Fixed VHD
try {
    Write-Host "Converting snapshot to fixed VHD..."
    Convert-VHD -Path $snapshotVHD -DestinationPath $fixedVHD -VHDType Fixed -ErrorAction Stop
    if (-not (Test-Path $fixedVHD)) { throw "Convert-VHD did not produce output file." }
    Write-Host "Created fixed VHD: $fixedVHD"
} catch {
    Write-Error "Convert-VHD failed: $_"
    exit 1
}

# --- Step 2: Mount the fixed VHD and find OS partition
$diskNumber = $null
$assignedLetters = @()
$osDrive = $null

try {
    Write-Host "Mounting fixed VHD..."
    
    # Mount the VHD
    Mount-VHD -Path $fixedVHD -ErrorAction Stop
    Start-Sleep -Seconds 5  # Wait for disk to be recognized
    
    # Find the disk by looking for the VHD filename in the location
    $vhdFileName = [System.IO.Path]::GetFileName($fixedVHD)
    $disk = Get-Disk | Where-Object { $_.Location -like "*$vhdFileName*" } | Select-Object -First 1
    
    if (-not $disk) {
        throw "Failed to find mounted disk for VHD: $fixedVHD"
    }
    
    $diskNumber = $disk.Number
    Write-Host "Mounted VHD disk number: $diskNumber"
    
    # Ensure disk is online & writable
    Set-Disk -Number $diskNumber -IsOffline $false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    
    # Get partitions
    $partitions = Get-Partition -DiskNumber $diskNumber -ErrorAction SilentlyContinue
    if (-not $partitions) {
        throw "No partitions found on mounted VHD (disk $diskNumber)."
    }
    
    # Function to get a free drive letter
    function Get-FreeDriveLetter {
        $usedLetters = (Get-Volume | Where-Object { $_.DriveLetter }).DriveLetter
        $allLetters = 67..90 | ForEach-Object { [char]$_ }  # C to Z
        foreach ($letter in $allLetters) {
            if ($letter -notin $usedLetters) {
                return $letter
            }
        }
        throw "No free drive letters available"
    }
    
    # Find and assign drive letters to partitions
    foreach ($partition in $partitions) {
        if (-not $partition.DriveLetter) {
            $freeLetter = Get-FreeDriveLetter
            try {
                Set-Partition -DiskNumber $diskNumber -PartitionNumber $partition.PartitionNumber -NewDriveLetter $freeLetter -ErrorAction Stop
                $assignedLetters += @{
                    DiskNumber = $diskNumber
                    PartitionNumber = $partition.PartitionNumber
                    DriveLetter = $freeLetter
                }
                Write-Host "Assigned drive letter $freeLetter to partition $($partition.PartitionNumber)"
            } catch {
                Write-Warning "Failed to assign drive letter to partition $($partition.PartitionNumber): $_"
            }
        }
    }
    
    # Wait a moment for drive letters to become accessible
    Start-Sleep -Seconds 3
    
    # Find the OS partition (look for Windows directory)
    foreach ($partition in $partitions) {
        if ($partition.DriveLetter) {
            $drivePath = "${$partition.DriveLetter}:\"
            if (Test-Path (Join-Path $drivePath "Windows")) {
                $osDrive = $partition.DriveLetter
                Write-Host "Found OS partition on drive: $osDrive"
                break
            }
        }
    }
    
    if (-not $osDrive) {
        # Fallback: use the first partition with a drive letter
        $firstPartition = $partitions | Where-Object { $_.DriveLetter } | Select-Object -First 1
        if ($firstPartition) {
            $osDrive = $firstPartition.DriveLetter
            Write-Host "Using fallback drive letter: $osDrive"
        } else {
            throw "Could not find any accessible partitions with drive letters"
        }
    }
    
    # --- Step 3: Zero free space on the OS partition
    $drivePath = "${osDrive}:\"
    Write-Host "Zeroing free space on drive $drivePath"
    
    # Use the sdelete path we already verified exists
    if (Test-Path $sdeletePath) {
        Write-Host "Using sdelete for zeroing (much faster): $sdeletePath"
        
        # Show progress - sdelete will display its own progress
        Write-Host "Starting sdelete -z ${osDrive}: (this will show progress percentage)"
        
        $process = Start-Process -FilePath $sdeletePath `
            -ArgumentList @("-z", "${osDrive}:", "-accepteula") `
            -NoNewWindow -Wait -PassThru

        if ($process.ExitCode -eq 0) {
            Write-Host "sdelete completed successfully!"
        } else {
            Write-Warning "sdelete exited with code $($process.ExitCode) - falling back to cipher"
            # Fallback to cipher
            Write-Host "Falling back to cipher /w (this will take much longer)..."
            $process = Start-Process -FilePath "cipher.exe" `
                -ArgumentList @("/w:${drivePath}") `
                -NoNewWindow -Wait -PassThru
        }
    } else {
        Write-Host "sdelete not found at $sdeletePath. Using cipher /w (this will take much longer)..."
        $process = Start-Process -FilePath "cipher.exe" `
            -ArgumentList @("/w:${drivePath}") `
            -NoNewWindow -Wait -PassThru
    }
    
    if ($process.ExitCode -ne 0) {
        Write-Warning "Zeroing tool exited with code $($process.ExitCode)"
    } else {
        Write-Host "Zeroing completed successfully"
    }
    
} catch {
    Write-Error "Error during mounting/zeroing: $_"
    # Continue to cleanup
} finally {
    # --- Cleanup: Remove assigned drive letters and dismount
    Write-Host "Cleaning up..."
    
    # Remove assigned drive letters
    foreach ($assignment in $assignedLetters) {
        try {
            Remove-PartitionAccessPath -DiskNumber $assignment.DiskNumber `
                -PartitionNumber $assignment.PartitionNumber `
                -AccessPath "$($assignment.DriveLetter):\" `
                -ErrorAction SilentlyContinue
        } catch {
            Write-Warning "Failed to remove drive letter $($assignment.DriveLetter): $_"
        }
    }
    
    # Dismount VHD
    try {
        if (Get-VHD -Path $fixedVHD -ErrorAction SilentlyContinue) {
            Dismount-VHD -Path $fixedVHD -ErrorAction Stop
            Write-Host "VHD dismounted successfully"
        }
    } catch {
        Write-Warning "Failed to dismount VHD: $_"
    }
}

# --- Step 4: Compact VHD with Optimize-VHD
try {
    Write-Host "Compacting VHD (this may take a while)..."
    Optimize-VHD -Path $fixedVHD -Mode Full -ErrorAction Stop
    Write-Host "VHD compaction completed"
} catch {
    Write-Warning "Optimize-VHD failed: $_"
}

# --- Final size report
try {
    $vhdInfo = Get-Item $fixedVHD
    $sizeGB = [math]::Round($vhdInfo.Length / 1GB, 2)
    Write-Host "Final VHD size: $sizeGB GB"
    Write-Host "Output file: $fixedVHD"
} catch {
    Write-Warning "Could not get final file size: $_"
}

Write-Host "Script completed successfully"