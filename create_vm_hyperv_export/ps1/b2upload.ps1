# -----------------------------
# STEP 0: Download and install rclone (optional)
# -----------------------------
$toolsDir = "C:\Tools"
if (-not (Test-Path $toolsDir)) { New-Item -Path $toolsDir -ItemType Directory | Out-Null }

$rcloneZip = Join-Path $toolsDir "rclone.zip"
$rcloneUrl = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"

Write-Host "Downloading rclone..."
Invoke-WebRequest -Uri $rcloneUrl -OutFile $rcloneZip -UseBasicParsing

Write-Host "Extracting rclone..."
Expand-Archive -Path $rcloneZip -DestinationPath $toolsDir -Force

$rclonePath = Get-ChildItem -Path $toolsDir -Recurse -Filter "rclone.exe" | Select-Object -First 1 -ExpandProperty FullName
if (-not (Test-Path $rclonePath)) { Write-Error "rclone installation failed"; exit 1 }
Write-Host "✅ rclone installed successfully at: $rclonePath"

# -----------------------------
# STEP 1: Configure Backblaze B2 remote automatically
# -----------------------------
$remoteName = "b2remote"
$bucketName = "my-bucket-name"        # Change this to your bucket
$appKeyId   = "YOUR_APP_KEY_ID"       # Replace with your key ID
$appKey     = "YOUR_APP_KEY"          # Replace with your application key

# Create rclone config file if it doesn't exist
$rcloneConfigDir = "$env:USERPROFILE\.config\rclone"
if (-not (Test-Path $rcloneConfigDir)) { New-Item -Path $rcloneConfigDir -ItemType Directory | Out-Null }
$rcloneConfigFile = Join-Path $rcloneConfigDir "rclone.conf"

# Add B2 remote configuration
$configText = @"
[$remoteName]
type = b2
account = $appKeyId
key = $appKey
endpoint =
"@

# If config exists, append or replace the remote
if (Test-Path $rcloneConfigFile) {
    # Remove old remote if exists
    (Get-Content $rcloneConfigFile) -notmatch "^\[$remoteName\]" | Set-Content $rcloneConfigFile
    Add-Content -Path $rcloneConfigFile -Value $configText
} else {
    $configText | Out-File -FilePath $rcloneConfigFile -Encoding ASCII
}
Write-Host "✅ Backblaze B2 remote '$remoteName' configured successfully."

# -----------------------------
# STEP 2: Upload file to B2
# -----------------------------
$remotePath = "$remoteName:$bucketName/vhds/"

Write-Host "Uploading $fixedVHD to Backblaze B2..."
$cmd = "`"$rclonePath`" copy `"$fixedVHD`" `"$remotePath`" --progress"
$proc = Start-Process -FilePath cmd.exe -ArgumentList "/c $cmd" -Wait -PassThru -NoNewWindow

if ($proc.ExitCode -eq 0) {
    Write-Host "✅ Upload to B2 completed successfully."
} else {
    Write-Error "❌ rclone upload to B2 failed with code $($proc.ExitCode)"
}