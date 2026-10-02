#!/bin/sh
# Exp G5: does lmbench's 8 MB point follow the interconnect (NoC) frequency?
#
# Question (worklog 11.33): the N90's two 8 MB levels are judged to come from a
# platform state that changes from one lmbench child to the next, with the
# NoC devfreq governor as the candidate.  Here the unmodified lat_mem_rd runs
# under three governors -- performance (pinned at the maximum, the N80's
# setting all along), simple_ondemand (follows bus traffic) and powersave
# (pinned at the minimum) -- while
#   nocsample      records the NoC frequency every 100 ms, and
#   lmb-frames.py  records the physical layout of every child's buffer,
# so that every data point can be matched with both.
#
# ROOT.  About 35-40 minutes.  Pinned to cpu0 (sampler cpu7, watcher cpu6).
# CHANGES A SYSTEM SETTING while it runs: /sys/class/devfreq/nocfreq/governor.
# The original governor is restored when the script exits, whatever the
# reason (normal end, error, Ctrl-C); the last line of meta.log shows it.
# Nothing else is changed (no max_freq/min_freq writes, no THP change).
#
#   cd /tmp/kx-memprobe && sudo sh ./run33-noc-lmbench-frames.sh
#
# Expects ./lat_mem_rd ./nothp ./nocsample ./lmb-frames.py next to it.
cd "$(dirname "$0")" || exit 1
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
for f in lat_mem_rd nothp nocsample lmb-frames.py; do [ -e "$f" ] || { echo "missing ./$f"; exit 1; }; done
DF=/sys/class/devfreq/nocfreq
ORIG=$(cat $DF/governor) || exit 1
SAMPLER=""
WATCH=""
restore() {
  [ -n "$SAMPLER" ] && kill $SAMPLER 2>/dev/null
  [ -n "$WATCH" ] && kill $WATCH 2>/dev/null
  echo "$ORIG" > $DF/governor
  echo "# run33 restored governor=$(cat $DF/governor) cur_freq=$(cat $DF/cur_freq) $(date -Is)" >> meta.log
  echo "run33: governor restored to $(cat $DF/governor)"
}
trap restore EXIT
trap 'exit 1' INT TERM HUP
st() { echo "gov=$(cat $DF/governor) noc=$(cat $DF/cur_freq)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
trans() { awk '/Total transition/{print $NF}' $DF/trans_stat; }
echo "# run33 start $(date -Is) orig_governor=$ORIG cur_freq=$(cat $DF/cur_freq) available=$(cat $DF/available_frequencies | tr ' ' ,) min=$(cat $DF/min_freq) max=$(cat $DF/max_freq) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log

: > expG5.log
: > expG5-frames.log
: > expG5-noc-samples.log
taskset -c 7 ./nocsample 100 expG5-noc-samples.log &
SAMPLER=$!
taskset -c 6 python3 lmb-frames.py expG5-frames.log lat_mem_rd &
WATCH=$!
sleep 1

sweep() {   # $1 = state label, $2 = sweep number, rest = lat_mem_rd arguments
  state=$1; n=$2; shift 2
  echo "## state=$state sweep=$n start=$(date +%s.%N | cut -c1-14) $(st) transitions=$(trans) args=$*" >> expG5.log
  taskset -c 0 ./nothp ./lat_mem_rd "$@" 2>&1 | stamp >> expG5.log
  echo "## end state=$state sweep=$n $(st) transitions=$(trans)" >> expG5.log
}
state() {   # $1 = governor
  echo "$1" > $DF/governor || { echo "# run33 could not set $1" >> meta.log; return 1; }
  sleep 3
  echo "# run33 governor=$(cat $DF/governor) begin $(date -Is) cur_freq=$(cat $DF/cur_freq) transitions=$(trans)" >> meta.log
}

# A: pinned at the maximum (the setting of every N80 measurement so far)
state performance
for i in 1 2 3 4; do sweep max $i -P 1 64 256; done
sweep max 1 -t -P 1 64 16

# B: frequency follows bus traffic (devfreq simple_ondemand)
if state simple_ondemand; then
  for i in $(seq 1 12); do sweep ondemand $i -P 1 64 256; done
  sweep ondemand 1 -P 1 64 16 32 64 128 256 512 1024
  for i in 1 2; do sweep ondemand $i -t -P 1 64 16; done
fi

# C: pinned at the minimum
if state powersave; then
  for i in 1 2 3 4; do sweep min $i -P 1 64 256; done
  sweep min 1 -t -P 1 64 16
fi

cp $DF/trans_stat expG5-trans_stat.txt 2>/dev/null
echo "# run33 done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
echo "run33: done; logs expG5.log expG5-frames.log expG5-noc-samples.log"
