#!/bin/sh
# Exp N3: the translation-only chase over page sets that mix two GiB slots in
# a fixed proportion (frames2, 9th argument <slot A>:<slot B>:<percent of A>).
#
# Exp Z measured sets taken from one slot each: slots that can still be 1 GiB
# stage-2 blocks (0x22c0000000, 0x2300000000 = slot numbers 0x8b, 0x8c) cost
# about 3.6 cycles more per page walk than slots mapped with 2 MiB blocks.
# Exp N2 (probe3, pages wherever the kernel put them) gave about 7 cycles per
# unit share of pages in those two slots, over shares from 0 to 0.43.  Here
# the share is set, the rest of the set comes from one 2 MiB-block slot.
#
#   tlb1 over 8 MB (2048 pages x 1 line): a page walk on almost every hop
#     A = 0x8b, B = 0x88 and A = 0x8c, B = 0x89 at 0, 12, 25, 50, 75, 100 % of A
#     controls: two 1 GiB-candidate slots half and half, two 2 MiB slots half and half
#   tlb4 over 4 MB (1024 pages x 4 lines): no page walks, 0, 50, 100 % of A
#
# The third loop variable only changes the order of the chase: every process
# builds its pool anew and gets largely the same frames, so the three passes
# are repetitions, not three independent page sets.
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 6 minutes.
#
#   sudo sh run20-slot-mix-controlled.sh [pid of the VMM]
cd "$(dirname "$0")" || exit 1
PID=${1:-$(pgrep -x pvm | head -1)}
DF=/sys/class/devfreq/nocfreq
E=11,2d,17
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run20 start $(date -Is) uid=$(id -u) vmm_pid=$PID $(st)" >> meta.log
[ -n "$PID" ] && python3 vm-frames.py "$PID" guest-regions-n3.txt > vm-frames-n3.txt 2>&1
: > expN3.log
for seed in 61 67 71; do
  for mix in 0x8b:0x88:0 0x8b:0x88:12 0x8b:0x88:25 0x8b:0x88:50 0x8b:0x88:75 0x8b:0x88:100 \
             0x8c:0x89:0 0x8c:0x89:12 0x8c:0x89:25 0x8c:0x89:50 0x8c:0x89:75 0x8c:0x89:100 \
             0x8b:0x8c:50 0x88:0x89:50; do
    echo "## seed=$seed size_mb=8 mode=tlb1 mix=$mix $(date -Is) $(st)" >> expN3.log
    taskset -c 0 ./frames2 8 3072 $E $seed even guest-regions-n3.txt tlb1 sorted $mix >> expN3.log 2>&1
  done
  for mix in 0x8b:0x88:0 0x8b:0x88:50 0x8b:0x88:100; do
    echo "## seed=$seed size_mb=4 mode=tlb4 mix=$mix $(date -Is) $(st)" >> expN3.log
    taskset -c 0 ./frames2 4 3072 $E $seed even guest-regions-n3.txt tlb4 sorted $mix >> expN3.log 2>&1
  done
done
echo "# run20 done $(date -Is) $(st)" >> meta.log
