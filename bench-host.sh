#!/usr/bin/env bash
# One-shot driver: prepare host -> run pilot suite -> run memory suite,
# on each requested core. Output goes to results/<env>-cpu<N>.{csv,log}.
#
# Usage:
#   ./bench-host.sh                   # default: ENV_TAG=pkvm-host, cores 0,3
#   CORES=0,3,7 ./bench-host.sh
#   ENV_TAG=baremetal ITERS=5 ./bench-host.sh --no-prep
#
# Flags:
#   --no-prep   skip host preparation (use when state is already set)
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

ENV_TAG="${ENV_TAG:-pkvm-host}"
CORES="${CORES:-0,3}"
ITERS="${ITERS:-10}"
DO_PREP=1
for arg in "$@"; do
  case "$arg" in
    --no-prep) DO_PREP=0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

if [ ! -x bin/aarch64-Linux/lat_syscall ]; then
  echo "[bench-host] lmbench not built — running make build" >&2
  make build >/dev/null 2>&1 || { echo "build failed"; exit 1; }
fi

if [ "$DO_PREP" = "1" ]; then
  bash ./prepare-host.sh
fi

mkdir -p results
STAMP="$(date +%Y%m%d-%H%M%S)"
SUMMARY="results/${ENV_TAG}-${STAMP}-summary.txt"
{
  echo "env=$ENV_TAG  cores=$CORES  iters=$ITERS  started=$(date -Iseconds)"
  echo "kernel=$(uname -r)  cmdline=$(cat /proc/cmdline)"
} > "$SUMMARY"

IFS=, read -ra CORE_LIST <<< "$CORES"
for core in "${CORE_LIST[@]}"; do
  CSV="results/${ENV_TAG}-cpu${core}.csv"
  LOG="results/${ENV_TAG}-cpu${core}.log"
  echo "[bench-host] === cpu${core} (env=${ENV_TAG}) ==="
  : > "$CSV"; : > "$LOG"
  echo "  -> $CSV"

  # tee stderr to both LOG (file) and stderr (terminal), keep stdout -> CSV.
  ITERS="$ITERS" CORE="$core" ENV_TAG="$ENV_TAG" bash ./run-pilot.sh \
    2> >(tee -a "$LOG" >&2) >>"$CSV"
  ITERS="$ITERS" CORE="$core" ENV_TAG="$ENV_TAG" bash ./run-mem.sh \
    2> >(tee -a "$LOG" >&2) >>"$CSV"

  echo "  rows: $(wc -l <"$CSV")  empties: $(awk -F, 'NR>1 && $6==""{c++} END{print c+0}' "$CSV")"
done

echo "[bench-host] done. summary: $SUMMARY"
