 #Convert a downloaded snapshot VHD to a fixed VHD, zero free space in the guest OS partition,
#then compact the VHD so its file size is reduced.

#region Parameters (edit if needed)
# Path to the downloaded snapshot VHD (input)
$snapshotVHD = "C:\Users\source\Downloads\sxshdjue3-snapshot-1757506900.vhd"

# Path for the fixed-size VHD to create (output)
$fixedVHD = "C:\Users\source\Downloads\vhdusb\sxshdjue3-snapshot-fixed-bootable.vhd"

# Overwrite existing $fixedVHD if present?
$OverwriteFixedVHD = $true

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
$mounted = $null
$diskNumber = $null
$assignedLetters = @()  # track assigned letters we created so we can remove them later
try {
    Write-Host "Mounting fixed VHD..."
    $mounted = Mount-VHD -Path $fixedVHD -Passthru -ErrorAction Stop

    # Wait for the disk to show up
    $tries = 0
    while ($null -eq $mounted -or $null -eq $mounted.DiskNumber) {
        Start-Sleep -Seconds 1
        $tries++
        if ($tries -gt 10) { break }
        $mounted = Get-VHD -Path $fixedVHD | ForEach-Object { Mount-VHD -Path $fixedVHD -Passthru -ErrorAction SilentlyContinue }
    }

    # Best effort: read DiskNumber from the Mount-VHD passthru object
    $diskNumber = $mounted.DiskNumber
    if ($null -eq $diskNumber) {
        # fallback: try to find a disk whose Location contains the VHD path (best-effort)
        $disk = Get-Disk | Where-Object { $_.Location -match [regex]::Escape($fixedVHD) } | Select-Object -First 1
        if ($disk) { $diskNumber = $disk.Number }
    }

    if ($null -eq $diskNumber) { throw "Unable to determine the disk number for mounted VHD." }

    Write-Host "Mounted VHD disk number: $diskNumber"

    # Ensure disk is online & writable
    try {
        Set-Disk -Number $diskNumber -IsOffline $false -IsReadOnly $false -ErrorAction SilentlyContinue
    } catch { }

    Start-Sleep -Seconds 1

    $partitions = Get-Partition -DiskNumber $diskNumber -ErrorAction Stop
    if (-not $partitions) { throw "No partitions found on mounted VHD (disk $diskNumber)." }

    # function: find a free drive letter (Z -> D)
    function Get-FreeDriveLetter {
        $letters = 'Z','Y','X','W','V','U','T','S','R','Q','P','O','N','M','L','K','J','I','H','G','F','E','D','C','B','A'
        foreach ($L in $letters) {
            if (-not (Get-Volume -DriveLetter $L -ErrorAction SilentlyContinue)) { return $L }
        }
        throw "No free drive letter available."
    }

    $osDrive = $null
    foreach ($p in $partitions) {
        $drv = $p.DriveLetter
        if (-not $drv) {
            # assign a temp letter
            $letter = Get-FreeDriveLetter
            try {
                Set-Partition -DiskNumber $diskNumber -PartitionNumber $p.PartitionNumber -NewDriveLetter $letter -ErrorAction Stop
                $assignedLetters += @{ Disk = $diskNumber; Partition = $p.PartitionNumber; Letter = $letter }
                $drv = $letter
            } catch {
                # can't assign letter; skip
                continue
            }
        }
        # test for Windows folder - identify OS partition
        if (Test-Path ("$drv`: \Windows".Replace(" ", ""))) {
            $osDrive = $drv
            break
        } elseif (Test-Path ("$drv`:\Program Files")) {
            # fallback heuristics
            $osDrive = $drv
            break
        }
    }

    if (-not $osDrive) {
        Write-Warning "Could not reliably detect the OS partition by checking for \Windows. Trying largest NTFS partition..."

        # try largest partition with format
        $vols = @()
        foreach ($p in $partitions) {
            $vol = Get-Volume -DiskNumber $diskNumber -ErrorAction SilentlyContinue | Where-Object { $_.FileSystem -ne $null }
            if ($vol) { $vols += $vol }
        }
        if ($vols) {
            $largest = $vols | Sort-Object Size -Descending | Select-Object -First 1
            $osDrive = $largest.DriveLetter
        }
    }

    if (-not $osDrive) {
        throw "Unable to locate OS partition inside VHD. Aborting zero/compact step."
    }

    Write-Host "Identified OS partition drive letter inside mounted VHD: $osDrive`:"

    # --- Step 3: Zero free space on the OS partition
    # Prefer sdelete if available (Sysinternals), otherwise use cipher /w
    $sdelete = (Get-Command sdelete -ErrorAction SilentlyContinue).Source
    if ($sdelete) {
        Write-Host "Using sdelete to zero free space (sdelete found): $sdelete"
        # sdelete usage: sdelete -z <drive>:
        $arg = "-z $osDrive`:"
        $p = Start-Process -FilePath $sdelete -ArgumentList $arg -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -ne 0) { Write-Warning "sdelete returned exit code $($p.ExitCode). You may want to run sdelete manually." }
    } else {
        Write-Host "sdelete not found. Falling back to 'cipher /w' to zero free space. This may take long."
        $cipherArgs = "/w:$osDrive`:\"
        $p = Start-Process -FilePath "cipher.exe" -ArgumentList $cipherArgs -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -ne 0) { Write-Warning "cipher returned exit code $($p.ExitCode)." }
    }

    Write-Host "Zeroing complete. Proceeding to dismount and compact."

} catch {
    $err = $_.Exception.Message
    Write-Error "Error while mounting/zeroing partitions: $err"
    # try cleanup later in finally
} finally {
    # remove any temporary letters we added
    foreach ($m in $assignedLetters) {
        try {
            Remove-PartitionAccessPath -DiskNumber $m.Disk -PartitionNumber $m.Partition -AccessPath ("$($m.Letter)`:\") -ErrorAction SilentlyContinue
        } catch { }
    }

    # Dismount VHD if mounted
    try {
        if (Get-VHD -Path $fixedVHD -ErrorAction SilentlyContinue) {
            Dismount-VHD -Path $fixedVHD -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
    } catch {
        Write-Warning "Failed to dismount VHD cleanly: $_"
    }
}

# --- Step 4: Compact VHD with Optimize-VHD
try {
    Write-Host "Optimizing/compacting VHD. This can take a while..."
    Optimize-VHD -Path $fixedVHD -Mode Full -ErrorAction Stop
    Write-Host "Optimize-VHD finished."
} catch {
    Write-Warning "Optimize-VHD failed: $_. Ensure the Hyper-V module is available and VHD is not mounted."
}

# --- Final size report
try {
    $sizeBytes = (Get-Item $fixedVHD).Length
    $sizeGB = [math]::Round($sizeBytes / 1GB, 2)
    Write-Host "Final VHD size: $sizeGB GB ($sizeBytes bytes) -> $fixedVHD"
} catch {
    Write-Warning "Unable to read final VHD size: $_"
}

Write-Host "Script complete."
 
