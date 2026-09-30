#!/bin/sh
# Exp V: does it cost more to access host pages that share a 2 MiB region with
# the memory of a running protected VM?  Root (pagemap PFNs of this process and
# of the VMM), cpu0.  Changes no system setting; reads the VMM's page map only.
# About 8 minutes.  Expects ./frames2 and vm-frames.py next to this script.
#
#   sudo sh run11-vm-shared.sh [pid of the VMM]      # default: the process named "pvm"
#
# Pages given to a protected VM are removed from the host stage-2 map one 4 KiB
# page at a time; the host pages left in the same 2 MiB region are then mapped
# with 4 KiB stage-2 leaves instead of a 2 MiB or 1 GiB block.
cd "$(dirname "$0")" || exit 1
PID=${1:-$(pgrep -x pvm | head -1)}
[ -n "$PID" ] || { echo "no VMM process found" >&2; exit 1; }
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run11 start $(date -Is) uid=$(id -u) vmm_pid=$PID $(st)" >> meta.log
{
  echo "# $(date -Is) VMM: $(ps -o pid=,lstart=,args= -p "$PID" | cut -c1-200)"
  python3 vm-frames.py "$PID" guest-regions.txt
} > vm-frames-n80.txt 2>&1
: > expV.log
for rep in 1 2 3; do
  echo "## rep=$rep size_mb=32 pick=even $(date -Is) $(st)" >> expV.log
  taskset -c 0 ./frames2 32 3072 $E $((rep * 19)) even guest-regions.txt >> expV.log 2>&1
done
echo "## rep=4 size_mb=32 pick=low $(date -Is) $(st)" >> expV.log
taskset -c 0 ./frames2 32 3072 $E 23 low guest-regions.txt >> expV.log 2>&1
echo "## rep=5 size_mb=16 pick=even $(date -Is) $(st)" >> expV.log
taskset -c 0 ./frames2 16 3072 $E 29 even guest-regions.txt >> expV.log 2>&1
echo "# run11 done $(date -Is) $(st)" >> meta.log
