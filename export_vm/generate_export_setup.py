def generate_hyperv_setup_script(os_disk_sas_url: str, fixed_vhd_upload_sas_url: str, hook_url: str, download_folder: str = "D:\\") -> str:
    script = f'''
param(
    [Parameter(Mandatory=$true)]
    [string]$OsDiskSasUrl = "{os_disk_sas_url}",

    [Parameter(Mandatory=$true)]
    [string]$HookUrl = "{hook_url}",

    [Parameter(Mandatory=$true)]
    [string]$FixedVhdUploadSasUrl = "{fixed_vhd_upload_sas_url}",

    [Parameter(Mandatory=$false)]
    [string]$DownloadFolder = "{download_folder}"
)

function Invoke-Hook {{
    param([string]$status)
    try {{
        $body = @{{ status = $status }} | ConvertTo-Json
        Invoke-RestMethod -Uri $HookUrl -Method Post -Body $body -ContentType "application/json"
    }} catch {{
        Write-Warning "Failed to invoke hook with status $status: $_"
    }}
}}

# Get disk assigned to D: drive (or the disk with uninitialized partition)
$driveLetter = "D"

$vol = Get-Volume -DriveLetter $driveLetter -ErrorAction SilentlyContinue

if (-not $vol) {{
    # Find the disk without partitions or uninitialized disk
    $disks = Get-Disk | Where-Object PartitionStyle -Eq 'RAW'

    foreach ($disk in $disks) {{
        Write-Host "Initializing disk number $($disk.Number)..."
        Initialize-Disk -Number $disk.Number -PartitionStyle GPT

        # Create a new partition that uses the full disk
        $partition = New-Partition -DiskNumber $disk.Number -UseMaximumSize -AssignDriveLetter

        # Format the partition as NTFS
        Format-Volume -Partition $partition -FileSystem NTFS -NewFileSystemLabel "Data" -Confirm:$false

        Write-Host "Disk $($disk.Number) initialized and formatted with drive letter $($partition.DriveLetter)"
    }}
}} else {{
    Write-Host "Drive $driveLetter: is already initialized and formatted."
}}

# Ensure download folder exists
if (-not (Test-Path $DownloadFolder)) {{
    New-Item -Path $DownloadFolder -ItemType Directory | Out-Null
}}

# Create vhd_exports folder inside download folder
$exportFolder = Join-Path $DownloadFolder "vhd_exports"
if (-not (Test-Path $exportFolder)) {{
    New-Item -Path $exportFolder -ItemType Directory | Out-Null
}}

$downloadedVhd = Join-Path $DownloadFolder "abcd.vhd"
$fixedVhd = Join-Path $exportFolder "abcd_fixed.vhd"

# Download the dynamic VHD
Invoke-Hook -status "download_start"
Write-Host "Downloading VHD from SAS URL..."
try {{
    Invoke-WebRequest -Uri $OsDiskSasUrl -OutFile $downloadedVhd -UseBasicParsing
    Invoke-Hook -status "download_completed"
    Write-Host "Download completed."
}} catch {{
    Invoke-Hook -status "download_failed"
    Write-Error "Failed to download VHD: $_"
    exit 1
}}

# Convert dynamic VHD to fixed VHD
Invoke-Hook -status "conversion_start"
Write-Host "Converting dynamic VHD to fixed VHD..."
try {{
    Import-Module Hyper-V -ErrorAction Stop

    # Remove existing fixed VHD if it exists
    if (Test-Path $fixedVhd) {{
        Remove-Item $fixedVhd -Force
    }}

    Convert-VHD -Path $downloadedVhd -DestinationPath $fixedVhd -VHDType Fixed
    Invoke-Hook -status "conversion_completed"
    Write-Host "Conversion completed."
}} catch {{
    Invoke-Hook -status "conversion_failed"
    Write-Error "Failed to convert VHD: $_"
    exit 1
}}

# Upload fixed VHD folder back to Azure Storage using azcopy
Invoke-Hook -status "upload_start"
Write-Host "Uploading fixed VHD folder back to Azure Storage..."
try {{
    $azcopyPath = "C:\\Program Files (x86)\\Microsoft SDKs\\Azure\\AzCopy\\AzCopy.exe"
    if (-not (Test-Path $azcopyPath)) {{
        $azcopyPath = "azcopy"  # fallback if in PATH
    }}

    & $azcopyPath copy $exportFolder $FixedVhdUploadSasUrl --recursive=true --overwrite=true
    Invoke-Hook -status "upload_completed"
    Write-Host "Upload completed."
}} catch {{
    Invoke-Hook -status "upload_failed"
    Write-Error "Failed to upload fixed VHD folder: $_"
    exit 1
}}

# Shutdown VM after upload
Invoke-Hook -status "shutdown_start"
Write-Host "Shutting down the VM..."
Stop-Computer -Force
Invoke-Hook -status "shutdown_completed"
'''
    return script