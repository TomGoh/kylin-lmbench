#!/bin/bash
# thp-leg.sh <protected|nvhe> : run the full THP-mitigation suite (E1/E2/E3) for one boot/mode.
# Identical procedure across modes so protected-vs-nvhe is a fair A/B. Only the boot mode differs.
set -u
MODE="${1:?usage: thp-leg.sh <protected|nvhe>}"
cd ~/kylin-lmbench
RD="experiments/perf-reinvestigation/results/kaitian-thp-20260626/$MODE"
mkdir -p "$RD"
MM=experiments/munmap-tlbi
LP=bin/lat_mmap_precise
THPSYS=/sys/kernel/mm/transparent_hugepage/enabled

# --- environment control (re-applied every boot; THP/ASLR/freq reset on reboot) ---
sudo DISABLE_THP=0 ./prepare-host.sh >/dev/null 2>&1
sudo ./quiet-host.sh quiet >/dev/null 2>&1
echo always | sudo tee "$THPSYS" >/dev/null
sudo mkdir -p /mnt/thptmp
mountpoint -q /mnt/thptmp || sudo mount -t tmpfs -o huge=always,size=512M thp_e3 /mnt/thptmp

# --- metadata ---
{
  echo "mode_label=$MODE"
  echo "date=$(date -Is)"
  echo "kernel=$(uname -r)"
  echo "cmdline=$(cat /proc/cmdline)"
  echo "thp=$(cat $THPSYS)"
  echo "shmem=$(cat /sys/kernel/mm/transparent_hugepage/shmem_enabled)"
  echo "aslr=$(cat /proc/sys/kernel/randomize_va_space)"
  echo "gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
  echo "freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)"
} | tee "$RD/metadata.txt"

# --- E1: anon_base vs anon_huge (engagement gate + interleaved sweep) ---
{ for g in "64 - 6.4 16" "16 - 1.6 16" "8 - 0.8 16" "64 - 64 4"; do
    taskset -c 0 $MM/huge_check anon $g | grep -E "huge_check|AnonHugePages"; done; } > "$RD/e1-huge-check.txt"
POINTS="8:0.8:16:sparse 16:1.6:16:sparse 64:6.4:16:sparse" ROUNDS=10 ITERS=300 CORE=0 \
  OUT="$RD/e1-anon-sweep.txt" bash $MM/run-thp-sweep.sh >/dev/null 2>&1
POINTS="64:64:4:dense" ROUNDS=5 ITERS=20 CORE=0 \
  OUT="$RD/e1-anon-dense.txt" bash $MM/run-thp-sweep.sh >/dev/null 2>&1

# --- E2: ext4 file-backed, THP always vs never (interleaved per round) ---
EF=/tmp/thp-e2-backing.bin
dd if=/dev/zero of="$EF" bs=1M count=64 status=none
: > "$RD/e2-file-thp.txt"
for r in $(seq 1 8); do for thp in always never; do
  echo "$thp" | sudo tee "$THPSYS" >/dev/null
  echo "thp=$thp r=$r op_sweep_sparse: $(taskset -c 0 $MM/op_sweep munmap file 64 200 "$EF" 6.4 16)" >> "$RD/e2-file-thp.txt"
done; done
for thp in always never; do
  echo "$thp" | sudo tee "$THPSYS" >/dev/null
  for r in 1 2 3; do echo "thp=$thp r=$r lat_mmap_precise: $(taskset -c 0 $LP 64 50 "$EF")" >> "$RD/e2-file-thp.txt"; done
done
echo always | sudo tee "$THPSYS" >/dev/null

# --- E3: tmpfs/shmem shared mapping (huge=always) ---
TF=/mnt/thptmp/backing
dd if=/dev/zero of="$TF" bs=1M count=64 status=none
{ taskset -c 0 $MM/huge_check shmem 64 /mnt/thptmp/hc 6.4 16 | grep -E "huge_check|ShmemPmdMapped"
  taskset -c 0 $MM/huge_check shmem 64 /mnt/thptmp/hc 64 4   | grep -E "huge_check|ShmemPmdMapped"; } > "$RD/e3-huge-check.txt"
rm -f /mnt/thptmp/hc
: > "$RD/e3-tmpfs.txt"
for r in $(seq 1 8); do echo "tmpfs r=$r op_sweep_sparse: $(taskset -c 0 $MM/op_sweep munmap file 64 200 "$TF" 6.4 16)" >> "$RD/e3-tmpfs.txt"; done
for r in 1 2 3; do echo "tmpfs r=$r lat_mmap_precise: $(taskset -c 0 $LP 64 50 "$TF")" >> "$RD/e3-tmpfs.txt"; done

echo "DONE $MODE -> $RD"
