#!/bin/bash
set -euo pipefail

# ---------------- CONFIG ----------------
IMAGE_NAME="codeberg.org/forgejo/forgejo:12.0.1"   # The exact Forgejo image you want to snapshot
BACKUP_DIR="$HOME/forgejo_backups"                # Where to store the snapshot
WEBHOOK_URL=""                                    # Optional webhook for status
REMOTE_UPLOAD_CMD=""                              # e.g., rclone copy, scp, aws s3 cp

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
IMAGE_FILE="$BACKUP_DIR/forgejo_$(echo $IMAGE_NAME | tr ':' '_')_$TIMESTAMP.tar"

mkdir -p "$BACKUP_DIR"

# ---------------- SNAPSHOT ----------------
echo "📦 Saving Docker image $IMAGE_NAME..."
docker pull "$IMAGE_NAME"
docker save -o "$IMAGE_FILE" "$IMAGE_NAME"
echo "✅ Docker image saved as $IMAGE_FILE"

# ---------------- OPTIONAL UPLOAD ----------------
if [[ -n "$REMOTE_UPLOAD_CMD" ]]; then
    echo "☁️ Uploading image to remote..."
    eval "$REMOTE_UPLOAD_CMD \"$IMAGE_FILE\""
    echo "✅ Upload completed"
fi

# ---------------- WEBHOOK NOTIFICATION ----------------
if [[ -n "$WEBHOOK_URL" ]]; then
    echo "🔔 Sending webhook notification..."
    JSON_PAYLOAD=$(cat <<EOF
{
  "hostname": "$(hostname)",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "image_name": "$IMAGE_NAME",
  "image_file": "$IMAGE_FILE",
  "status": "success"
}
EOF
)
    curl -s -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$JSON_PAYLOAD" \
        --connect-timeout 10 \
        --max-time 30 \
        --retry 2 \
        --retry-delay 5 \
        --output /dev/null
fi

echo "🎉 Backup snapshot completed!"
