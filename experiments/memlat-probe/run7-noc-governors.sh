#!/bin/sh
# Exp G2 and G3: memory latency under each interconnect (NoC) frequency governor.
# Root, cpu0.  Expects ./probe3 and ./bgload next to this script.  About 25 minutes.
#
# CHANGES A SYSTEM SETTING while it runs: /sys/class/devfreq/nocfreq/governor.
# The original governor is restored when the script exits, whatever the reason.
#
# G2: is the 8 MB sequential point two-valued when the frequency follows bus
#     traffic (the driver default), and does the value follow the frequency?
#     Where does the frequency sit during the random chase?
# G3: what does memory traffic from other cores do in each case?
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,2a,17,5,13
ORIG=$(cat $DF/governor) || exit 1
restore() {
  echo "$ORIG" > $DF/governor
  echo "# run7 restored governor=$(cat $DF/governor) cur_freq=$(cat $DF/cur_freq) $(date -Is)" >> meta.log
}
trap restore EXIT
trap 'exit 1' INT TERM HUP
trans() { awk '/Total transition/{print $NF}' $DF/trans_stat; }
echo "# run7 start $(date -Is) orig_governor=$ORIG cur_freq=$(cat $DF/cur_freq) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log

: > expG2.log
for gov in performance simple_ondemand stable_ondemand; do
  echo $gov > $DF/governor
  sleep 3
  tag="G2 gov=$(cat $DF/governor)"
  echo "# run7 G2 gov=$(cat $DF/governor) begin $(date -Is) cur_freq=$(cat $DF/cur_freq) transitions=$(trans)" >> meta.log
  # sequential stride 256, fresh process per point, chain rewritten before every interval as lmbench does;
  # the 8 MB point also with the chain built once
  for lap in $(seq 1 12); do
    for sz in 4 6 8 12 16 64; do
      echo "$tag lap=$lap $(taskset -c 0 ./probe3 seq $sz 256 64 $E 1 2>&1)" >> expG2.log
    done
    echo "$tag lap=$lap $(taskset -c 0 ./probe3 seq 8 256 64 $E 0 2>&1)" >> expG2.log
  done
  # random chase
  for seed in 11 22 33; do
    for sz in 3 4 8 64; do
      echo "$tag $(taskset -c 0 ./probe3 rand $sz 16 64 $E 1 $seed 2>&1)" >> expG2.log
    done
  done
  for seed in 11 22; do
    echo "$tag $(taskset -c 0 ./probe3 rand 64 16 64 $E 0 $seed 2>&1)" >> expG2.log
  done
  echo "$tag $(taskset -c 0 ./bgload r 256 2 2>&1) noc_after=$(cat $DF/cur_freq)" >> expG2.log
  echo "$tag $(taskset -c 0 ./bgload w 256 2 2>&1) noc_after=$(cat $DF/cur_freq)" >> expG2.log
  echo "# run7 G2 gov=$(cat $DF/governor) end $(date -Is) cur_freq=$(cat $DF/cur_freq) transitions=$(trans)" >> meta.log
done

: > expG3.log
for gov in performance simple_ondemand; do
  echo $gov > $DF/governor
  sleep 3
  for bg in none r1 w1 w2; do
    pids=""
    case $bg in
      r1) taskset -c 5 ./bgload r 256 600 > /dev/null & pids=$! ;;
      w1) taskset -c 5 ./bgload w 256 600 > /dev/null & pids=$! ;;
      w2) taskset -c 5 ./bgload w 256 600 > /dev/null & pids=$!
          taskset -c 6 ./bgload w 256 600 > /dev/null & pids="$pids $!" ;;
    esac
    sleep 2
    tag="G3 gov=$(cat $DF/governor) bg=$bg"
    for rep in 1 2 3; do
      echo "$tag $(taskset -c 0 ./probe3 seq 4 256 64 $E 1 2>&1)" >> expG3.log
      echo "$tag $(taskset -c 0 ./probe3 seq 8 256 64 $E 1 2>&1)" >> expG3.log
      echo "$tag $(taskset -c 0 ./probe3 seq 64 256 64 $E 1 2>&1)" >> expG3.log
      echo "$tag $(taskset -c 0 ./probe3 rand 8 16 64 $E 1 $((rep * 7)) 2>&1)" >> expG3.log
    done
    for rep in 1 2; do
      echo "$tag $(taskset -c 0 ./probe3 rand 64 16 64 $E 1 $((rep * 7)) 2>&1)" >> expG3.log
    done
    [ -n "$pids" ] && kill $pids 2>/dev/null
    wait 2>/dev/null
  done
done
echo "# run7 done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
