#!/bin/sh
# PROPOSED, NOT EXECUTED (as of 2026-09-30).
#
# Same-machine comparison across KVM boot modes: the measurement that is still
# missing.  Run it once per boot mode (kvm-arm.mode=none | nvhe | vhe |
# protected), as root, from the directory that holds ./probe (make first).
# Then compare the output directories with analyze-mode-compare.py.
#
#   sudo sh run5-mode-compare.sh [label]        # about 15 minutes
#
# It changes NO system setting.  It records the state it finds (boot mode,
# kernel config, THP knobs, CPU frequency, devfreq governors and frequencies,
# running services) before and after, and the interconnect frequency before and
# after every single probe run, because the June runs recorded none of these.
#
# Output: modecmp-<label>-<timestamp>/
#   state-before.txt state-after.txt   platform state
#   rand.log   random chase (lmbench -t, stride 16), 14 sizes x 5 seeds
#   seq.log    sequential chase over 64 MB, 6 strides x 5 repetitions
#   llc.log    sequential stride 256 at 4..64 MB, fresh process per point, 30 laps
#   tlb.log    translation-only chase (frames2 tlb<L>) per GiB slot, 5 configurations x 3 seeds;
#              the most direct measure of what a page walk costs in each boot mode, because the
#              data stay in the L1/L2 caches (needs ./frames2 and root)
cd "$(dirname "$0")" || exit 1
[ -x ./probe ] || { echo "build ./probe first (make)" >&2; exit 1; }
CPU=${CPU:-0}
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
LABEL=${1:-${MODE:-default}}
OUT=modecmp-$LABEL-$(date +%Y%m%d-%H%M%S)
mkdir "$OUT" || exit 1
NOC=/sys/class/devfreq/nocfreq
E=11,2d,5,2a,17,13

state() {
  echo "date: $(date -Is)"
  echo "label: $LABEL"
  echo "kvm_arm_mode: ${MODE:-(not on the command line)}"
  echo "uname: $(uname -a)"
  echo "uptime: $(uptime)"
  echo "cmdline: $(cat /proc/cmdline)"
  echo "loadavg: $(cat /proc/loadavg)"
  echo "## kvm lines in the kernel log"
  dmesg 2>/dev/null | grep -iE 'kvm|IPA Size|hyp mode|nVHE|VHE' | head -40
  echo "## kernel config"
  grep -E 'CONFIG_X1_RMS|CONFIG_KVM=|CONFIG_TRANSPARENT_HUGEPAGE|CONFIG_ARM64_CONTPTE|PHYTIUM_(NOC|DMU)_DEVFREQ' "/boot/config-$(uname -r)" 2>/dev/null
  echo "## transparent huge pages"
  for f in /sys/kernel/mm/transparent_hugepage/enabled /sys/kernel/mm/transparent_hugepage/defrag \
           /sys/kernel/mm/transparent_hugepage/shmem_enabled /sys/kernel/mm/transparent_hugepage/hugepages-*/enabled; do
    [ -r "$f" ] && echo "$f: $(cat "$f")"
  done
  echo "randomize_va_space: $(cat /proc/sys/kernel/randomize_va_space)"
  echo "## cpufreq"
  for c in /sys/devices/system/cpu/cpu[0-9]*; do
    p=$c/cpufreq
    [ -d "$p" ] && echo "$(basename "$c"): governor=$(cat $p/scaling_governor) cur=$(cat $p/scaling_cur_freq) min=$(cat $p/scaling_min_freq) max=$(cat $p/scaling_max_freq) hw_cur=$(cat $p/cpuinfo_cur_freq 2>/dev/null)"
  done
  echo "## cpuidle (cpu$CPU)"
  for s in /sys/devices/system/cpu/cpu$CPU/cpuidle/state*; do
    [ -d "$s" ] && echo "$(basename "$s"): name=$(cat $s/name) disable=$(cat $s/disable)"
  done
  echo "## devfreq"
  for d in /sys/class/devfreq/*; do
    [ -d "$d" ] || continue
    echo "### $(basename "$d") -> $(readlink -f "$d/device" 2>/dev/null) driver=$(basename "$(readlink -f "$d/device/driver" 2>/dev/null)")"
    for a in governor cur_freq min_freq max_freq available_frequencies available_governors polling_interval; do
      [ -r "$d/$a" ] && echo "$a: $(cat "$d/$a")"
    done
    echo "trans_stat:"; cat "$d/trans_stat" 2>/dev/null
  done
  echo "## memory"
  grep -E 'MemTotal|MemFree|MemAvailable|AnonHugePages|^Cached' /proc/meminfo
  cat /proc/buddyinfo
  echo "## running services"
  systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print $1}' | tr '\n' ' '
  echo
  echo "## power-management processes"
  ps -eo pid,user,comm 2>/dev/null | grep -iE 'power|upower|tlp|thermal' | grep -v grep
  echo "## virtual machines"
  ps -eo pid,user,lstart,comm,args 2>/dev/null | grep -E 'crosvm|qemu|pvm-manage' | grep -v grep
}

noc() { cat $NOC/cur_freq 2>/dev/null || echo na; }

# run one probe and prefix its line with the interconnect frequency before and after
one() {   # $1 = log file, rest = probe arguments
  log=$1; shift
  b=$(noc)
  out=$(taskset -c "$CPU" ./probe "$@" 2>&1)
  echo "noc_before=$b noc_after=$(noc) $out" >> "$OUT/$log"
}

state > "$OUT/state-before.txt" 2>&1

for seed in 101 202 303 404 505; do
  for sz in 0.5 1 1.5 2 3 4 6 8 12 16 24 32 48 64; do
    one rand.log rand $sz 16 64 0 $E $seed
  done
done

for rep in 1 2 3 4 5; do
  for st in 16 64 128 256 512 1024; do
    one seq.log seq 64 $st 64 0 $E
  done
done

for lap in $(seq 1 30); do
  for sz in 4 6 8 12 16 64; do
    one llc.log seq $sz 256 64 0 $E
  done
done

# translation-only chase: another page on every hop, few cache lines per page
if [ -x ./frames2 ] && [ "$(id -u)" = 0 ]; then
  for seed in 51 53 57; do
    for cfg in "4 tlb4" "8 tlb2" "16 tlb1" "8 tlb1" "32 tlb1"; do
      set -- $cfg
      echo "## size_mb=$1 pick=even mode=$2 seed=$seed noc=$(noc) $(date -Is)" >> "$OUT/tlb.log"
      taskset -c "$CPU" ./frames2 $1 2048 11,2d,17,2a,3,5 $seed even - $2 >> "$OUT/tlb.log" 2>&1
    done
  done
else
  echo "tlb.log skipped: needs ./frames2 and root" >&2
fi

state > "$OUT/state-after.txt" 2>&1
echo "done: $OUT"
