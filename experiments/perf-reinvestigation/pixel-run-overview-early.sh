#!/usr/bin/env bash
# Host-side runner for the early pkvm-mmap-overview experiments on Pixel:
#   - Stage 1: multi-size lat_mmap_precise and steady-state memory controls
#   - Stage 2: full 12-way mmap lifecycle split matrix
#
# This script assumes the phone is already in the desired KVM mode and adb root
# is active. It does not switch modes, reboot, or flash.
set -euo pipefail

SERIAL="${SERIAL:-47091FDAS009VF}"
ADB_BIN="${ADB_BIN:-adb}"
REMOTE_DIR="${REMOTE_DIR:-/data/local/tmp/pixel-overview-early}"
OUT="${OUT:-experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260629-overview-early}"
CPU="${CPU:-4}"
CPU_MASK="${CPU_MASK:-}"
WAIT_THERMAL_MAX_MC="${WAIT_THERMAL_MAX_MC:-39000}"
WAIT_THERMAL_POLL_SEC="${WAIT_THERMAL_POLL_SEC:-5}"

LAT_RUNS="${LAT_RUNS:-10}"
SPLIT_RUNS="${SPLIT_RUNS:-10}"
STEADY_RUNS="${STEADY_RUNS:-5}"
SIZES="${SIZES:-0.5 1 2 4 8 16 64}"
SPLIT_MODES="${SPLIT_MODES:-openclose mmap_unmap mmap_populate_unmap mmap_write_touch_unmap mmap_read_touch_unmap write_touch_cold read_touch_cold write_touch_hot read_touch_hot munmap_after_no_touch munmap_after_write_touch munmap_after_read_touch}"
BW_MEM_WHAT="${BW_MEM_WHAT:-rd wr rdwr}"

LOCAL_LAT="${LOCAL_LAT:-src/lat_mmap_precise.android}"
LOCAL_SPLIT="${LOCAL_SPLIT:-experiments/mmap-split/mmap_split_bench.android}"
LOCAL_LAT_MEM="${LOCAL_LAT_MEM:-bin/android-aarch64/lat_mem_rd}"
LOCAL_BW_MEM="${LOCAL_BW_MEM:-bin/android-aarch64/bw_mem}"
LOCAL_BW_MMAP="${LOCAL_BW_MMAP:-bin/android-aarch64/bw_mmap_rd}"

adb_shell() {
    "$ADB_BIN" -s "$SERIAL" shell "$@" < /dev/null
}

die() {
    echo "error: $*" >&2
    exit 1
}

is_uint() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

cpu_mask() {
    if [ -n "$CPU_MASK" ]; then
        echo "$CPU_MASK"
        return
    fi
    printf "%x\n" "$((1 << CPU))"
}

ceil_mb() {
    awk -v v="$1" 'BEGIN{n=int(v); if (v > n) n++; if (n < 1) n=1; print n}'
}

iters_for_size() {
    case "$1" in
        0.5) echo 10000 ;;
        1) echo 8000 ;;
        2) echo 5000 ;;
        4) echo 3000 ;;
        8) echo 2000 ;;
        16) echo 1000 ;;
        64) echo 300 ;;
        *) die "no iteration policy for size $1" ;;
    esac
}

size_file_name() {
    echo "$REMOTE_DIR/lmb_${1}MB.bin"
}

mode_label() {
    adb_shell 'cat /proc/cmdline 2>/dev/null | tr " " "\n" | grep "^kvm-arm.mode=" | tail -1 | cut -d= -f2' \
        | tr -d '\r'
}

read_freq() {
    adb_shell "cat /sys/devices/system/cpu/cpu${CPU}/cpufreq/scaling_cur_freq 2>/dev/null || true" \
        | tr -d '\r'
}

read_thermal_max() {
    adb_shell 'for f in /sys/class/thermal/thermal_zone*/temp; do cat "$f" 2>/dev/null; done | sort -n | tail -1' \
        | tr -d '\r'
}

wait_for_thermal_gate() {
    local start current waited
    start="$(read_thermal_max)"
    current="$start"
    waited=0
    if [ -z "$WAIT_THERMAL_MAX_MC" ] || ! is_uint "$WAIT_THERMAL_MAX_MC"; then
        echo "${start},${waited},${current}"
        return
    fi
    while is_uint "$current" && [ "$current" -ge "$WAIT_THERMAL_MAX_MC" ]; do
        sleep "$WAIT_THERMAL_POLL_SEC"
        waited=$((waited + WAIT_THERMAL_POLL_SEC))
        current="$(read_thermal_max)"
    done
    echo "${start},${waited},${current}"
}

require_bins() {
    local bin
    for bin in "$LOCAL_LAT" "$LOCAL_SPLIT" "$LOCAL_LAT_MEM" "$LOCAL_BW_MEM" "$LOCAL_BW_MMAP"; do
        [ -x "$bin" ] || die "missing executable Android binary: $bin"
    done
}

push_bins() {
    adb_shell "mkdir -p '$REMOTE_DIR'"
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_LAT" "$REMOTE_DIR/lat_mmap_precise" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_SPLIT" "$REMOTE_DIR/mmap_split_bench" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_LAT_MEM" "$REMOTE_DIR/lat_mem_rd" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_BW_MEM" "$REMOTE_DIR/bw_mem" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_BW_MMAP" "$REMOTE_DIR/bw_mmap_rd" >/dev/null
    adb_shell "chmod 755 '$REMOTE_DIR/'*"
}

prepare_backing_files() {
    local sz count file
    for sz in $SIZES; do
        count="$(ceil_mb "$sz")"
        file="$(size_file_name "$sz")"
        adb_shell "dd if=/dev/zero of='$file' bs=1M count='$count' >/dev/null 2>&1; sync"
    done
    file="$(size_file_name 64)"
    adb_shell "[ -s '$file' ] || { dd if=/dev/zero of='$file' bs=1M count=64 >/dev/null 2>&1; sync; }"
}

collect_metadata() {
    local live_mode="$1"
    mkdir -p "$OUT/metadata"
    {
        echo "date=$(date -Is)"
        echo "serial=$SERIAL"
        echo "mode=$live_mode"
        echo "out=$OUT"
        echo "cpu=$CPU"
        echo "cpu_mask=$(cpu_mask)"
        echo "wait_thermal_max_mc=$WAIT_THERMAL_MAX_MC"
        echo "wait_thermal_poll_sec=$WAIT_THERMAL_POLL_SEC"
        echo "lat_runs=$LAT_RUNS"
        echo "split_runs=$SPLIT_RUNS"
        echo "steady_runs=$STEADY_RUNS"
        echo "sizes=$SIZES"
        echo "split_modes=$SPLIT_MODES"
        echo "bw_mem_what=$BW_MEM_WHAT"
        echo "--- adb devices ---"
        "$ADB_BIN" devices -l
        echo "--- uid ---"
        adb_shell 'id -u'
        echo "--- props ---"
        adb_shell 'getprop ro.product.device; getprop ro.product.model; getprop ro.boot.slot_suffix; getprop ro.boot.hypervisor.version; getprop ro.boot.flash.locked'
        echo "--- cmdline ---"
        adb_shell 'cat /proc/cmdline 2>/dev/null || true'
        echo "--- uname ---"
        adb_shell 'uname -a'
        echo "--- cpu freq ---"
        adb_shell 'for c in /sys/devices/system/cpu/cpu[0-9]*; do b=$(basename "$c"); printf "%s " "$b"; cat "$c/cpufreq/scaling_cur_freq" 2>/dev/null || true; done'
        echo "--- thermal ---"
        adb_shell 'for z in /sys/class/thermal/thermal_zone*; do t=$(cat "$z/type" 2>/dev/null || echo unknown); v=$(cat "$z/temp" 2>/dev/null || echo NA); printf "%s=%s|" "$t" "$v"; done; echo'
        echo "--- local binary sha256 ---"
        sha256sum "$LOCAL_LAT" "$LOCAL_SPLIT" "$LOCAL_LAT_MEM" "$LOCAL_BW_MEM" "$LOCAL_BW_MMAP"
    } > "$OUT/metadata/${live_mode}.txt"
}

run_remote() {
    local mode="$1"
    local section="$2"
    local label="$3"
    local outfile="$4"
    local cmd="$5"
    local gate_start gate_wait gate_ready freq_before freq_after thermal_before thermal_after rc
    mkdir -p "$(dirname "$outfile")"
    IFS=, read -r gate_start gate_wait gate_ready < <(wait_for_thermal_gate)
    freq_before="$(read_freq)"
    thermal_before="$(read_thermal_max)"
    {
        echo
        echo "### section=$section label=$label"
        echo "### command=$cmd"
        echo "### gate_start_mc=$gate_start gate_wait_sec=$gate_wait gate_ready_mc=$gate_ready freq_before_khz=$freq_before thermal_before_mc=$thermal_before"
    } >> "$outfile"
    set +e
    adb_shell "taskset $(cpu_mask) $cmd" >> "$outfile" 2>&1
    rc=$?
    set -e
    freq_after="$(read_freq)"
    thermal_after="$(read_thermal_max)"
    echo "### rc=$rc freq_after_khz=$freq_after thermal_after_mc=$thermal_after" >> "$outfile"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$mode" "$section" "$label" "$rc" "$gate_start" "$gate_wait" "$gate_ready" \
        "$freq_before" "$freq_after" "$thermal_before" "$thermal_after" "$cmd" \
        >> "$OUT/raw/$mode/thermal_gate.tsv"
    if [ "$rc" -ne 0 ]; then
        die "remote command failed: section=$section label=$label rc=$rc"
    fi
}

run_lat_mmap_precise() {
    local mode="$1" raw="$OUT/raw/$mode" sz iters run file
    for sz in $SIZES; do
        iters="$(iters_for_size "$sz")"
        file="$(size_file_name "$sz")"
        for run in $(seq 1 "$LAT_RUNS"); do
            run_remote "$mode" "lat_mmap_precise" "size-${sz}MB-run-${run}" "$raw/lat_mmap_precise.txt" \
                "'$REMOTE_DIR/lat_mmap_precise' '$sz' '$iters' '$file'"
        done
    done
}

run_mmap_split() {
    local mode="$1" raw="$OUT/raw/$mode" sz iters bench_mode run file out line rc
    local csv="$raw/mmap_split_full.csv"
    echo "env,run,bench_mode,size_mb,iters,warmups,timed,touch_divisor,stride_kb,touch_bytes,touches_per_iter,total_ns,per_iter_ns,per_iter_us,per_touch_ns,sink" > "$csv"
    for sz in $SIZES; do
        iters="$(iters_for_size "$sz")"
        file="$(size_file_name "$sz")"
        for bench_mode in $SPLIT_MODES; do
            for run in $(seq 1 "$SPLIT_RUNS"); do
                local gate_start gate_wait gate_ready freq_before freq_after thermal_before thermal_after
                IFS=, read -r gate_start gate_wait gate_ready < <(wait_for_thermal_gate)
                freq_before="$(read_freq)"
                thermal_before="$(read_thermal_max)"
                set +e
                out="$(adb_shell "taskset $(cpu_mask) '$REMOTE_DIR/mmap_split_bench' '$bench_mode' '$sz' '$iters' '$file' 10 16 1" 2>&1)"
                rc=$?
                set -e
                freq_after="$(read_freq)"
                thermal_after="$(read_thermal_max)"
                printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
                    "$mode" "mmap_split_full" "${bench_mode}-${sz}MB-run-${run}" "$rc" \
                    "$gate_start" "$gate_wait" "$gate_ready" "$freq_before" "$freq_after" \
                    "$thermal_before" "$thermal_after" \
                    "'$REMOTE_DIR/mmap_split_bench' '$bench_mode' '$sz' '$iters' '$file' 10 16 1" \
                    >> "$raw/thermal_gate.tsv"
                printf '\n### section=mmap_split_full label=%s-%sMB-run-%s\n%s\n### rc=%s\n' \
                    "$bench_mode" "$sz" "$run" "$out" "$rc" >> "$raw/mmap_split_full.raw.txt"
                if [ "$rc" -ne 0 ]; then
                    die "mmap_split failed: $bench_mode size=$sz run=$run rc=$rc"
                fi
                line="$(printf '%s\n' "$out" | tail -n 1 | tr -d '\r')"
                echo "$mode,$run,$line" >> "$csv"
            done
        done
    done
}

run_steady_controls() {
    local mode="$1" raw="$OUT/raw/$mode" run what file64
    file64="$(size_file_name 64)"
    for run in $(seq 1 "$STEADY_RUNS"); do
        run_remote "$mode" "lat_mem_rd" "64MB-stride128-run-${run}" "$raw/lat_mem_rd.txt" \
            "'$REMOTE_DIR/lat_mem_rd' -P 1 -W 1 -N 3 64 128"
    done
    for what in $BW_MEM_WHAT; do
        for run in $(seq 1 "$STEADY_RUNS"); do
            run_remote "$mode" "bw_mem" "${what}-64m-run-${run}" "$raw/bw_mem.txt" \
                "'$REMOTE_DIR/bw_mem' -P 1 -W 1 -N 3 64m '$what'"
        done
    done
    for run in $(seq 1 "$STEADY_RUNS"); do
        run_remote "$mode" "bw_mmap_rd" "mmap_only-64m-run-${run}" "$raw/bw_mmap_rd.txt" \
            "'$REMOTE_DIR/bw_mmap_rd' -P 1 -W 1 -N 3 64m mmap_only '$file64'"
        run_remote "$mode" "bw_mmap_rd" "open2close-64m-run-${run}" "$raw/bw_mmap_rd.txt" \
            "'$REMOTE_DIR/bw_mmap_rd' -P 1 -W 1 -N 3 64m open2close '$file64'"
    done
}

main() {
    require_bins
    [ "$("$ADB_BIN" -s "$SERIAL" get-state 2>/dev/null | tr -d '\r')" = "device" ] || die "adb does not see $SERIAL"
    [ "$(adb_shell 'id -u' | tr -d '\r')" = "0" ] || die "adb is not root"

    local mode raw
    mode="$(mode_label)"
    [ -n "$mode" ] || mode="unknown"
    raw="$OUT/raw/$mode"
    mkdir -p "$raw"
    printf 'mode\tsection\tlabel\trc\tthermal_gate_start_mc\tthermal_wait_sec\tthermal_gate_ready_mc\tfreq_before_khz\tfreq_after_khz\tthermal_before_mc\tthermal_after_mc\tcommand\n' \
        > "$raw/thermal_gate.tsv"

    collect_metadata "$mode"
    push_bins
    prepare_backing_files
    run_lat_mmap_precise "$mode"
    run_mmap_split "$mode"
    run_steady_controls "$mode"
    echo "DONE pixel overview early suite: mode=$mode out=$raw"
}

main "$@"
