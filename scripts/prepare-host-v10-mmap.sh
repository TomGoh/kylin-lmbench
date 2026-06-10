#!/usr/bin/env bash
# Kylin V10 host preparation for mmap-only lmbench runs.
#
# This intentionally does not stop networking/SSH services. It prepares the
# current boot for a pinned single-core benchmark by:
#   - stopping desktop/Kylin/security/update background services
#   - locking all CPUs to a common fixed frequency
#   - disabling THP and ASLR
#   - moving movable IRQs away from the benchmark core
set -euo pipefail

TEST_CORE="${TEST_CORE:-0}"
TARGET_KHZ="${TARGET_KHZ:-auto}"

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E TEST_CORE="$TEST_CORE" TARGET_KHZ="$TARGET_KHZ" bash "$0" "$@"
fi

log() { echo "[prepare-v10-mmap] $*"; }

log "preserving network/SSH services; not stopping NetworkManager, ssh, wpa_supplicant, resolved, dbus"

STOP_SERVICES=(
  lightdm
  accounts-daemon
  acpid
  atd
  auditd
  auserver
  avahi-daemon
  biometric-authentication
  bluetooth
  com.kylin-os-manager
  cron
  cups
  dnsmasq
  getty@tty1
  haveged
  kyfs-fuse
  kylin-process-manager-daemon
  kylin-system-updater
  kylin-unattended-upgrades
  kysdk-conf2
  kysdk-logrotate
  kysdk-logsec-daemon
  kysdk-systime
  kysec-daemon
  kysec-sync-daemon
  kyseclogd
  logrotate_chkdisk
  oem-privacy-key
  rsyslog
  serial-getty@ttyAMA0
  serviceavserver
  smartmontools
  systemd-drop-cache
  systemd-timesyncd
  tee-supplicant
  udisks2
  ukui-bluetooth
  ukui-input-gather
  ukui-media-control-mute-led
  upower
  vddaemon
)

log "stopping non-network background services"
for svc in "${STOP_SERVICES[@]}"; do
  systemctl stop "${svc}.service" 2>/dev/null || true
done

KILL_PATTERN='Xorg|ukui|peony|pulseaudio|kylin-software-center|kylin-printer|avserver|serviceav|auserver|kysec-sync|kyseclogd|kysec-daemon|kysdk-log|kysdk-systime|kyfs-fuse|bluetoothd|cupsd|avahi-daemon|dnsmasq|udisksd|upowerd|haveged|auditd'
log "killing leftover desktop/security helper processes"
pkill -9 -f "$KILL_PATTERN" 2>/dev/null || true

if [ "$TARGET_KHZ" = "auto" ]; then
  TARGET_KHZ=""
  for maxf in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/cpuinfo_max_freq; do
    [ -e "$maxf" ] || continue
    v=$(cat "$maxf")
    if [ -z "$TARGET_KHZ" ] || [ "$v" -lt "$TARGET_KHZ" ]; then
      TARGET_KHZ="$v"
    fi
  done
  TARGET_KHZ="${TARGET_KHZ:-2100000}"
fi

log "locking all CPUs to ${TARGET_KHZ} kHz, governor=performance"
for c in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
  [ -d "$c" ] || continue
  echo performance > "$c/scaling_governor" 2>/dev/null || true
  cur_min=$(cat "$c/scaling_min_freq" 2>/dev/null || echo 0)
  if [ "$TARGET_KHZ" -lt "$cur_min" ]; then
    echo "$TARGET_KHZ" > "$c/scaling_min_freq" 2>/dev/null || true
    echo "$TARGET_KHZ" > "$c/scaling_max_freq" 2>/dev/null || true
  else
    echo "$TARGET_KHZ" > "$c/scaling_max_freq" 2>/dev/null || true
    echo "$TARGET_KHZ" > "$c/scaling_min_freq" 2>/dev/null || true
  fi
done

if [ -e /sys/kernel/mm/transparent_hugepage/enabled ]; then
  log "THP -> never"
  echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
fi

log "ASLR -> 0"
echo 0 > /proc/sys/kernel/randomize_va_space

if [ -d /sys/devices/system/cpu/cpu0/cpuidle ]; then
  log "disabling deep cpuidle states"
  for s in /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state[1-9]*/disable; do
    [ -e "$s" ] && echo 1 > "$s" || true
  done
fi

if [ -d /proc/irq ]; then
  ncpu=$(getconf _NPROCESSORS_ONLN)
  away=""
  for cpu in $(seq 0 $((ncpu - 1))); do
    [ "$cpu" = "$TEST_CORE" ] && continue
    away="${away}${away:+,}${cpu}"
  done
  if [ -n "$away" ]; then
    log "moving movable IRQs away from cpu${TEST_CORE}: ${away}"
    for f in /proc/irq/*/smp_affinity_list; do
      [ -w "$f" ] || continue
      echo "$away" > "$f" 2>/dev/null || true
    done
  fi
fi

log "verification"
echo "  cmdline=$(cat /proc/cmdline)"
echo "  lsm=$(cat /sys/kernel/security/lsm 2>/dev/null || echo n/a)"
echo "  THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo n/a)"
echo "  ASLR=$(cat /proc/sys/kernel/randomize_va_space)"
for c in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
  [ -d "$c" ] || continue
  cpu="${c%/cpufreq}"; cpu="${cpu##*/cpu}"
  printf "  cpu%s cur=%s min=%s max=%s gov=%s\n" "$cpu" \
    "$(cat "$c/scaling_cur_freq" 2>/dev/null || echo n/a)" \
    "$(cat "$c/scaling_min_freq" 2>/dev/null || echo n/a)" \
    "$(cat "$c/scaling_max_freq" 2>/dev/null || echo n/a)" \
    "$(cat "$c/scaling_governor" 2>/dev/null || echo n/a)"
done
echo "  top_user_processes:"
ps -eo pid,ppid,psr,pcpu,comm,args --sort=-pcpu | head -20 | sed 's/^/    /'

log "done"
