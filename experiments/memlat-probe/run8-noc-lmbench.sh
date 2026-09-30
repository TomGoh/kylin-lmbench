#!/bin/sh
# Exp G4: lmbench's own lat_mem_rd (and bw_mem) in three interconnect (NoC)
# frequency states: pinned at the maximum, following bus traffic (the driver
# default), pinned at the minimum.  Root, cpu0.  About 50 minutes.
# Expects ./lat_mem_rd ./bw_mem (build-lmbench-tools.sh) and ./nocsample.
#
# CHANGES A SYSTEM SETTING while it runs: /sys/class/devfreq/nocfreq/governor.
# The original governor is restored when the script exits, whatever the reason.
#
# Every output line of lmbench is prefixed with the wall-clock time at which
# it appeared, and expG4-noc-samples.log holds the interconnect frequency every
# 100 ms, so each data point can be matched with the frequency during it.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
ORIG=$(cat $DF/governor) || exit 1
SAMPLER=""
restore() {
  [ -n "$SAMPLER" ] && kill $SAMPLER 2>/dev/null
  echo "$ORIG" > $DF/governor
  echo "# run8 restored governor=$(cat $DF/governor) cur_freq=$(cat $DF/cur_freq) $(date -Is)" >> meta.log
}
trap restore EXIT
trap 'exit 1' INT TERM HUP
echo "# run8 start $(date -Is) orig_governor=$ORIG cur_freq=$(cat $DF/cur_freq) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }

: > expG4-noc-samples.log
taskset -c 7 ./nocsample 100 expG4-noc-samples.log &
SAMPLER=$!

sweep() {   # $1 = log, $2 = state label, $3 = sweep number, rest = lat_mem_rd arguments
  log=$1; state=$2; n=$3; shift 3
  echo "## state=$state sweep=$n start=$(date +%s.%N | cut -c1-14) gov=$(cat $DF/governor) noc=$(cat $DF/cur_freq) args=$*" >> "$log"
  taskset -c 0 ./lat_mem_rd "$@" 2>&1 | stamp >> "$log"
}
bw() {      # $1 = state label
  for what in "8m rd" "8m wr" "64m rd" "64m wr"; do
    for rep in 1 2 3; do
      echo "state=$1 bw_mem $what: $(taskset -c 0 ./bw_mem -P 1 $what 2>&1) noc_after=$(cat $DF/cur_freq)" >> expG4-bw.log
    done
  done
}

: > expG4-seq256.log
: > expG4-seqall.log
: > expG4-rand.log
: > expG4-bw.log

# state 1: pinned at the maximum
echo performance > $DF/governor; sleep 3
for i in 1 2; do sweep expG4-rand.log max $i -t -P 1 64 16; done
for i in $(seq 1 8); do sweep expG4-seq256.log max $i -P 1 64 256; done
bw max

# state 2: frequency follows bus traffic (driver default)
echo simple_ondemand > $DF/governor; sleep 3
for i in 1 2 3; do sweep expG4-rand.log ondemand $i -t -P 1 64 16; done
for i in $(seq 1 12); do sweep expG4-seq256.log ondemand $i -P 1 64 256; done
sweep expG4-seqall.log ondemand 1 -P 1 64 16 32 64 128 256 512 1024
bw ondemand

# state 3: pinned at the minimum
echo userspace > $DF/governor
if [ -w $DF/userspace/set_freq ]; then
  echo 600000 > $DF/userspace/set_freq; sleep 3
  for i in 1 2; do sweep expG4-rand.log min $i -t -P 1 64 16; done
  for i in 1 2 3 4; do sweep expG4-seq256.log min $i -P 1 64 256; done
  bw min
fi
echo "# run8 done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
