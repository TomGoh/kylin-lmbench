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

echo "[bench-in-guest] guest prep state:"
echo "  THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null)"
echo "  ASLR=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)"

# KYSEC fingerprint via the shared probe — identical code path to the host's
# bench.sh, so the two fingerprints are directly comparable. Compare the
# `class=` token on both sides: they MUST match (target: class=off) or the
# host-vs-guest delta is a KYSEC artifact, not a hypervisor cost. See
# docs/KYSEC-OFF.md.
GUEST_KYSEC_FP="$(bash /opt/lmbench/kysec-probe.sh)"
echo "[bench-in-guest] $GUEST_KYSEC_FP"

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
  echo "$GUEST_KYSEC_FP"
} > /opt/lmbench/results/last-run.meta
