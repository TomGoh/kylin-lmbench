#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_layout
space_guard

for online in /sys/devices/system/cpu/cpu[0-9]*/online; do
    printf '1\n' | sudo tee "$online" >/dev/null || true
done
for governor in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do
    printf 'performance\n' | sudo tee "$governor" >/dev/null
done

printf '2\n' | sudo tee /proc/sys/kernel/randomize_va_space >/dev/null
if systemctl is-active --quiet graphical.target; then
    sudo systemctl isolate multi-user.target
fi
sudo swapoff -a

# Confirm all eight CPUs are online and locked at the expected policy.
[[ $(cat /sys/devices/system/cpu/online) == '0-7' ]] || die "unexpected online CPU mask: $(cat /sys/devices/system/cpu/online)"
if grep -L '^performance$' /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor | grep -q .; then
    die "not all CPUs use the performance governor"
fi
[[ -z $(swapon --show --noheadings) ]] || die "swap remains active"

mkdir -p "$STATE_DIR"
touch "$STATE_DIR/host-prepared"
record_note host "prepared CPUs=0-7 governor=performance ASLR=2 swap=off target=multi-user"
log "host prepared: CPUs=0-7 governor=performance ASLR=2 swap=off target=multi-user"
