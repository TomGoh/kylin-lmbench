#!/usr/bin/env bash
# Temporarily strip the host environment to approximate a minimal benchmark
# guest: stop the desktop layer + non-essential daemons before a bench run,
# restore them after. Idempotent.
#
# Usage:
#   sudo ./quiet-host.sh quiet     # stop noisy services (and isolate multi-user)
#   sudo ./quiet-host.sh restore   # bring services back, return to graphical
#   sudo ./quiet-host.sh status    # show which curated services are active
#
# Design choice: we DO NOT stop:
#   - dbus / polkit       (KYSEC depends on them)
#   - ksaf-* / kyseclogd  (LSM userspace — keeping these matches guest behavior
#                          because guest also runs them; turning them off would
#                          flip kysec from "active+consuming records" to
#                          "active+queue-only" which is a different state)
#   - auditd              (we want audit records consumed, not backlogged)
#   - rpcbind             (lat_rpc needs it)
#   - ssh                 (we connect via it)
#   - systemd-journald/logind/udevd (system stability)
set -euo pipefail

# Curated list of services that are pure noise for OS-microbenchmarks.
# Sorted, not bundled by category, so individual items are easy to add/remove.
NOISY=(
  accounts-daemon.service
  auserver.service
  avahi-daemon.service
  biometric-authentication.service
  bluetooth.service
  com.kylin-os-manager.service
  cron.service
  cups.service
  dnsmasq.service
  kylin-core-dump-monitor.service
  kylin-daq.service
  kylin-endisk-daemon.service
  kylin-nm-sysdbus.service
  kylin-os-manager-driver-acquirer.service
  kylin-printer-applet-dbus.service
  kylin-process-manager-daemon.service
  kylin-process-resource-manager-daemon.service
  kylin-unattended-upgrades.service
  kytensor.service
  lightdm.service
  logrotate_chkdisk.service
  # NetworkManager.service       # NEVER stop remotely — owns wired interface
                                  # on KylinOS desktop, kills SSH connectivity.
  # nm-enhance-optimization.service  # depends on NetworkManager
  oem-privacy-key.service
  OptiDaemon.service
  org.kylin.kaiming.service
  rsyslog.service
  smartmontools.service
  strongswan-starter.service
  systemd-resolved.service
  systemd-timesyncd.service
  udisks2.service
  ukui-bluetooth.service
  ukui-input-gather.service
  ukui-media-control-mute-led.service
  ukui-system-service-manager.service
  upower.service
  uuidd.service
  vulnerabilityrepair.service
  wpa_supplicant.service
)

if [ "$(id -u)" -ne 0 ]; then exec sudo -E bash "$0" "$@"; fi

# Safety guard: refuse to stop any service whose name matches networking
# infrastructure — those will kill remote SSH.
NEVER_STOP_RE='^(NetworkManager|systemd-networkd|networking|ssh|sshd|wicked|netplan)'
for s in "${NOISY[@]}"; do
  if [[ "$s" =~ $NEVER_STOP_RE ]]; then
    echo "[quiet-host] FATAL: refusing to include $s in stop list" >&2
    exit 3
  fi
done

cmd="${1:-status}"
case "$cmd" in
  quiet)
    # NB: deliberately do NOT call `systemctl isolate multi-user.target` —
    # would risk dropping the remote SSH user.slice on some kylin setups.
    # Stop services individually so logind / sshd / user sessions survive.
    echo "[quiet-host] stopping ${#NOISY[@]} noisy services"
    for s in "${NOISY[@]}"; do
      if systemctl is-active --quiet "$s"; then
        systemctl stop "$s" 2>/dev/null && echo "  stopped $s" || echo "  FAILED $s"
      fi
    done
    echo "[quiet-host] active running services now: $(systemctl list-units --type=service --state=running --no-pager --no-legend | wc -l)"
    echo "[quiet-host] tip: 'btop' should show a much idler box"
    ;;
  restore)
    echo "[quiet-host] restoring services"
    for s in "${NOISY[@]}"; do
      systemctl start "$s" 2>/dev/null && echo "  started $s" || echo "  FAILED $s"
    done
    echo "[quiet-host] all done"
    ;;
  status)
    echo "[quiet-host] curated service state:"
    for s in "${NOISY[@]}"; do
      st=$(systemctl is-active "$s" 2>/dev/null)
      printf "  %-50s %s\n" "$s" "$st"
    done
    echo
    echo "current default target: $(systemctl get-default)"
    echo "active running services: $(systemctl list-units --type=service --state=running --no-pager --no-legend | wc -l)"
    ;;
  *)
    echo "usage: $0 {quiet|restore|status}" >&2
    exit 2
    ;;
esac
