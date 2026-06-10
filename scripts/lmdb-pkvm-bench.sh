#!/usr/bin/env bash
# Run the local LMDB benchmark for one host mode.
#
# Usage:
#   MODE=kvmoff bash scripts/lmdb-pkvm-bench.sh
#   MODE=pkvm   bash scripts/lmdb-pkvm-bench.sh
#
# Suggested flow per boot:
#   sudo ./prepare-host.sh
#   MODE=<kvmoff|vhe|nvhe|pkvm> FRESH=1 bash scripts/lmdb-pkvm-bench.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${MODE:-${1:-unknown}}"
BIN="${BIN:-$ROOT/bin/lmdb-pkvm-bench}"
SRC="$ROOT/scripts/lmdb-pkvm-bench.c"
OUTDIR="${OUTDIR:-$ROOT/results/lmdb-bench/$MODE}"
DBDIR="${DBDIR:-/tmp/lmdb-pkvm-bench-db-$MODE}"

RECORDS="${RECORDS:-1000000}"
VALUE_SIZE="${VALUE_SIZE:-256}"
MAP_MB="${MAP_MB:-4096}"
BATCH="${BATCH:-1000}"
READ_OPS="${READ_OPS:-5000000}"
TXN_BATCH="${TXN_BATCH:-1000}"
WRITE_RECORDS="${WRITE_RECORDS:-200000}"
OPENCLOSE_ITERS="${OPENCLOSE_ITERS:-1000}"
RUNS="${RUNS:-5}"
NOSYNC="${NOSYNC:-1}"
SEED="${SEED:-12345}"
FRESH="${FRESH:-0}"

mkdir -p "$ROOT/bin" "$OUTDIR"

if [ ! -x "$BIN" ] || [ "$SRC" -nt "$BIN" ]; then
    echo "[lmdb-bench] building $BIN"
    cc -O2 -Wall -Wextra -o "$BIN" "$SRC" -ldl
fi

if [ "$FRESH" = "1" ]; then
    case "$DBDIR" in
        /tmp/lmdb-pkvm-bench-db-*|"$ROOT"/results/lmdb-bench/*/db)
            echo "[lmdb-bench] removing old DB: $DBDIR"
            rm -rf "$DBDIR"
            ;;
        *)
            echo "[lmdb-bench] refusing to remove unsafe DBDIR: $DBDIR" >&2
            exit 2
            ;;
    esac
fi

{
    echo "mode=$MODE"
    echo "date=$(date -Is)"
    echo "root=$ROOT"
    echo "dbdir=$DBDIR"
    echo "records=$RECORDS"
    echo "value_size=$VALUE_SIZE"
    echo "map_mb=$MAP_MB"
    echo "batch=$BATCH"
    echo "read_ops=$READ_OPS"
    echo "txn_batch=$TXN_BATCH"
    echo "write_records=$WRITE_RECORDS"
    echo "openclose_iters=$OPENCLOSE_ITERS"
    echo "runs=$RUNS"
    echo "nosync=$NOSYNC"
    echo "seed=$SEED"
    echo "uname=$(uname -a)"
    echo "cmdline=$(cat /proc/cmdline 2>/dev/null || true)"
    echo "lsm=$(cat /sys/kernel/security/lsm 2>/dev/null || true)"
    echo "thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true)"
    echo "aslr=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null || true)"
} > "$OUTDIR/environment.txt"

echo "[lmdb-bench] preparing DB at $DBDIR"
"$BIN" prepare "$DBDIR" "$RECORDS" "$VALUE_SIZE" "$MAP_MB" "$BATCH" "$NOSYNC" \
    > "$OUTDIR/prepare.csv"

for run in $(seq 1 "$RUNS"); do
    echo "[lmdb-bench] run $run/$RUNS openclose"
    "$BIN" openclose "$DBDIR" "$OPENCLOSE_ITERS" "$MAP_MB" \
        > "$OUTDIR/openclose-run${run}.csv"

    echo "[lmdb-bench] run $run/$RUNS read"
    "$BIN" read "$DBDIR" "$READ_OPS" "$TXN_BATCH" "$((SEED + run))" \
        > "$OUTDIR/read-run${run}.csv"

    echo "[lmdb-bench] run $run/$RUNS write"
    "$BIN" write "$DBDIR" "$WRITE_RECORDS" "$VALUE_SIZE" "$MAP_MB" "$BATCH" "$NOSYNC" \
        > "$OUTDIR/write-run${run}.csv"
done

echo "[lmdb-bench] done: $OUTDIR"
