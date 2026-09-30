#!/bin/sh
# Controlled physical-layout experiments. Root (pagemap), cpu0. Output in /tmp/kx-memprobe.
cd /tmp/kx-memprobe || exit 1
E=11,2a,17,2d,5,13
echo "# run2 start $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log
: > expL.log
for rep in 1 2 3; do
  for sz in 4 6 8 12 16 32; do
    echo "## rep=$rep size=$sz stride=256" >> expL.log
    taskset -c 0 ./layout $sz 256 192 $E sorted,shuffled,reversed,sorted,shuffled $((rep*100+1)) >> expL.log 2>&1
  done
  for st in 128 512 1024; do
    echo "## rep=$rep size=8 stride=$st" >> expL.log
    taskset -c 0 ./layout 8 $st 192 $E sorted,shuffled,reversed $((rep*100+2)) >> expL.log 2>&1
  done
done
: > expT.log
for rep in 1 2 3 4 5; do
  for t in none rand desc; do
    taskset -c 0 ./probe2 seq 64 256 64 0 $E 0 $t >> expT.log 2>&1
    taskset -c 0 ./probe2 seq 8 256 64 0 $E 0 $t >> expT.log 2>&1
  done
done
echo "# run2 done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
