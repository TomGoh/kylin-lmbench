#!/bin/sh
# Exp W: is the "same pages, different virtual order" effect of Exp L a stage-2
# effect?  Sequential chase (stride 256) over the same set of pages in
# physically sorted and in shuffled virtual order, separately for pages that
# share a 2 MiB region with the running protected VM (4 KiB stage-2 leaves) and
# pages that do not (block-mapped at stage 2).
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 10 minutes.
# Expects ./frames2 and guest-regions.txt (written by run11 or run12).
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run13 start $(date -Is) uid=$(id -u) $(st)" >> meta.log
: > expW.log
rep=0
for sz in 8 16 64; do
  for pick in low even; do
    for order in sorted shuffled; do
      rep=$((rep + 1))
      echo "## rep=$rep size_mb=$sz pick=$pick order=$order mode=seq256 $(date -Is) $(st)" >> expW.log
      taskset -c 0 ./frames2 $sz 3072 $E 37 $pick guest-regions.txt seq256 $order >> expW.log 2>&1
    done
  done
done
echo "# run13 done $(date -Is) $(st)" >> meta.log
