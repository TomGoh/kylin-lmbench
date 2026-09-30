#!/bin/sh
# Exp N5: does the mix of stage-2 page classes in probe3's own buffer account
# for what one page walk costs it?
#
# frames2 measures sets of one class at a time (2048 pages x 1 line, cycles
# per page walk after subtracting the no-walk reference): pages under 2 MiB
# stage-2 blocks about 24, pages in the two slots that can still be 1 GiB
# blocks about 28, pages in 2 MiB regions shared with the running VM (4 KiB
# stage-2 leaves) about 34.  probe3 takes whatever frames the kernel hands
# out.  Here it reports, per process, the share of its pages in the two
# 1 GiB-candidate slots (from slots=) and in VM-shared regions (shared_frac=,
# REGIONS file written by vm-frames.py at the start), so that the measured
# cost per walk can be compared with the mixture of the three class values.
#
# As run19: before each repetition a stopped process holds back
# (repetition - 1) x 192 MB so that the frames differ.  Each repetition runs
# the no-walk reference (1024 x 2) and 2048 x 1, without and with
# TLB_PREFAULT.  Root (pagemap PFNs), cpu0.  Changes no system setting.
# About 4 minutes.
#
#   sudo sh run22-page-classes.sh [pid of the VMM]
cd "$(dirname "$0")" || exit 1
PID=${1:-$(pgrep -x pvm | head -1)}
E=11,2d,17
echo "# run22 start $(date -Is) uid=$(id -u) vmm_pid=$PID memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)" >> meta.log
python3 vm-frames.py "$PID" guest-regions-n5.txt > vm-frames-n5.txt 2>&1
: > expN5.log
for rep in 1 2 3 4 5 6 7 8 9 10 11 12; do
  hold=$(( (rep - 1) * 192 ))
  pid=""
  if [ "$hold" -gt 0 ]; then
    taskset -c 5 ./bgload w $hold 600 > /dev/null 2>&1 &
    pid=$!
    # wait until the block is resident (at most 20 s), then stop the process
    n=0
    while [ "$(awk '/VmRSS/{print $2}' /proc/$pid/status 2>/dev/null || echo 0)" -lt $(( hold * 1000 )) ] && [ $n -lt 100 ]; do
      sleep 0.2
      n=$((n + 1))
    done
    kill -STOP $pid
  fi
  for pf in 0 1; do
    for cfg in "4 2" "8 1"; do
      set -- $cfg
      echo "N5 rep=$rep hold_mb=$hold $(REGIONS=guest-regions-n5.txt TLB_PREFAULT=$pf taskset -c 0 ./probe3 tlb $1 $2 64 $E 1 $rep 2>/dev/null)" >> expN5.log
    done
  done
  [ -n "$pid" ] && kill -KILL $pid
  wait 2>/dev/null
done
# the VM's regions again, to see how far the list moved during the run
python3 vm-frames.py "$PID" guest-regions-n5-end.txt > vm-frames-n5-end.txt 2>&1
echo "# run22 done $(date -Is) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)" >> meta.log
