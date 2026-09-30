#!/bin/sh
# PROPOSED, NOT EXECUTED (as of 2026-09-30).
#
# Question: how much does the NoC (interconnect) frequency-scaling state change
# memory latency on this platform, and does the on-demand governor make the
# 8 MB sequential point bistable?
#
# Unlike the other run scripts this one CHANGES A SYSTEM SETTING: it switches
# /sys/class/devfreq/nocfreq/governor to "userspace" (fixed frequencies), then
# to the on-demand governors, and restores the original governor when it exits.
# Run it only on a machine you are free to disturb for about ten minutes, and
# check afterwards that the governor is back (last line of meta.log).
#
# Root, cpu0.  Expects ./probe in /tmp/kx-memprobe.
cd /tmp/kx-memprobe || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,2a,17,5,13
ORIG=$(cat $DF/governor)
restore() { echo "$ORIG" > $DF/governor; echo "# run4 restored governor=$(cat $DF/governor) cur_freq=$(cat $DF/cur_freq) $(date -Is)" >> meta.log; }
trap restore EXIT INT TERM
echo "# run4 start $(date -Is) orig_governor=$ORIG cur_freq=$(cat $DF/cur_freq) available=$(cat $DF/available_frequencies) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log

# run one probe while sampling the NoC frequency every 100 ms
one() {   # $1 = tag, rest = probe args
  tag=$1; shift
  : > .nocsample
  ( while :; do cat $DF/cur_freq; sleep 0.1; done ) >> .nocsample 2>/dev/null &
  sp=$!
  b=$(cat $DF/cur_freq)
  out=$(taskset -c 0 ./probe "$@" 2>&1)
  a=$(cat $DF/cur_freq)
  kill $sp 2>/dev/null; wait $sp 2>/dev/null
  stats=$(awk '{s+=$1; n++; if(min==""||$1<min)min=$1; if($1>max)max=$1; c[$1]++} END{printf "noc_mean=%.0f noc_min=%d noc_max=%d noc_samples=%d noc_hist=", s/n, min, max, n; for(k in c) printf "%d:%d,", k, c[k]}' .nocsample)
  echo "$tag noc_gov=$(cat $DF/governor) noc_before=$b noc_after=$a $stats $out"
}

# G1: fixed NoC frequencies
: > expG1.log
echo userspace > $DF/governor
for f in 600000 900000 1200000 1800000; do
  echo $f > $DF/userspace/set_freq; sleep 1
  for rep in 1 2 3; do
    one "G1 set=$f" rand 64 16 64 0 $E $((rep*13)) >> expG1.log
    one "G1 set=$f" seq 8 256 64 0 $E >> expG1.log
    one "G1 set=$f" seq 64 256 64 0 $E >> expG1.log
  done
  one "G1 set=$f" rand 8 16 64 0 $E 13 >> expG1.log
  one "G1 set=$f" rand 4 16 64 0 $E 13 >> expG1.log
  one "G1 set=$f" rand 1 16 64 0 $E 13 >> expG1.log
  one "G1 set=$f" seq 4 256 64 0 $E >> expG1.log
  one "G1 set=$f" seq 1 256 64 0 $E >> expG1.log
done

# G2: the governors that let the frequency follow measured traffic
: > expG2.log
for gov in simple_ondemand stable_ondemand; do
  echo $gov > $DF/governor; sleep 2
  for lap in $(seq 1 12); do
    for sz in 6 8 12 64; do
      one "G2 lap=$lap" seq $sz 256 64 0 $E >> expG2.log
    done
    one "G2 lap=$lap" rand 64 16 64 0 $E $lap >> expG2.log
    one "G2 lap=$lap" rand 8 16 64 0 $E $lap >> expG2.log
  done
done
echo "# run4 done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
