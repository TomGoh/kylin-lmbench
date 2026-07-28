#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

mode=${1:?usage: set-next-mode.sh nvhe|protected}
case "$mode" in
    nvhe|protected) id="d3000-6.6.30-$mode" ;;
    *) die "unsupported one-shot mode: $mode" ;;
esac

sudo grub-editenv /boot/efi/boot/grub/grubenv unset next_entry || true
sudo grub-editenv /boot/grub/grubenv unset next_entry || true
sudo grub-reboot --boot-directory=/boot/efi/boot "$id"
next=$(sudo grub-editenv /boot/efi/boot/grub/grubenv list | sed -n 's/^next_entry=//p')
[[ "$next" == "$id" ]] || die "active ESP grubenv verification failed: expected=$id actual=${next:-none}"
record_note grub "verified one-shot next_entry=$id in active ESP grubenv"
log "verified one-shot GRUB next_entry=$id in active ESP grubenv"
