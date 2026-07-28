#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LOCAL_DEST=${LOCAL_DEST:-$SCRIPT_DIR}
SSH_CONFIG=${SSH_CONFIG:-/home/jose/.ssh/config}
mkdir -p "$LOCAL_DEST"
for category in configs logs metadata notes results staged state; do
    mkdir -p "$LOCAL_DEST/$category"
    rsync -a --partial \
        -e "ssh -F $SSH_CONFIG -o ConnectTimeout=10 -o ConnectionAttempts=1" \
        "D3000:/home/jose/kylin-lmbench-exp/$category/" "$LOCAL_DEST/$category/"
done
mkdir -p "$LOCAL_DEST/deployed-scripts"
rsync -a --partial --exclude __pycache__/ \
    -e "ssh -F $SSH_CONFIG -o ConnectTimeout=10 -o ConnectionAttempts=1" \
    D3000:/home/jose/kylin-lmbench-exp/scripts/ "$LOCAL_DEST/deployed-scripts/"
printf '[%s] synced D3000 experiment artifacts\n' "$(date --iso-8601=seconds)" \
    >>"$LOCAL_DEST/logs/local-sync.log"

# Geekbench claim URLs contain a result-ownership credential.  Keep the result
# ID and canonical URL, but never copy the claim key into Git history.
find "$LOCAL_DEST/results" -type f \( -name stdout.txt -o -name result-urls.txt \) \
    -exec sed -i -E 's#(claim\?key=)[A-Za-z0-9_-]+#\1REDACTED#g' {} +

manifest_tmp="$LOCAL_DEST/ARCHIVE_SHA256SUMS.tmp"
(
    cd "$LOCAL_DEST"
    LC_ALL=C find configs deployed-scripts logs metadata notes results staged state \
        -type f ! -path '*/__pycache__/*' -print0 |
        LC_ALL=C sort -z |
        xargs -0 sha256sum
) >"$manifest_tmp"
mv "$manifest_tmp" "$LOCAL_DEST/ARCHIVE_SHA256SUMS"
