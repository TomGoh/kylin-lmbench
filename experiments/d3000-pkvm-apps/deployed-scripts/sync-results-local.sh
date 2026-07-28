#!/usr/bin/env bash
set -euo pipefail

LOCAL_DEST=${LOCAL_DEST:-/home/jose/kylin-lmbench-exp}
SSH_CONFIG=${SSH_CONFIG:-/home/jose/.ssh/config}
mkdir -p "$LOCAL_DEST"
rsync -a --partial \
    --exclude work/ --exclude build/ \
    -e "ssh -F $SSH_CONFIG -o ConnectTimeout=10 -o ConnectionAttempts=1" \
    D3000:/home/jose/kylin-lmbench-exp/ "$LOCAL_DEST/"
printf '[%s] synced D3000 experiment artifacts\n' "$(date --iso-8601=seconds)" \
    >>"$LOCAL_DEST/logs/local-sync.log"
