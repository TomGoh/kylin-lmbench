#!/bin/sh
# Exp Z: a chase whose cost is dominated by address translation.
#
# frames2 mode tlb<L> moves to another page on every hop and touches only L
# cache lines per page, so the data stay in the L1/L2 caches while the number
# of pages decides whether a hop needs a page walk:
#
#   tlb4  over  4 MB (1024 pages x 4 lines = 4096 lines): no page walks
#   tlb2  over  8 MB (2048 pages x 2 lines = 4096 lines): a walk on almost every hop
#   tlb1  over 16 MB (4096 pages x 1 line  = 4096 lines): a walk on every hop
#   tlb1  over  8, 32 and 64 MB (2048, 8192, 16384 lines)
#
# Per GiB slot and page class (clear / shared with the running VM), as in run11.
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 25 minutes.
#
#   sudo sh run17-translation-only.sh [pid of the VMM]
cd "$(dirname "$0")" || exit 1
PID=${1:-$(pgrep -x pvm | head -1)}
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run17 start $(date -Is) uid=$(id -u) vmm_pid=$PID $(st)" >> meta.log
[ -n "$PID" ] && python3 vm-frames.py "$PID" guest-regions-z.txt > vm-frames-z.txt 2>&1
: > expZ.log
rep=0
for seed in 51 53 57; do
  for cfg in "4 tlb4" "8 tlb2" "16 tlb1" "8 tlb1" "32 tlb1" "64 tlb1"; do
    set -- $cfg
    rep=$((rep + 1))
    echo "## rep=$rep size_mb=$1 pick=even mode=$2 seed=$seed $(date -Is) $(st)" >> expZ.log
    taskset -c 0 ./frames2 $1 3072 $E $seed even guest-regions-z.txt $2 >> expZ.log 2>&1
  done
done
echo "# run17 done $(date -Is) $(st)" >> meta.log
