#!/bin/sh
# Does the physical location / spread of the frames change RANDOM-access latency? Root, cpu0.
cd /tmp/kx-memprobe || exit 1
E=11,2d,2a,17,5,13
echo "# run3 start $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log
: > expF.log
for rep in 1 2 3; do
  for pol in compact scatter low high region:0 region:1 region:2 region:3; do
    taskset -c 0 ./frames 64 16 1024 $E $pol $((rep*11)) >> expF.log 2>&1
  done
done
echo "# run3 done $(date -Is) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
