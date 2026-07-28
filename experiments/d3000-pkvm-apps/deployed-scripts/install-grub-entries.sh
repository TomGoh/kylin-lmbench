#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $(uname -r) == 6.6.30+ ]] || die "unexpected running kernel: $(uname -r)"
for file in /boot/vmlinuz-6.6.30+ /boot/initrd.img-6.6.30+; do
    [[ -f "$file" ]] || die "missing boot artifact: $file"
done

backup="$EXP_HOME/metadata/grub-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
sudo cp -a /boot/grub/grub.cfg "$backup/grub.cfg.boot"
sudo cp -a /boot/efi/boot/grub/grub.cfg "$backup/grub.cfg.esp"
sudo cp -a /boot/grub/grubenv "$backup/grubenv.boot" || true
sudo cp -a /boot/efi/boot/grub/grubenv "$backup/grubenv.esp" || true
sudo chown -R "$(id -u):$(id -g)" "$backup"

sudo install -m 0755 "$SCRIPT_DIR/41_d3000_kvm_modes" /etc/grub.d/41_d3000_kvm_modes
sudo update-grub

# The EFI stub on this D3000 uses the ESP copy. Keep it byte-identical to the
# generated /boot copy; update-grub alone writes only the latter.
sudo install -m 0644 /boot/grub/grub.cfg /boot/efi/boot/grub/grub.cfg
sudo grub-script-check /boot/grub/grub.cfg
sudo grub-script-check /boot/efi/boot/grub/grub.cfg
sudo cmp /boot/grub/grub.cfg /boot/efi/boot/grub/grub.cfg

for id in d3000-6.6.30-nvhe d3000-6.6.30-protected; do
    grep -Fq -- "--id '$id'" /boot/efi/boot/grub/grub.cfg || die "GRUB entry not generated: $id"
done
sudo grep -q '^GRUB_DEFAULT=0$' /etc/default/grub || die "GRUB_DEFAULT is no longer index 0"
sudo grub-editenv /boot/efi/boot/grub/grubenv unset next_entry || true
sudo grub-editenv /boot/grub/grubenv unset next_entry || true
record_note grub "installed audited nVHE/protected entries; backup=$backup; active and secondary grub.cfg identical"
log "installed one-shot nVHE/protected GRUB entries; default entry remains VHE index 0"
