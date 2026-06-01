#!/usr/bin/env bash
# Inside-guest entrypoint. Invoked by root's .bash_profile on autologin
# when the marker /opt/lmbench/autorun is present.
#
# Steps:
#   1. Start rpcbind so lat_rpc has data (best-effort).
#   2. Run bench.sh with the env tag and core list read from /opt/lmbench/autorun
#      (or fall back to safe defaults).
#   3. On completion, leave shell so caller can scrape results from
#      /opt/lmbench/results/ via virtio-blk (powered-off guest's image mount).
#
# Marker file format (key=value, one per line, all optional):
#   ENV_TAG=pkvm-guest-np
#   CORES=0,1
#   ITERS=10
#   CONFIG=configs/CONFIG.pkvm-guest
set -u

MARKER=/opt/lmbench/autorun
cd /opt/lmbench

# defaults
ENV_TAG=guest
CORES=0,1
ITERS=10
CONFIG=configs/CONFIG.pkvm-guest

if [ -f "$MARKER" ]; then
  # shellcheck disable=SC1090
  . "$MARKER"
fi

systemctl start rpcbind 2>/dev/null || rpcbind 2>/dev/null || true

# in-guest prep — backstop in case systemd or kysec flipped a knob during
# boot. Mirrors prepare-host.sh for the things visible inside a guest.
echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
echo 0     > /proc/sys/kernel/randomize_va_space 2>/dev/null || true
echo 0     > /proc/sys/kernel/numa_balancing 2>/dev/null || true
# (cpufreq sysfs absent in guest — vCPU follows host frequency.)

echo "[bench-in-guest] guest state:"
echo "  THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null)"
echo "  ASLR=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)"
echo "  LSM=$(cat /sys/kernel/security/lsm 2>/dev/null)"
echo "  /proc/cmdline=$(cat /proc/cmdline)"
echo "  KYSEC userspace:"
for s in ksaf-devctl-sync-daemon ksaf-label-manager ksaf-policy-init \
         kyseclogd kysec-scene-init auditd kysec2-kbox-load; do
  printf "    %-30s %s\n" "$s" "$(systemctl is-active "$s" 2>&1)"
done
echo "  /sys/fs/box=$(ls /sys/fs/box 2>&1 | head -1)"
echo "  /sys/kernel/security listing=$(ls /sys/kernel/security 2>&1 | tr "\n" " ")"
echo "  auditctl -s:"
auditctl -s 2>&1 | sed 's/^/    /'
echo "  auditctl -l (rules count):"
echo "    $(auditctl -l 2>&1 | wc -l)"
auditctl -l 2>&1 | head -3 | sed 's/^/    /'
echo "  BPF programs loaded:"
echo "    count=$(bpftool prog show 2>/dev/null | grep -c '^[0-9]')"
bpftool prog show 2>/dev/null | grep -E '^[0-9]' | awk '{print $2, $4}' | sort | uniq -c | sed 's/^/      /'
echo "  kprobes attached: $(cat /sys/kernel/tracing/kprobe_events 2>/dev/null | wc -l)"
echo "  uprobes attached: $(cat /sys/kernel/tracing/uprobe_events 2>/dev/null | wc -l)"
echo "  ftrace current: $(cat /sys/kernel/tracing/current_tracer 2>/dev/null)"
echo "  tracepoints enabled: $(find /sys/kernel/tracing/events -name enable -exec grep -l '^1$' {} \; 2>/dev/null | wc -l)"

echo "[bench-in-guest] ENV_TAG=$ENV_TAG CORES=$CORES ITERS=$ITERS CONFIG=$CONFIG"
echo "[bench-in-guest] starting at $(date -Iseconds)"
ENV_TAG="$ENV_TAG" CORES="$CORES" ITERS="$ITERS" CONFIG="$CONFIG" \
  ./bench.sh --no-prep
EXIT=$?
echo "[bench-in-guest] finished at $(date -Iseconds) (exit=$EXIT)"

# leave a breadcrumb of what ran for the host-side scraper
{
  echo "completed_at=$(date -Iseconds)"
  echo "exit_status=$EXIT"
  echo "env_tag=$ENV_TAG"
  echo "cores=$CORES"
  echo "iters=$ITERS"
  echo "config=$CONFIG"
} > /opt/lmbench/results/last-run.meta
