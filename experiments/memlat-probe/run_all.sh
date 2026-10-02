#!/bin/sh
# Runs as root (pagemap PFNs need CAP_SYS_ADMIN). Pinned to cpu0 (1.9 GHz, FTC862). Output: /tmp/kx-memprobe/*.log
cd "$(dirname "$0")" || exit 1
P="taskset -c 0 ./probe"
E1=11,2d,5,2a,17,13
E2=11,2d,19,2b,2f,24
{
echo "# $(date -Is) kernel=$(uname -r) cmdline_mode=$(tr ' ' '\n' </proc/cmdline | grep kvm-arm.mode) thp_sys=$(cat /sys/kernel/mm/transparent_hugepage/enabled) cpu0_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)"
} > meta.log
# A: random page-order chase (lmbench -t, stride 16), 4K pages, size sweep, 3 seeds x 2 event sets
: > expA.log
for seed in 101 202 303; do
  for sz in 0.5 1 1.5 2 3 4 6 8 12 16 24 32 48 64; do
    $P rand $sz 16 64 0 $E1 $seed >> expA.log 2>&1
    $P rand $sz 16 64 0 $E2 $seed >> expA.log 2>&1
  done
done
# C: random 64MB and 8MB with 2MB THP backing
: > expC.log
for seed in 101 202 303; do
  for sz in 8 64; do
    $P rand $sz 16 64 1 $E1 $seed >> expC.log 2>&1
  done
done
# D: sequential 64MB, stride sweep (TLB refills per access should be stride/4096)
: > expD.log
for rep in 1 2 3; do
  for st in 64 128 256 512 1024; do
    $P seq 64 $st 64 0 $E1 >> expD.log 2>&1
  done
done
# B: sequential stride 256 around the L3 boundary, fresh process per point like lmbench, 30 laps
: > expB.log
EB=11,2a,19,17,2d,2b
for lap in $(seq 1 30); do
  for sz in 4 6 8 12 16 64; do
    $P seq $sz 256 64 0 $EB >> expB.log 2>&1
  done
done
echo "# done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
