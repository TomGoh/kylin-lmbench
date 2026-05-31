#!/usr/bin/env bash
# Host preparation: deterministic state for KVM/pKVM overhead measurements.
# Idempotent. Requires sudo (will prompt once if needed).
# Knobs via env: TARGET_KHZ (default 1900000), DISABLE_THP (default 1),
# DISABLE_ASLR (default 1), DISABLE_DEEP_IDLE (default 1).
set -eu
TARGET_KHZ="${TARGET_KHZ:-1900000}"
DISABLE_THP="${DISABLE_THP:-1}"
DISABLE_ASLR="${DISABLE_ASLR:-1}"
DISABLE_DEEP_IDLE="${DISABLE_DEEP_IDLE:-1}"

if [ "$(id -u)" -ne 0 ]; then
  echo "[prepare-host] elevating with sudo..." >&2
  exec sudo -E TARGET_KHZ="$TARGET_KHZ" DISABLE_THP="$DISABLE_THP" \
              DISABLE_ASLR="$DISABLE_ASLR" DISABLE_DEEP_IDLE="$DISABLE_DEEP_IDLE" \
              bash "$0" "$@"
fi

echo "[prepare-host] locking all CPUs to ${TARGET_KHZ} kHz, governor=performance"
for c in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
  echo performance > "$c/scaling_governor"
  # Order matters: lower max before raising min (and vice versa) to avoid
  # 'max < min' transient rejections.
  cur_min=$(cat "$c/scaling_min_freq")
  if [ "$TARGET_KHZ" -lt "$cur_min" ]; then
    echo "$TARGET_KHZ" > "$c/scaling_min_freq"
    echo "$TARGET_KHZ" > "$c/scaling_max_freq"
  else
    echo "$TARGET_KHZ" > "$c/scaling_max_freq"
    echo "$TARGET_KHZ" > "$c/scaling_min_freq"
  fi
done

if [ "$DISABLE_DEEP_IDLE" = "1" ]; then
  echo "[prepare-host] disabling deep cpuidle states (keeping state0 only)"
  for s in /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state[1-9]*/disable; do
    [ -e "$s" ] && echo 1 > "$s" || true
  done
fi

if [ "$DISABLE_THP" = "1" ] && [ -e /sys/kernel/mm/transparent_hugepage/enabled ]; then
  echo "[prepare-host] THP -> never"
  echo never > /sys/kernel/mm/transparent_hugepage/enabled
fi

if [ "$DISABLE_ASLR" = "1" ]; then
  echo "[prepare-host] ASLR off"
  echo 0 > /proc/sys/kernel/randomize_va_space
fi

# rpcbind needed by lat_rpc (it registers a transient service).
# Failure is non-fatal; lmbench will just skip RPC numbers gracefully.
if command -v rpcbind >/dev/null 2>&1; then
  if ! pgrep -x rpcbind >/dev/null 2>&1; then
    echo "[prepare-host] starting rpcbind for lat_rpc"
    rpcbind 2>/dev/null || echo "[prepare-host] rpcbind start failed; lat_rpc data will be empty" >&2
  fi
fi

echo "[prepare-host] verification:"
for c in 0 3 7; do
  [ -e /sys/devices/system/cpu/cpu$c/cpufreq/scaling_cur_freq ] || continue
  printf "  cpu%d: cur=%s gov=%s\n" "$c" \
    "$(cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_cur_freq)" \
    "$(cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_governor)"
done
printf "  THP=%s  ASLR=%s\n" \
  "$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo n/a)" \
  "$(cat /proc/sys/kernel/randomize_va_space)"
echo "[prepare-host] done"
