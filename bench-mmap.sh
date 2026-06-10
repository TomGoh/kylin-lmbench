#!/usr/bin/env bash
# mmap-only lmbench driver.
#
# Runs only the mmap-related lmbench items on one pinned CPU:
#   - lat_mmap
#   - bw_mmap_rd mmap_only
#   - bw_mmap_rd open2close
# Optionally parses the raw reports into results/<env>-cpu<core>.csv.
#
# Usage:
#   ENV_TAG=pkvm CORE=0 ITERS=10 ./bench-mmap.sh
#   ENV_TAG=vhe CORE=2 ITERS=10 RUN_PRECISE=0 ./bench-mmap.sh --no-prep
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

ENV_TAG="${ENV_TAG:-mmap-host}"
CORE="${CORE:-0}"
ITERS="${ITERS:-10}"
MB="${MB:-64}"
FILE="${FILE:-/tmp/lmb_mmap_file}"
RUN_PRECISE="${RUN_PRECISE:-1}"
PARSE="${PARSE:-1}"
DO_PREP=1

for arg in "$@"; do
  case "$arg" in
    --no-prep) DO_PREP=0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

BIN_DIR="$HERE/bin/aarch64-Linux"
LAT_MMAP="$BIN_DIR/lat_mmap"
BW_MMAP_RD="$BIN_DIR/bw_mmap_rd"
LMDD="$BIN_DIR/lmdd"
PARSER="$HERE/parse-lmbench.py"

if [ ! -x "$LAT_MMAP" ] || [ ! -x "$BW_MMAP_RD" ] || [ ! -x "$LMDD" ]; then
  echo "[bench-mmap] lmbench not built; running make build"
  make build >/dev/null
fi

if [ "$RUN_PRECISE" = "1" ] && [ ! -x "$BIN_DIR/lat_mmap_precise" ]; then
  echo "[bench-mmap] building lat_mmap_precise"
  gcc -O2 -o "$BIN_DIR/lat_mmap_precise" "$HERE/src/lat_mmap_precise.c"
fi

if [ "$DO_PREP" = "1" ]; then
  bash ./prepare-host.sh
fi

HALF="512 1k 2k 4k 8k 16k 32k 64k 128k 256k 512k 1m"
ALL="$HALF 2m"
LAT_MMAP_SIZES="512k 1m 2m"
i=4
while [ "$i" -le "$MB" ]; do
  ALL="$ALL ${i}m"
  LAT_MMAP_SIZES="$LAT_MMAP_SIZES ${i}m"
  i=$((i * 2))
done

mkdir -p results
STAMP="$(date +%Y%m%d-%H%M%S)"
SUMMARY="results/${ENV_TAG}-mmap-${STAMP}-summary.txt"
{
  echo "env=$ENV_TAG  core=$CORE  iters=$ITERS  mb=$MB  file=$FILE  run_precise=$RUN_PRECISE  started=$(date -Iseconds)"
  echo "kernel=$(uname -r)"
  echo "cmdline=$(cat /proc/cmdline)"
  if [ -e "/sys/devices/system/cpu/cpu${CORE}/cpufreq/scaling_cur_freq" ]; then
    echo "cpu${CORE}_cur_freq=$(cat "/sys/devices/system/cpu/cpu${CORE}/cpufreq/scaling_cur_freq")"
    echo "cpu${CORE}_governor=$(cat "/sys/devices/system/cpu/cpu${CORE}/cpufreq/scaling_governor")"
  fi
} > "$SUMMARY"

CSV="results/${ENV_TAG}-cpu${CORE}.csv"
RAWS=()

echo "[bench-mmap] env=${ENV_TAG} core=${CORE} iters=${ITERS} lat_mmap_sizes=${LAT_MMAP_SIZES} bw_sizes=${ALL}"
for iter in $(seq 1 "$ITERS"); do
  RAW="results/${ENV_TAG}-cpu${CORE}-iter${iter}.txt"
  RAWS+=("$RAW")
  printf '  [iter %d/%d cpu%s] ' "$iter" "$ITERS" "$CORE"
  START=$(date +%s)

  {
    echo "[mmap-only env=${ENV_TAG} core=${CORE} iter=${iter} started=$(date -Iseconds)]"
    echo "[fill backing file: $FILE ${MB}m]"
  } > "$RAW"

  rm -f "$FILE"
  taskset -c "$CORE" "$LMDD" of="$FILE" move="${MB}m" fsync=1 print=0 >> "$RAW" 2>&1

  {
    echo
    echo '"mappings'
  } >> "$RAW"
  for sz in $LAT_MMAP_SIZES; do
    taskset -c "$CORE" "$LAT_MMAP" -P 1 "$sz" "$FILE" >> "$RAW" 2>&1
  done

  {
    echo
    echo '"Mmap read bandwidth'
  } >> "$RAW"
  for sz in $ALL; do
    taskset -c "$CORE" "$BW_MMAP_RD" -P 1 "$sz" mmap_only "$FILE" >> "$RAW" 2>&1
  done

  {
    echo
    echo '"Mmap read open2close bandwidth'
  } >> "$RAW"
  for sz in $ALL; do
    taskset -c "$CORE" "$BW_MMAP_RD" -P 1 "$sz" open2close "$FILE" >> "$RAW" 2>&1
  done

  END=$(date +%s)
  printf '%ds\n' "$((END - START))"
done

if [ "$PARSE" = "1" ]; then
  if [ ! -x "$PARSER" ]; then
    echo "[bench-mmap] parser not found: $PARSER; skipping parse"
  else
    echo "[bench-mmap] parsing -> $CSV"
    "$PARSER" "${RAWS[@]}" > "$CSV" 2> "results/${ENV_TAG}-cpu${CORE}-parse.err"
    ROWS=$(($(wc -l < "$CSV") - 1))
    UNPARSED=$(wc -l < "results/${ENV_TAG}-cpu${CORE}-parse.err")
    echo "  $ROWS data rows, $UNPARSED unparsed lines (see results/${ENV_TAG}-cpu${CORE}-parse.err)"
  fi
else
  echo "[bench-mmap] PARSE=0; raw logs kept under results/"
fi

if [ "$RUN_PRECISE" = "1" ]; then
  echo "[bench-mmap] running precise mmap on core ${CORE}"
  CORE="$CORE" bash "$HERE/scripts/precise-mmap-bench.sh" "$ENV_TAG"
fi

echo "[bench-mmap] done. summary: $SUMMARY"
