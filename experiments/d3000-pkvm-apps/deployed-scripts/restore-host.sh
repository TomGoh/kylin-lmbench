#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

set_thp always
sudo swapon -a || true
sudo systemctl set-default graphical.target
sudo systemctl isolate graphical.target || true
rm -f "$STATE_DIR/host-prepared"
record_note host "restored THP=always swap=on graphical target"
log "host restored: THP=always swap=on graphical target"
