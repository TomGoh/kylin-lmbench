#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

expected=${1:-$(mode_from_cmdline)}
assert_mode "$expected"
capture_metadata "${2:-$EXP_HOME/metadata/mode-$(mode_from_cmdline)-$(date +%Y%m%d-%H%M%S)}"
record_note mode "validated boot mode=$expected using cmdline and kernel-specific dmesg markers"
log "validated boot mode: $expected"
