#!/bin/bash
set -u
B=~/perf-reinvestigation/benches; OUT=~/perf-reinvestigation/results/corescaling
PERF=/usr/local/bin/perf; F=~/perf-reinvestigation/mb.bin; ITERS=1000   # user-owned dir, not world-writable /tmp (symlink/TOCTOU)
mkdir -p "$OUT"; truncate -s 160M "$F"
maxf=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)
set_online() {  # keep cpu0 + listed cpus online; offline rest; re-lock freq (onlined cores reset governor!)
  local keep=" 0 $* "
  for c in 1 2 3 4 5 6 7; do
    if [[ "$keep" == *" $c "* ]]; then echo 1 | sudo tee /sys/devices/system/cpu/cpu$c/online >/dev/null
    else echo 0 | sudo tee /sys/devices/system/cpu/cpu$c/online >/dev/null; fi
  done
  for d in /sys/devices/system/cpu/cpu*/cpufreq; do
    echo performance | sudo tee $d/scaling_governor >/dev/null 2>&1
    echo $maxf | sudo tee $d/scaling_max_freq >/dev/null 2>&1; echo $maxf | sudo tee $d/scaling_min_freq >/dev/null 2>&1
  done
}
run() {
  echo "### $1 : online=$(cat /sys/devices/system/cpu/online) freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) ###"
  taskset -c 0 "$B/munmap_only" file 64 "$ITERS" "$F" 6.4 16
  taskset -c 0 "$PERF" stat -e cycles,r0024,instructions "$B/munmap_only" file 64 "$ITERS" "$F" 6.4 16 2>&1 | grep -E 'cycles|r0024|instructions|elapsed'
}
{
echo "## Core-scaling (protected): LOCAL vs cross-core broadcast?  metric=MEAN (min lies, corescaling-followup §9)"
set_online 1 2 3 4 5 6 7; run "n8_all"
set_online 1;             run "n2_intra_0_1"
set_online 4;             run "n2_cross_0_4"
set_online;               run "n1_solo_0"
set_online 1 2 3 4 5 6 7; echo "restored online=$(cat /sys/devices/system/cpu/online)"
} | tee "$OUT/corescaling.txt"
