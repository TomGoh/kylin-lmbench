#!/bin/bash
# Identical runtime controls for any boot mode (protected/nvhe).
maxf=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)
for c in /sys/devices/system/cpu/cpu*/cpufreq; do
  echo performance | sudo tee $c/scaling_governor >/dev/null 2>&1
  echo $maxf | sudo tee $c/scaling_max_freq >/dev/null 2>&1
  echo $maxf | sudo tee $c/scaling_min_freq >/dev/null 2>&1
done
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled >/dev/null
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space >/dev/null
sudo sysctl -w kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0 >/dev/null
for s in /sys/devices/system/cpu/cpu*/cpuidle/state[1-9]*/disable; do
  [ -e "$s" ] && echo 1 | sudo tee $s >/dev/null 2>&1
done
echo "controls: gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) curfreq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled) aslr=$(cat /proc/sys/kernel/randomize_va_space) paranoid=$(cat /proc/sys/kernel/perf_event_paranoid)"
