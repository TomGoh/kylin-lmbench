#!/bin/sh
# For the N90 (the paper's machine): what do the two levels of the 8 MB point
# go with, the physical layout of lmbench's buffer or the interconnect
# frequency?
#
# Runs the paper's own command (lat_mem_rd -P 1 64 16 32 64 128 256 512 1024)
# several times and records, for every data point,
#   - the physical layout of the buffer of the lmbench child that measured it
#     (lmb-frames.py reads /proc/<pid>/pagemap), and
#   - the interconnect frequency every 100 ms (nocsample),
# plus the state of the machine before and after (boot mode, THP switches,
# devfreq governors, per-CPU free-list limits, free blocks by order).
# It changes NO system setting; run it in whatever environment the paper's
# numbers were taken in (services masked, CPU frequency locked, THP never).
#
#   sudo sh run30-n90-two-levels.sh [sweeps, default 6] [cpu, default 0]
#
# About 5.5 minutes per sweep.  Output: directory twolevels-<mode>-<time>/
#   state-before.txt state-after.txt   machine state
#   lmbench.log     lmbench's output, every line prefixed with its time
#   frames.log      one line per lmbench child: pages, adjacency, runs
#   noc.log         time and interconnect frequency every 100 ms
# Evaluate with analyze-state-experiments.py (section H3 shows how a child is
# matched to its output line).  If the library run27 uses is wanted as well:
# sudo sh run27-lmbench-layout-shim.sh afterwards (needs THP enabled for the
# library's pool: transparent_hugepage/enabled = madvise or always).
# Expects ./lat_mem_rd ./nothp ./nocsample ./lmb-frames.py (make; sh build-lmbench-tools.sh).
cd "$(dirname "$0")" || exit 1
N=${1:-6}
CPU=${2:-0}
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
OUT=twolevels-${MODE:-unset}-$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT" || exit 1
state() {
  echo "## $(date -Is) uname: $(uname -a)"
  echo "## cmdline: $(cat /proc/cmdline)"
  echo "## kernel config:"; grep -E 'CONFIG_X1_RMS|CONFIG_ARM64_CONTPTE|CONFIG_TRANSPARENT_HUGEPAGE' /boot/config-$(uname -r) 2>/dev/null
  echo "## THP:"; for f in /sys/kernel/mm/transparent_hugepage/enabled /sys/kernel/mm/transparent_hugepage/defrag /sys/kernel/mm/transparent_hugepage/shmem_enabled /sys/kernel/mm/transparent_hugepage/hugepages-*/enabled; do echo "$f: $(cat $f 2>/dev/null)"; done
  echo "## devfreq:"; for d in /sys/class/devfreq/*; do [ -d "$d" ] && echo "$d governor=$(cat $d/governor 2>/dev/null) cur_freq=$(cat $d/cur_freq 2>/dev/null) available=$(cat $d/available_frequencies 2>/dev/null)"; done
  echo "## cpufreq cpu$CPU: governor=$(cat /sys/devices/system/cpu/cpu$CPU/cpufreq/scaling_governor 2>/dev/null) cur=$(cat /sys/devices/system/cpu/cpu$CPU/cpufreq/scaling_cur_freq 2>/dev/null) max=$(cat /sys/devices/system/cpu/cpu$CPU/cpufreq/scaling_max_freq 2>/dev/null)"
  echo "## meminfo:"; grep -E 'MemTotal|MemFree|MemAvailable|AnonHugePages' /proc/meminfo
  echo "## min_free_kbytes=$(cat /proc/sys/vm/min_free_kbytes) percpu_pagelist_high_fraction=$(cat /proc/sys/vm/percpu_pagelist_high_fraction 2>/dev/null)"
  echo "## buddyinfo:"; cat /proc/buddyinfo
  echo "## pagetypeinfo:"; cat /proc/pagetypeinfo 2>/dev/null
  echo "## zoneinfo:"; cat /proc/zoneinfo
  echo "## kvm log:"; dmesg 2>/dev/null | grep -i 'kvm \[' | tail -12
  echo "## loadavg: $(cat /proc/loadavg)"
  echo "## processes:"; ps -eo pid,ppid,psr,pcpu,rss,etimes,comm --sort=-pcpu | head -40
  echo "## VMs:"; pgrep -a crosvm; pgrep -a pvm; pgrep -a qemu
}
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
state > "$OUT/state-before.txt" 2>&1
taskset -c 7 ./nocsample 100 "$OUT/noc.log" &
NOC=$!
taskset -c 6 python3 lmb-frames.py "$OUT/frames.log" &
WATCH=$!
trap 'kill $NOC $WATCH 2>/dev/null' EXIT
trap 'exit 1' INT TERM HUP
: > "$OUT/lmbench.log"
i=1
while [ "$i" -le "$N" ]; do
  echo "## sweep=$i start=$(date +%s.%N | cut -c1-14) noc=$(cat /sys/class/devfreq/nocfreq/cur_freq 2>/dev/null) free blocks by order: $(grep Normal /proc/buddyinfo | tr -s ' ' | cut -d' ' -f5-)" >> "$OUT/lmbench.log"
  # nothp only guarantees 4 KiB pages for the buffer if the system THP switch is not 'never'
  taskset -c "$CPU" ./nothp ./lat_mem_rd -P 1 64 16 32 64 128 256 512 1024 2>&1 | stamp >> "$OUT/lmbench.log"
  i=$((i + 1))
done
kill $NOC $WATCH 2>/dev/null
state > "$OUT/state-after.txt" 2>&1
echo "done: $OUT"
