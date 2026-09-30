#!/bin/sh
# Exp V2: the shared-versus-clear comparison of run11 at working-set sizes from
# 2 MB to 64 MB.  Root (pagemap PFNs), cpu0.  Changes no system setting.
# About 12 minutes.  Expects ./frames2 and a fresh guest-regions.txt (run11
# writes it; this script rewrites it first if a VMM pid is given or found).
#
#   sudo sh run12-vm-shared-sizes.sh [pid of the VMM]
#
# If the extra time of the shared class is a stage-2 cost paid on page walks,
# it should be absent where the random chase needs no walks (2 MB) and grow
# with the walk rate and with the number of stage-2 leaf descriptors in use.
cd "$(dirname "$0")" || exit 1
PID=${1:-$(pgrep -x pvm | head -1)}
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run12 start $(date -Is) uid=$(id -u) vmm_pid=$PID $(st)" >> meta.log
[ -n "$PID" ] && python3 vm-frames.py "$PID" guest-regions.txt > vm-frames-n80-run12.txt 2>&1
: > expV2.log
rep=0
for sz in 2 3 4 6 8 12 16 24 32 48 64; do
  rep=$((rep + 1))
  echo "## rep=$rep size_mb=$sz pick=even $(date -Is) $(st)" >> expV2.log
  taskset -c 0 ./frames2 $sz 3072 $E 31 even guest-regions.txt >> expV2.log 2>&1
done
echo "# run12 done $(date -Is) $(st)" >> meta.log
