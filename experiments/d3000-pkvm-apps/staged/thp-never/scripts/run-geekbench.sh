#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

GEEKBENCH="$TOOLS_DIR/geekbench-6.7.1/geekbench6"
[[ -x "$GEEKBENCH" ]] || die "Geekbench executable missing: $GEEKBENCH"
printf '%s  %s\n' "$GEEKBENCH_SHA256" "$GEEKBENCH_ARCHIVE" | sha256sum --check >/dev/null
set_project_thp geekbench

out=$(run_dir geekbench cpu 0)
record_note geekbench "start CPU suite output=$out"
rm -rf "$out"; mkdir -p "$out/warmup"
capture_metadata "$out/metadata"

log "Geekbench non-scoring warmup"
/usr/bin/time -v -o "$out/warmup/time.txt" taskset -c "$ALL_CPUS" "$GEEKBENCH" --cpu \
    >"$out/warmup/stdout.txt" 2>"$out/warmup/stderr.txt"
cooldown

for rep in $(seq 1 "$REPETITIONS"); do
    repdir=$(printf '%s/rep-%02d' "$out" "$rep")
    mkdir -p "$repdir"
    log "Geekbench formal run $rep/$REPETITIONS"
    /usr/bin/time -v -o "$repdir/time.txt" taskset -c "$ALL_CPUS" "$GEEKBENCH" --cpu \
        >"$repdir/stdout.txt" 2>"$repdir/stderr.txt"
    grep -Eo 'https?://[^[:space:]]+' "$repdir/stdout.txt" >"$repdir/result-urls.txt" || true
    touch "$repdir/VALID"
    cooldown
done
touch "$out/VALID"
record_note geekbench "valid CPU suite with $REPETITIONS scored runs output=$out"
log "completed Geekbench CPU suite"
