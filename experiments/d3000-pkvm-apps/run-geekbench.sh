#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

GEEKBENCH="$TOOLS_DIR/geekbench-6.7.1/geekbench6"
GEEKBENCH_TIMEOUT_SECONDS=${GEEKBENCH_TIMEOUT_SECONDS:-1200}
GEEKBENCH_MAX_ATTEMPTS=${GEEKBENCH_MAX_ATTEMPTS:-3}
[[ -x "$GEEKBENCH" ]] || die "Geekbench executable missing: $GEEKBENCH"
printf '%s  %s\n' "$GEEKBENCH_SHA256" "$GEEKBENCH_ARCHIVE" | sha256sum --check >/dev/null
set_project_thp geekbench

out=$(run_dir geekbench cpu 0)
record_note geekbench "start CPU suite output=$out"
rm -rf "$out"; mkdir -p "$out"
capture_metadata "$out/metadata"

run_suite() {
    local target=$1 label=$2 attempt attempt_dir failed_dir rc started_at
    for attempt in $(seq 1 "$GEEKBENCH_MAX_ATTEMPTS"); do
        attempt_dir="$out/.${label}-attempt-$(printf '%02d' "$attempt")"
        failed_dir="$out/failed-${label}-attempt-$(printf '%02d' "$attempt")"
        rm -rf "$attempt_dir" "$failed_dir"
        mkdir -p "$attempt_dir"
        started_at=$(timestamp)
        {
            printf 'label=%s\n' "$label"
            printf 'attempt=%s\n' "$attempt"
            printf 'started_at=%s\n' "$started_at"
            printf 'timeout_seconds=%s\n' "$GEEKBENCH_TIMEOUT_SECONDS"
        } >"$attempt_dir/attempt.env"
        log "Geekbench $label attempt $attempt/$GEEKBENCH_MAX_ATTEMPTS"
        if timeout --signal=TERM --kill-after=30s "${GEEKBENCH_TIMEOUT_SECONDS}s" \
            /usr/bin/time -v -o "$attempt_dir/time.txt" taskset -c "$ALL_CPUS" "$GEEKBENCH" --cpu \
            >"$attempt_dir/stdout.txt" 2>"$attempt_dir/stderr.txt"; then
            printf 'finished_at=%s\nrc=0\n' "$(timestamp)" >>"$attempt_dir/attempt.env"
            rm -rf "$target"
            mv "$attempt_dir" "$target"
            record_note geekbench "valid label=$label attempt=$attempt output=$target"
            return 0
        else
            rc=$?
        fi
        printf 'finished_at=%s\nrc=%s\n' "$(timestamp)" "$rc" >>"$attempt_dir/attempt.env"
        mv "$attempt_dir" "$failed_dir"
        record_note geekbench "failed label=$label attempt=$attempt rc=$rc output=$failed_dir"
        if (( attempt < GEEKBENCH_MAX_ATTEMPTS )); then cooldown; fi
    done
    die "Geekbench $label failed after $GEEKBENCH_MAX_ATTEMPTS attempts"
}

log "Geekbench non-scoring warmup"
run_suite "$out/warmup" warmup
cooldown

for rep in $(seq 1 "$REPETITIONS"); do
    repdir=$(printf '%s/rep-%02d' "$out" "$rep")
    log "Geekbench formal run $rep/$REPETITIONS"
    run_suite "$repdir" "rep-$(printf '%02d' "$rep")"
    grep -Eo 'https?://[^[:space:]]+' "$repdir/stdout.txt" >"$repdir/result-urls.txt" || true
    touch "$repdir/VALID"
    cooldown
done
touch "$out/VALID"
record_note geekbench "valid CPU suite with $REPETITIONS scored runs output=$out"
log "completed Geekbench CPU suite"
