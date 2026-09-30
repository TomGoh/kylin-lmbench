#!/bin/sh
# Exp X: does the form of the timed loop matter?
#
# lmbench times 100 load instructions in a row (the HUNDRED macro in
# benchmark_loads); probe3 and frames2 time one load instruction in a loop.
# In the same platform state lmbench's own lat_mem_rd reads 8% to 19% slower
# than probe3 for the sequential pattern (Exp H against Exp R), and 2% to 5%
# slower for the random pattern.  With CHASE_UNROLL=1 probe3 and frames2 time
# lmbench's loop body instead.
#
#   expX1.log  probe3, fresh process per point, chain rewritten before every
#              interval: sequential stride 256 at 24 KiB..64 MB and the random
#              pattern at 8 and 64 MB, loop form against unrolled form
#   expX2.log  frames2, sequential stride 256 over the same pages in sorted and
#              in shuffled virtual order (as Exp W), unrolled form; at 8 MB also
#              the loop form, taken in the same session
#   expX3.log  lmbench's own lat_mem_rd (stride 256, 4 KiB pages), 3 sweeps,
#              as the reference taken in the same session
#
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 30 minutes.
# Expects ./probe3 ./frames2 ./lat_mem_rd ./nothp ./vm-frames.py; $1 = pid of
# the VMM process of the running VM (frames2 needs the list of 2 MiB regions
# that hold VM pages; it is read again here because the VM may have touched
# more memory since run11).
cd "$(dirname "$0")" || exit 1
VMM=$1
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
echo "# run14 start $(date -Is) uid=$(id -u) $(st) thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled) cpu0_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)" >> meta.log

# X3 first half: lmbench's own program
: > expX3.log
lm() { echo "## sweep=$1 start=$(date +%s.%N | cut -c1-14) $(st) args=-P 1 64 256" >> expX3.log
       taskset -c 0 ./nothp ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> expX3.log; }
lm 1

# X1: probe3, loop form against unrolled form
: > expX1.log
for lap in 1 2 3 4 5 6 7 8; do
  for sz in 0.0234375 0.5 1 2 4 6 8 12 16 64; do
    for un in 0 1; do
      echo "X1 lap=$lap $(CHASE_UNROLL=$un taskset -c 0 ./probe3 seq $sz 256 64 $E 1 2>&1)" >> expX1.log
    done
  done
done
for seed in 7 14 21; do
  for sz in 8 64; do
    for un in 0 1; do
      echo "X1 lap=$seed $(CHASE_UNROLL=$un taskset -c 0 ./probe3 rand $sz 16 64 $E 1 $seed 2>&1)" >> expX1.log
    done
  done
done
echo "# run14 X1 done $(date -Is) $(st)" >> meta.log
lm 2

# X2: frames2, sorted against shuffled, by page class
if [ -n "$VMM" ] && [ -r "/proc/$VMM/maps" ]; then
  python3 ./vm-frames.py "$VMM" guest-regions-x.txt > vm-frames-x.txt 2>&1
  REG=guest-regions-x.txt
else
  REG=-
fi
: > expX2.log
rep=0
for sz in 8 16 64; do
  for pick in low even; do
    for order in sorted shuffled; do
      for un in 1 0; do
        [ $un = 0 ] && [ $sz != 8 ] && continue
        rep=$((rep + 1))
        echo "## rep=$rep size_mb=$sz pick=$pick order=$order mode=seq256 unroll=$un $(date -Is) $(st)" >> expX2.log
        CHASE_UNROLL=$un taskset -c 0 ./frames2 $sz 3072 $E 37 $pick $REG seq256 $order >> expX2.log 2>&1
      done
    done
  done
done
echo "# run14 X2 done $(date -Is) $(st)" >> meta.log
lm 3
echo "# run14 done $(date -Is) $(st)" >> meta.log
