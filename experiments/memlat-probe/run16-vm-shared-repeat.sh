#!/bin/sh
# Exp V3: repetitions of the shared-versus-clear size sweep (Exp V2), which had
# one set of shared pages and two passes per size from 6 MB upward.  Three more
# page sets per size (other seeds, a new pool each time), and the physically
# contiguous pick at three sizes.
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 30 minutes.
#
#   sudo sh run16-vm-shared-repeat.sh [pid of the VMM]
cd "$(dirname "$0")" || exit 1
PID=${1:-$(pgrep -x pvm | head -1)}
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run16 start $(date -Is) uid=$(id -u) vmm_pid=$PID $(st)" >> meta.log
[ -n "$PID" ] && python3 vm-frames.py "$PID" guest-regions-v3.txt > vm-frames-v3.txt 2>&1
: > expV3.log
rep=0
for seed in 41 43 47; do
  for sz in 6 8 12 16 24 32 48 64; do
    rep=$((rep + 1))
    echo "## rep=$rep size_mb=$sz pick=even seed=$seed $(date -Is) $(st)" >> expV3.log
    taskset -c 0 ./frames2 $sz 3072 $E $seed even guest-regions-v3.txt >> expV3.log 2>&1
  done
done
for sz in 16 32 64; do
  rep=$((rep + 1))
  echo "## rep=$rep size_mb=$sz pick=low seed=41 $(date -Is) $(st)" >> expV3.log
  taskset -c 0 ./frames2 $sz 3072 $E 41 low guest-regions-v3.txt >> expV3.log 2>&1
done
echo "# run16 done $(date -Is) $(st)" >> meta.log
