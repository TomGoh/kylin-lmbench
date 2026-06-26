#!/usr/bin/env bash
# Host-side runner for Pixel MADV per-entry slope experiments.
#
# This script does not switch KVM mode, reboot, fastboot, or flash. It assumes the
# phone is already in the desired mode and adb root is active. It pushes/runs the
# userspace probe under /data/local/tmp and records enough metadata to audit
# fairness: randomized task order, target CPU, frequency, thermal readings, and
# reject reasons.
set -euo pipefail

SERIAL="${SERIAL:-47091FDAS009VF}"
ADB="${ADB:-adb -s $SERIAL}"
LOCAL_BIN="${LOCAL_BIN:-experiments/munmap-tlbi/pixel_madv_entry_slope.android}"
REMOTE_BIN="${REMOTE_BIN:-/data/local/tmp/pixel_madv_entry_slope}"
OUT="${OUT:-experiments/munmap-tlbi/results/pixel-madv-entry-$(date +%Y%m%d-%H%M%S)}"
PAGES="${PAGES:-256,512,1024,2048,4096,8192}"
RUNS="${RUNS:-30}"
BLOCKS="${BLOCKS:-1}"
SEED="${SEED:-1}"
CPU="${CPU:-}"
COOLDOWN_SEC="${COOLDOWN_SEC:-2}"
FREQ_DROP_PCT="${FREQ_DROP_PCT:-5}"
THERMAL_RISE_MC="${THERMAL_RISE_MC:-3000}"

die() {
    echo "error: $*" >&2
    exit 1
}

adb_shell() {
    $ADB shell "$@" < /dev/null
}

mode_label() {
    adb_shell 'cat /proc/cmdline 2>/dev/null | tr " " "\n" | grep "^kvm-arm.mode=" | tail -1 | cut -d= -f2' \
        | tr -d '\r'
}

read_freq() {
    if [ -z "$CPU" ]; then
        echo ""
        return
    fi
    adb_shell "cat /sys/devices/system/cpu/cpu${CPU}/cpufreq/scaling_cur_freq 2>/dev/null || true" \
        | tr -d '\r'
}

read_thermal_max() {
    adb_shell 'for f in /sys/class/thermal/thermal_zone*/temp; do cat "$f" 2>/dev/null; done | sort -n | tail -1' \
        | tr -d '\r'
}

read_thermal() {
    adb_shell 'for z in /sys/class/thermal/thermal_zone*; do t=$(cat "$z/type" 2>/dev/null || echo unknown); v=$(cat "$z/temp" 2>/dev/null || echo NA); printf "%s=%s|" "$t" "$v"; done' \
        | tr -d '\r'
}

collect_metadata() {
    local dir="$1"
    mkdir -p "$dir"
    {
        echo "date=$(date -Is)"
        echo "serial=$SERIAL"
        echo "out=$OUT"
        echo "pages=$PAGES"
        echo "runs=$RUNS"
        echo "blocks=$BLOCKS"
        echo "seed=$SEED"
        echo "cpu=$CPU"
        echo "cooldown_sec=$COOLDOWN_SEC"
        echo "freq_drop_pct=$FREQ_DROP_PCT"
        echo "thermal_rise_mc=$THERMAL_RISE_MC"
        echo "--- adb devices ---"
        adb devices -l
        echo "--- uid ---"
        adb_shell 'id -u'
        echo "--- props ---"
        adb_shell 'getprop ro.product.device; getprop ro.product.model; getprop ro.boot.slot_suffix; getprop ro.boot.hypervisor.version; getprop ro.boot.flash.locked'
        echo "--- cmdline ---"
        adb_shell 'cat /proc/cmdline 2>/dev/null || true'
        echo "--- cpu topology ---"
        adb_shell 'for c in /sys/devices/system/cpu/cpu[0-9]*; do b=$(basename "$c"); printf "%s " "$b"; cat "$c/topology/core_id" 2>/dev/null || true; done'
        echo "--- freq ---"
        adb_shell 'for c in /sys/devices/system/cpu/cpu[0-9]*; do b=$(basename "$c"); printf "%s " "$b"; cat "$c/cpufreq/scaling_cur_freq" 2>/dev/null || true; done'
        echo "--- thermal ---"
        read_thermal
        echo
        echo "--- binary sha256 ---"
        sha256sum "$LOCAL_BIN" 2>/dev/null || true
    } > "$dir/metadata.txt"
}

combo_order() {
    python3 - "$PAGES" "$SEED" "$1" <<'PY'
import random
import sys

pages = [p for p in sys.argv[1].split(",") if p]
seed = int(sys.argv[2])
block = int(sys.argv[3])
tasks = []
for mode in ("single", "batched"):
    for touch in ("touched", "untouched"):
        for pages_value in pages:
            tasks.append((mode, touch, pages_value))
rng = random.Random(seed + block * 1000003)
rng.shuffle(tasks)
for task in tasks:
    print(":".join(task))
PY
}

reject_reason() {
    local freq_before="$1"
    local freq_after="$2"
    local thermal_before="$3"
    local thermal_after="$4"
    local reasons=()

    if [[ "$freq_before" =~ ^[0-9]+$ ]] && [[ "$freq_after" =~ ^[0-9]+$ ]] && [ "$freq_before" -gt 0 ]; then
        local min_freq=$((freq_before * (100 - FREQ_DROP_PCT) / 100))
        if [ "$freq_after" -lt "$min_freq" ]; then
            reasons+=("freq_drop")
        fi
    fi
    if [[ "$thermal_before" =~ ^[0-9]+$ ]] && [[ "$thermal_after" =~ ^[0-9]+$ ]]; then
        if [ $((thermal_after - thermal_before)) -gt "$THERMAL_RISE_MC" ]; then
            reasons+=("thermal_rise")
        fi
    fi

    if [ "${#reasons[@]}" -eq 0 ]; then
        echo "ok"
    else
        local IFS='|'
        echo "${reasons[*]}"
    fi
}

append_with_context() {
    local csv="$1"
    local block_id="$2"
    local task_index="$3"
    local live_mode="$4"
    local freq_before="$5"
    local freq_after="$6"
    local thermal_before="$7"
    local thermal_after="$8"
    local thermal_detail_before="$9"
    local thermal_detail_after="${10}"
    local reject="${11}"

    python3 - "$csv" "$block_id" "$task_index" "$live_mode" "$CPU" \
        "$freq_before" "$freq_after" "$thermal_before" "$thermal_after" \
        "$thermal_detail_before" "$thermal_detail_after" "$reject" <<'PY'
import csv
import sys

path = sys.argv[1]
context = {
    "block_id": sys.argv[2],
    "task_index": sys.argv[3],
    "mode_label": sys.argv[4],
    "cpu_target": sys.argv[5],
    "freq_before_khz": sys.argv[6],
    "freq_after_khz": sys.argv[7],
    "thermal_before_mc": sys.argv[8],
    "thermal_after_mc": sys.argv[9],
    "thermal_detail_before": sys.argv[10],
    "thermal_detail_after": sys.argv[11],
    "reject_reason": sys.argv[12],
}
with open(path, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(context) + list(reader.fieldnames or [])
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for row in reader:
        out = dict(context)
        out.update(row)
        writer.writerow(out)
PY
}

main() {
    [ -f "$LOCAL_BIN" ] || die "missing local binary: $LOCAL_BIN (run make -C experiments/munmap-tlbi android)"
    [ "$($ADB get-state 2>/dev/null | tr -d '\r')" = "device" ] || die "adb does not see $SERIAL"
    [ "$(adb_shell 'id -u' | tr -d '\r')" = "0" ] || die "adb is not root; run adb root and re-attach if WSL drops USB"

    mkdir -p "$OUT/raw" "$OUT/metadata"
    collect_metadata "$OUT/metadata"
    $ADB push "$LOCAL_BIN" "$REMOTE_BIN" >/dev/null
    adb_shell "chmod 755 '$REMOTE_BIN'"

    local live_mode
    live_mode="$(mode_label)"
    [ -n "$live_mode" ] || live_mode="unknown"
    local out_csv="$OUT/raw/${live_mode}_madv_entry.csv"
    : > "$out_csv"

    local header_written=0
    for block in $(seq 1 "$BLOCKS"); do
        local task_index=0
        while IFS=: read -r mode touch pages; do
            task_index=$((task_index + 1))
            local freq_before freq_after thermal_before thermal_after thermal_detail_before thermal_detail_after reject tmp
            freq_before="$(read_freq)"
            thermal_before="$(read_thermal_max)"
            thermal_detail_before="$(read_thermal)"
            tmp="$(mktemp)"
            if [ -n "$CPU" ]; then
                adb_shell "'$REMOTE_BIN' --mode '$mode' --touch '$touch' --pages '$pages' --runs '$RUNS' --no-shuffle --cpu '$CPU'" > "$tmp"
            else
                adb_shell "'$REMOTE_BIN' --mode '$mode' --touch '$touch' --pages '$pages' --runs '$RUNS' --no-shuffle" > "$tmp"
            fi
            freq_after="$(read_freq)"
            thermal_after="$(read_thermal_max)"
            thermal_detail_after="$(read_thermal)"
            reject="$(reject_reason "$freq_before" "$freq_after" "$thermal_before" "$thermal_after")"
            if [ "$header_written" -eq 0 ]; then
                append_with_context "$tmp" "$block" "$task_index" "$live_mode" \
                    "$freq_before" "$freq_after" "$thermal_before" "$thermal_after" \
                    "$thermal_detail_before" "$thermal_detail_after" "$reject" > "$out_csv"
                header_written=1
            else
                append_with_context "$tmp" "$block" "$task_index" "$live_mode" \
                    "$freq_before" "$freq_after" "$thermal_before" "$thermal_after" \
                    "$thermal_detail_before" "$thermal_detail_after" "$reject" | tail -n +2 >> "$out_csv"
            fi
            rm -f "$tmp"
            sleep "$COOLDOWN_SEC"
        done < <(combo_order "$block")
    done

    echo "wrote: $out_csv"
    echo "metadata: $OUT/metadata/metadata.txt"
}

main "$@"
