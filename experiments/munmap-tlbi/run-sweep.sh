#!/bin/bash
# munmap teardown 的 TLBI 阈值扫描（C1 机制判定的决定性实验）。
#
# 连续密集触摸前 N MB（flush 范围≈N MB，由 N 干净控制），范围跨内核的
# 2MB full-flush 阈值（MAX_DVM_OPS=512×4K），只给 munmap 计时。
# 在 protected 与 nvhe 各跑一轮、对比同一行的 gap = protected − nvhe：
#   <2MB 逐页 TLBI 区：gap 随范围线性增长（∝TLBI 条数）；
#   ≥2MB 整表 flush 区：gap 在 2MB 处断崖塌到 ~0。
# 结论与解读见 docs/mmap/c1-tlbi-threshold.zh-CN.md。
#
# 用法（板上，分别以 kvm-arm.mode=protected / nvhe 启动各跑一次）：
#   ./run-sweep.sh
# 可覆盖：CORE SIZE ITERS FILE RANGES
set -eu

CORE=${CORE:-0}
SIZE=${SIZE:-64}
ITERS=${ITERS:-100}
FILE=${FILE:-/tmp/munmap-tlbi-backing.bin}
RANGES=${RANGES:-"0.25 0.5 1 1.9 2 4 8 32 64"}
DIR=$(cd "$(dirname "$0")" && pwd)

make -C "$DIR" munmap_only >/dev/null
dd if=/dev/zero of="$FILE" bs=1M count="$SIZE" conv=fsync status=none

# 锁频，减少抖动
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance | sudo tee "$g" >/dev/null 2>&1 || true
done

mode=$(grep -o 'kvm-arm.mode=[a-z]*' /proc/cmdline | cut -d= -f2)
echo "== munmap-only TLBI 阈值扫描  mode=${mode:-default}  size=${SIZE}MB iters=$ITERS core=$CORE =="
for TM in $RANGES; do
    taskset -c "$CORE" "$DIR/munmap_only" file "$SIZE" "$ITERS" "$FILE" "$TM" 4
done
echo "--- 稀疏参考（原 lat_mmap / mmap_split 模式：触 6.4MB，stride 16K）---"
taskset -c "$CORE" "$DIR/munmap_only" file "$SIZE" "$ITERS" "$FILE" 6.4 16

rm -f "$FILE"
