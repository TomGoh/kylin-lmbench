#!/bin/bash
# Generalized TLBI-threshold sweep: does the pKVM per-page TLBI penalty hit
# madvise(DONTNEED) and mprotect too, or only munmap?
#
# Same method as run-sweep.sh: dense-touch the first N MB (flush range ≈ N MB),
# sweep N across the kernel's 2MB full-flush gate (MAX_DVM_OPS=512×4K), time ONLY
# the op. Run once per boot mode (kvm-arm.mode=protected and =nvhe), then diff the
# same row: gap = protected − nvhe.
#   <2MB per-page TLBI region: gap ∝ range (∝ TLBI count)
#   ≥2MB integer-flush region: gap collapses to ~0 at 2MB
# If dontneed/mprotect behave like munmap, the penalty is a generic host-stage-2 tax.
#
# Usage (on board, boot once protected then once nvhe):
#   ./run-op-sweep.sh
# Override: CORE SIZE ITERS FILE RANGES OPS
set -eu

CORE=${CORE:-0}
SIZE=${SIZE:-64}
ITERS=${ITERS:-100}
FILE=${FILE:-/tmp/op-sweep-backing.bin}
RANGES=${RANGES:-"0.25 0.5 1 1.9 2 4 8 32 64"}
OPS=${OPS:-"munmap dontneed mprotect"}
DIR=$(cd "$(dirname "$0")" && pwd)

make -C "$DIR" op_sweep >/dev/null
dd if=/dev/zero of="$FILE" bs=1M count="$SIZE" conv=fsync status=none

for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance | sudo tee "$g" >/dev/null 2>&1 || true
done

mode=$(grep -o 'kvm-arm.mode=[a-z]*' /proc/cmdline | cut -d= -f2)
echo "== op-sweep  mode=${mode:-default}  size=${SIZE}MB iters=$ITERS core=$CORE  (dense 4K touch) =="
for OP in $OPS; do
    echo "--- op=$OP ---"
    for TM in $RANGES; do
        taskset -c "$CORE" "$DIR/op_sweep" "$OP" file "$SIZE" "$ITERS" "$FILE" "$TM" 4
    done
done

echo "--- sparse reference (lat_mmap mode: touch 6.4MB, stride 16K) ---"
for OP in $OPS; do
    taskset -c "$CORE" "$DIR/op_sweep" "$OP" file "$SIZE" "$ITERS" "$FILE" 6.4 16
done

rm -f "$FILE"
