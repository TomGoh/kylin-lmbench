#!/bin/sh
# Exp H: lmbench's own lat_mem_rd, repeated, in whatever platform state the
# machine is in.  Changes no system setting.  cpu0.  About 50 minutes.
# Expects ./lat_mem_rd ./nothp ./nocsample next to this script.
#
# The program runs under ./nothp so that its malloc()ed buffer uses 4 KiB
# pages as in the June N90 runs (THP never) even if the system setting is
# "always".  Three sweeps with the system setting left to apply are taken at
# the end for contrast.
#
# Every lmbench output line is prefixed with the wall-clock time at which it
# appeared; expH-noc-samples.log holds the interconnect frequency every 100 ms.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
echo "# run9 start $(date -Is) uid=$(id -u) $(st) thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled) cpu0_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log

: > expH-noc-samples.log
taskset -c 7 ./nocsample 100 expH-noc-samples.log &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT
trap 'exit 1' INT TERM HUP

sweep() {   # $1 = log, $2 = label, $3 = sweep number, $4 = wrapper ("./nothp" or ""), rest = lat_mem_rd arguments
  log=$1; label=$2; n=$3; wrap=$4; shift 4
  echo "## thp=$label sweep=$n start=$(date +%s.%N | cut -c1-14) $(st) args=$*" >> "$log"
  taskset -c 0 $wrap ./lat_mem_rd "$@" 2>&1 | stamp >> "$log"
}

: > expH-rand.log
: > expH-seq256.log
: > expH-seqall.log
for i in 1 2 3; do sweep expH-rand.log off $i ./nothp -t -P 1 64 16; done
for i in $(seq 1 16); do sweep expH-seq256.log off $i ./nothp -P 1 64 256; done
for i in 1 2; do sweep expH-seqall.log off $i ./nothp -P 1 64 16 32 64 128 256 512 1024; done
for i in 4 5; do sweep expH-rand.log off $i ./nothp -t -P 1 64 16; done
# contrast: the system THP setting applies
for i in 1 2 3; do sweep expH-seq256.log system $i "" -P 1 64 256; done
for i in 1 2; do sweep expH-rand.log system $i "" -t -P 1 64 16; done
echo "# run9 done $(date -Is) $(st) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
