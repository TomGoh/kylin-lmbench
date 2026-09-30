#!/bin/sh
# Exp G1: memory latency at fixed interconnect (NoC) frequencies.
# Root, cpu0.  Expects ./probe3 and ./bgload next to this script.  About 15 minutes.
#
# Unlike run_all.sh, run2.sh and run3.sh this script CHANGES A SYSTEM SETTING
# while it runs: it switches /sys/class/devfreq/nocfreq/governor to "userspace"
# and steps through fixed frequencies.  The original governor is restored when
# the script exits, whatever the reason; the last line it appends to meta.log
# shows the restored state.
#
# Question: does the interconnect frequency change memory latency, at which
# working-set sizes, and by how much?
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,2a,17,5,13
ORIG=$(cat $DF/governor) || exit 1
restore() {
  echo "$ORIG" > $DF/governor
  echo "# run4 restored governor=$(cat $DF/governor) cur_freq=$(cat $DF/cur_freq) $(date -Is)" >> meta.log
}
trap restore EXIT
trap 'exit 1' INT TERM HUP
echo "# run4 start $(date -Is) orig_governor=$ORIG cur_freq=$(cat $DF/cur_freq) available=$(cat $DF/available_frequencies) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log

echo userspace > $DF/governor
[ -w $DF/userspace/set_freq ] || { echo "# run4 abort: no userspace/set_freq" >> meta.log; exit 1; }

: > expG1.log
pass=0
for f in 1800000 1450000 1200000 900000 600000 1800000; do
  pass=$((pass + 1))
  echo $f > $DF/userspace/set_freq
  sleep 1
  tag="G1 pass=$pass set=$f got=$(cat $DF/cur_freq)"
  # random chase (lmbench -t pattern), chain built once
  for seed in 101 202; do
    for sz in 1 2 3 4 6 8 12 16 32 64; do
      echo "$tag $(taskset -c 0 ./probe3 rand $sz 16 64 $E 0 $seed 2>&1)" >> expG1.log
    done
  done
  # sequential chase, stride 256, around the L3 size and in DRAM
  for rep in 1 2 3; do
    for sz in 4 6 8 12 16 64; do
      echo "$tag $(taskset -c 0 ./probe3 seq $sz 256 64 $E 0 2>&1)" >> expG1.log
    done
  done
  # sequential chase over 64 MB at other strides
  for rep in 1 2; do
    for st in 16 64 1024; do
      echo "$tag $(taskset -c 0 ./probe3 seq 64 $st 64 $E 0 2>&1)" >> expG1.log
    done
  done
  # the same two headline points with the chain rewritten before every interval, as lmbench does
  for rep in 1 2 3; do
    echo "$tag $(taskset -c 0 ./probe3 seq 8 256 64 $E 1 2>&1)" >> expG1.log
  done
  echo "$tag $(taskset -c 0 ./probe3 rand 64 16 64 $E 1 101 2>&1)" >> expG1.log
  # streaming read and write rate over 256 MB
  echo "$tag $(taskset -c 0 ./bgload r 256 2 2>&1)" >> expG1.log
  echo "$tag $(taskset -c 0 ./bgload w 256 2 2>&1)" >> expG1.log
done
echo "# run4 done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
