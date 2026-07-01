#!/usr/bin/env bash
# Host-side runner for the Pixel port of the N80/N90/Kaitian mmap teardown suite.
#
# This script does not switch KVM mode. Run it once with the phone in protected
# mode and once in nvhe mode. It assumes adb root is already active.
set -euo pipefail

SERIAL="${SERIAL:-47091FDAS009VF}"
ADB_BIN="${ADB_BIN:-adb}"
REMOTE_DIR="${REMOTE_DIR:-/data/local/tmp/pixel-ported-suite}"
OUT="${OUT:-experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-$(date +%Y%m%d)/raw/ported}"
CPU="${CPU:-4}"
CPU_MASK="${CPU_MASK:-}"
SIZE_MB="${SIZE_MB:-64}"
ITERS="${ITERS:-200}"
BACKING_ITERS="${BACKING_ITERS:-120}"
BENCH_ITERS="${BENCH_ITERS:-60}"
SPLIT_ITERS="${SPLIT_ITERS:-200}"
LAT_ITERS="${LAT_ITERS:-200}"
RANGES="${RANGES:-0.25 0.5 1 1.5 1.9 2 2.1 4 8 16 64}"
OPS="${OPS:-munmap dontneed mprotect}"
WAIT_THERMAL_MAX_MC="${WAIT_THERMAL_MAX_MC:-39000}"
WAIT_THERMAL_POLL_SEC="${WAIT_THERMAL_POLL_SEC:-5}"

LOCAL_MUNMAP_DIR="${LOCAL_MUNMAP_DIR:-experiments/munmap-tlbi}"
LOCAL_SPLIT_BIN="${LOCAL_SPLIT_BIN:-experiments/mmap-split/mmap_split_bench.android}"
LOCAL_LAT_BIN="${LOCAL_LAT_BIN:-src/lat_mmap_precise.android}"

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
    for bin in \
        "$LOCAL_MUNMAP_DIR/op_sweep.android" \
        "$LOCAL_MUNMAP_DIR/munmap_only.android" \
        "$LOCAL_MUNMAP_DIR/munmap_bench.android" \
        "$LOCAL_MUNMAP_DIR/huge_check.android" \
        "$LOCAL_SPLIT_BIN" \
        "$LOCAL_LAT_BIN"
    do
        [ -x "$bin" ] || die "missing executable Android binary: $bin"
    done
}

collect_metadata() {
    local mode="$1"
    mkdir -p "$OUT/metadata"
    {
        echo "date=$(date -Is)"
        echo "serial=$SERIAL"
        echo "mode=$mode"
        echo "out=$OUT"
        echo "cpu=$CPU"
        echo "cpu_mask=$(cpu_mask)"
        echo "size_mb=$SIZE_MB"
        echo "iters=$ITERS"
        echo "backing_iters=$BACKING_ITERS"
        echo "bench_iters=$BENCH_ITERS"
        echo "split_iters=$SPLIT_ITERS"
        echo "lat_iters=$LAT_ITERS"
        echo "ranges=$RANGES"
        echo "ops=$OPS"
        echo "wait_thermal_max_mc=$WAIT_THERMAL_MAX_MC"
        echo "wait_thermal_poll_sec=$WAIT_THERMAL_POLL_SEC"
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
        sha256sum \
            "$LOCAL_MUNMAP_DIR/op_sweep.android" \
            "$LOCAL_MUNMAP_DIR/munmap_only.android" \
            "$LOCAL_MUNMAP_DIR/munmap_bench.android" \
            "$LOCAL_MUNMAP_DIR/huge_check.android" \
            "$LOCAL_SPLIT_BIN" \
            "$LOCAL_LAT_BIN"
    } > "$OUT/metadata/${mode}.txt"
}

push_bins() {
    adb_shell "mkdir -p '$REMOTE_DIR'"
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_MUNMAP_DIR/op_sweep.android" "$REMOTE_DIR/op_sweep" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_MUNMAP_DIR/munmap_only.android" "$REMOTE_DIR/munmap_only" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_MUNMAP_DIR/munmap_bench.android" "$REMOTE_DIR/munmap_bench" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_MUNMAP_DIR/huge_check.android" "$REMOTE_DIR/huge_check" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_SPLIT_BIN" "$REMOTE_DIR/mmap_split_bench" >/dev/null
    "$ADB_BIN" -s "$SERIAL" push "$LOCAL_LAT_BIN" "$REMOTE_DIR/lat_mmap_precise" >/dev/null
    adb_shell "chmod 755 '$REMOTE_DIR/'*"
}

prepare_backing_files() {
    adb_shell "dd if=/dev/zero of='$REMOTE_DIR/mb.bin' bs=1M count='$SIZE_MB' >/dev/null 2>&1; sync"
    adb_shell "rm -f /dev/pixel-ported-suite-tmpfs.bin; dd if=/dev/zero of=/dev/pixel-ported-suite-tmpfs.bin bs=1M count='$SIZE_MB' >/dev/null 2>&1 || true"
}

run_one() {
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
    {
        echo "### rc=$rc freq_after_khz=$freq_after thermal_after_mc=$thermal_after"
    } >> "$outfile"

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$mode" "$section" "$label" "$rc" "$gate_start" "$gate_wait" "$gate_ready" \
        "$freq_before" "$freq_after" "$thermal_before" "$thermal_after" "$cmd" \
        >> "$OUT/raw/$mode/thermal_gate.tsv"

    if [ "$rc" -ne 0 ]; then
        die "remote command failed: section=$section label=$label rc=$rc"
    fi
}

run_suite() {
    local mode="$1"
    local raw="$OUT/raw/$mode"
    local file="$REMOTE_DIR/mb.bin"
    local tmpfs="/dev/pixel-ported-suite-tmpfs.bin"
    local op range bench_mode mb

    mkdir -p "$raw"
    printf 'mode\tsection\tlabel\trc\tthermal_gate_start_mc\tthermal_wait_sec\tthermal_gate_ready_mc\tfreq_before_khz\tfreq_after_khz\tthermal_before_mc\tthermal_after_mc\tcommand\n' \
        > "$raw/thermal_gate.tsv"

    run_one "$mode" "lat_mmap_precise" "file-64-sparse" "$raw/lat_mmap_precise.txt" \
        "'$REMOTE_DIR/lat_mmap_precise' '$SIZE_MB' '$LAT_ITERS' '$file'"

    for bench_mode in mmap_unmap write_touch_cold munmap_after_no_touch munmap_after_write_touch mmap_write_touch_unmap; do
        run_one "$mode" "mmap_split" "$bench_mode" "$raw/mmap_split.csv" \
            "'$REMOTE_DIR/mmap_split_bench' '$bench_mode' '$SIZE_MB' '$SPLIT_ITERS' '$file' 10 16 1"
    done

    for range in $RANGES; do
        run_one "$mode" "munmap_threshold" "file-${range}MB-dense" "$raw/munmap_threshold.txt" \
            "'$REMOTE_DIR/munmap_only' file '$SIZE_MB' '$ITERS' '$file' '$range' 4"
    done
    run_one "$mode" "munmap_threshold" "file-6.4MB-sparse" "$raw/munmap_threshold.txt" \
        "'$REMOTE_DIR/munmap_only' file '$SIZE_MB' '$ITERS' '$file' 6.4 16"

    for op in $OPS; do
        for range in $RANGES; do
            run_one "$mode" "op_sweep" "${op}-file-${range}MB-dense" "$raw/op_sweep.txt" \
                "'$REMOTE_DIR/op_sweep' '$op' file '$SIZE_MB' '$ITERS' '$file' '$range' 4"
        done
        run_one "$mode" "op_sweep" "${op}-file-6.4MB-sparse" "$raw/op_sweep.txt" \
            "'$REMOTE_DIR/op_sweep' '$op' file '$SIZE_MB' '$ITERS' '$file' 6.4 16"
    done

    for bench_mode in file anon_base anon_huge; do
        for mb in 8 16 64; do
            run_one "$mode" "backing" "${bench_mode}-${mb}MB-sparse" "$raw/backing_munmap_only.txt" \
                "'$REMOTE_DIR/munmap_only' '$bench_mode' '$mb' '$BACKING_ITERS' '$file' 6.4 16"
        done
        run_one "$mode" "backing" "${bench_mode}-64MB-full" "$raw/backing_munmap_only.txt" \
            "'$REMOTE_DIR/munmap_only' '$bench_mode' 64 '$BACKING_ITERS' '$file' 64 4"
    done

    for bench_mode in file anon_base anon_huge; do
        run_one "$mode" "munmap_bench" "${bench_mode}-64MB-full" "$raw/munmap_bench.txt" \
            "'$REMOTE_DIR/munmap_bench' '$bench_mode' 64 '$BENCH_ITERS' '$file'"
    done

    for mb in 8 16 64; do
        run_one "$mode" "huge_check" "anon-${mb}MB-sparse" "$raw/huge_check.txt" \
            "'$REMOTE_DIR/huge_check' anon '$mb' - 6.4 16"
    done
    run_one "$mode" "huge_check" "anon-64MB-full" "$raw/huge_check.txt" \
        "'$REMOTE_DIR/huge_check' anon 64 - 64 4"
    run_one "$mode" "huge_check" "tmpfs-64MB-sparse" "$raw/huge_check.txt" \
        "'$REMOTE_DIR/huge_check' shmem 64 '$tmpfs' 6.4 16"
    run_one "$mode" "huge_check" "tmpfs-64MB-full" "$raw/huge_check.txt" \
        "'$REMOTE_DIR/huge_check' shmem 64 '$tmpfs' 64 4"
    run_one "$mode" "tmpfs_op_sweep" "munmap-tmpfs-6.4MB-sparse" "$raw/tmpfs_op_sweep.txt" \
        "'$REMOTE_DIR/op_sweep' munmap file 64 '$ITERS' '$tmpfs' 6.4 16"
    run_one "$mode" "tmpfs_op_sweep" "munmap-tmpfs-64MB-full" "$raw/tmpfs_op_sweep.txt" \
        "'$REMOTE_DIR/op_sweep' munmap file 64 '$ITERS' '$tmpfs' 64 4"
}

main() {
    require_bins
    [ "$("$ADB_BIN" -s "$SERIAL" get-state 2>/dev/null | tr -d '\r')" = "device" ] || die "adb does not see $SERIAL"
    [ "$(adb_shell 'id -u' | tr -d '\r')" = "0" ] || die "adb is not root"

    local mode
    mode="$(mode_label)"
    [ -n "$mode" ] || mode="unknown"

    mkdir -p "$OUT/raw/$mode"
    collect_metadata "$mode"
    push_bins
    prepare_backing_files
    run_suite "$mode"
    echo "DONE pixel ported suite: mode=$mode out=$OUT/raw/$mode"
}

main "$@"
