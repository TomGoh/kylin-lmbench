#!/usr/bin/env bash
# One-shot driver around lmbench's own scripts/lmbench.
#
# For each requested core, runs the full lmbench suite N times (each invocation
# pinned via taskset), saving raw reports to results/<env>-cpu<N>-iter<I>.txt,
# then parses everything into a single long-format CSV.
#
# Usage:
#   ./bench.sh                              # ENV_TAG=pkvm-host CORES=0,3 ITERS=10
#   CORES=0 ITERS=2 ./bench.sh              # quick smoke
#   ENV_TAG=baremetal ./bench.sh --no-prep  # already-prepared host
#   CONFIG=configs/CONFIG.kvm-guest CORES=0,1 ENV_TAG=kvm-guest ./bench.sh
#
# Layout:
#   results/<env>-cpu<N>-iter<I>.txt    raw lmbench report (stderr capture)
#   results/<env>-cpu<N>.csv            parsed, all iters merged for this core
#   results/<env>-summary.txt           run metadata
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

ENV_TAG="${ENV_TAG:-pkvm-host}"
CORES="${CORES:-0,3}"
ITERS="${ITERS:-10}"
CONFIG="${CONFIG:-configs/CONFIG.host}"
DO_PREP=1
for arg in "$@"; do
  case "$arg" in
    --no-prep) DO_PREP=0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# absolute paths because scripts/lmbench must run from bin/aarch64-Linux/
CONFIG_ABS="$HERE/$CONFIG"
SCRIPT_ABS="$HERE/scripts/lmbench"
BIN_DIR="$HERE/bin/aarch64-Linux"
PARSER="$HERE/parse-lmbench.py"

[ -f "$CONFIG_ABS" ] || { echo "config not found: $CONFIG_ABS" >&2; exit 1; }
[ -x "$BIN_DIR/lat_syscall" ] || { echo "lmbench not built; running make build" >&2; make build >/dev/null 2>&1; }

if [ "$DO_PREP" = "1" ]; then
  bash ./prepare-host.sh
fi

mkdir -p results
STAMP="$(date +%Y%m%d-%H%M%S)"
SUMMARY="results/${ENV_TAG}-${STAMP}-summary.txt"
{
  echo "env=$ENV_TAG  cores=$CORES  iters=$ITERS  config=$CONFIG  started=$(date -Iseconds)"
  echo "kernel=$(uname -r)"
  echo "cmdline=$(cat /proc/cmdline)"
  echo "cpu_max_freqs: $(for c in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_max_freq; do cat "$c"; done | tr '\n' ' ')"
} > "$SUMMARY"

IFS=, read -ra CORE_LIST <<< "$CORES"
for core in "${CORE_LIST[@]}"; do
  CSV="results/${ENV_TAG}-cpu${core}.csv"
  echo "[bench] === cpu${core} (env=${ENV_TAG}) — $ITERS iters ==="

  RAWS=()
  for i in $(seq 1 "$ITERS"); do
    RAW="results/${ENV_TAG}-cpu${core}-iter${i}.txt"
    RAWS+=("$RAW")
    printf '  [iter %d/%d cpu%d] ' "$i" "$ITERS" "$core"
    START=$(date +%s)
    # scripts/lmbench expects cwd to be bin/aarch64-Linux so PATH=. finds tools.
    ( cd "$BIN_DIR" && taskset -c "$core" bash "$SCRIPT_ABS" "$CONFIG_ABS" ) 2> "$RAW"
    END=$(date +%s)
    printf '%ds\n' "$((END-START))"
  done

  echo "[bench] parsing $core -> $CSV"
  "$PARSER" "${RAWS[@]}" > "$CSV" 2> "results/${ENV_TAG}-cpu${core}-parse.err"
  ROWS=$(($(wc -l < "$CSV") - 1))
  UNPARSED=$(wc -l < "results/${ENV_TAG}-cpu${core}-parse.err")
  echo "  $ROWS data rows, $UNPARSED unparsed lines (see *-parse.err)"
done

echo "[bench] done. summary: $SUMMARY"
