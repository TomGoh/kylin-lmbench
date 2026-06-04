#!/usr/bin/env bash
# Pre-bench 环境校验：在每个配置 reboot 后、运行 bench 前调用一次。
# 失败任何一条都 exit 1，强制人工介入。

set -u
FAIL=0
ok() { echo "  ✓ $*"; }
ng() { echo "  ✗ $*"; FAIL=1; }

echo "=== 1. systemd target ==="
[[ "$(systemctl get-default 2>/dev/null)" == "multi-user.target" ]] \
  && ok "default = multi-user.target" \
  || ng "default 不是 multi-user.target ($(systemctl get-default))"

echo "=== 2. LSM 栈 ==="
LSM="$(cat /sys/kernel/security/lsm 2>/dev/null)"
[[ "$LSM" == "capability,kycp" ]] \
  && ok "LSM = $LSM (无 ksaf / bpf / audit)" \
  || ng "LSM = $LSM, 期望 capability,kycp"

echo "=== 3. /sys/fs/box（ksaf LSM 模块痕迹） ==="
[[ ! -e /sys/fs/box ]] \
  && ok "ksaf 模块未加载" \
  || ng "/sys/fs/box 存在，ksaf 模块还在！"

echo "=== 4. /proc/cmdline ==="
CMDLINE="$(cat /proc/cmdline 2>/dev/null)"
echo "$CMDLINE" | grep -qE 'kvm-arm.mode=(none|vhe|nvhe|protected)' \
  && ok "kvm-arm.mode = $(echo "$CMDLINE" | grep -oE 'kvm-arm.mode=[a-z]+')" \
  || ng "kvm-arm.mode 缺失或非法"
echo "$CMDLINE" | grep -q 'lsm=[[:space:]]' || echo "$CMDLINE" | grep -q 'lsm= ' \
  && ok "lsm= 为空" \
  || ng "lsm= 不为空，可能有 LSM 模块在拖累"
echo "$CMDLINE" | grep -q 'audit=0' \
  && ok "audit=0" \
  || ng "audit 不是 0"

echo "=== 5. CPU 频率 + 调速器 ==="
for cpu in 0 1 2 3 7; do
  FREQ=$(cat /sys/devices/system/cpu/cpu${cpu}/cpufreq/scaling_cur_freq 2>/dev/null)
  GOV=$(cat /sys/devices/system/cpu/cpu${cpu}/cpufreq/scaling_governor 2>/dev/null)
  if [[ "$FREQ" == "1900000" && "$GOV" == "performance" ]]; then
    ok "cpu${cpu}: 1900000 kHz performance"
  else
    ng "cpu${cpu}: freq=$FREQ gov=$GOV (期望 1900000 / performance)"
  fi
done

echo "=== 6. THP / ASLR ==="
THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null)
echo "$THP" | grep -q '\[never\]' \
  && ok "THP = never" \
  || ng "THP = $THP"
ASLR=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)
[[ "$ASLR" == "0" ]] \
  && ok "ASLR = 0" \
  || ng "ASLR = $ASLR"

echo "=== 7. 噪声进程白名单外的违规 ==="
# 允许出现的：
#   - 所有内核线程（cmd 用方括号包起来，如 [kworker/0:1]）
#   - systemd 系列、dbus、NetworkManager、wpa_supplicant、sshd
#   - bench 自身：bench.sh / scripts/lmbench / lat_* / bw_* / par_* / stream / cache 等
#   - 一些必要的 Kylin 网络支撑（kylin-nm-sysdbus、nm-enhance-optimization）
# 用 PPID 排除内核线程：kernel thread ppid == 2 (kthreadd) 或 == 0 (kthreadd 本身)
# 用户态进程白名单：systemd 系列、SSH、dbus、网络、bench、bash 自身
ALLOWED='/sbin/init|/lib/systemd|/usr/lib/systemd|sshd|dbus|NetworkManager|wpa_supplicant|nm-enhance|kylin-nm-sysdbus|bench\.sh|scripts/lmbench|lat_|bw_|par_|stream|enough|cache|^tlb|hello|getopt|tail|polkitd|pollinate|^bash|/bin/bash|/usr/bin/bash|sd-pam|verify-clean-env|apply-masks| ps --no-headers| awk | head -30| grep | sleep |kylin-nm-netctrl|lmhttp|lmdd|stream2|/usr/bin/disk|prepare-host|quiet-host'
PIDS=$(ps --no-headers -eo pid,ppid,cmd 2>/dev/null \
  | awk '$2 != 2 && $2 != 0 {pid=$1; cmd=""; for (i=3; i<=NF; i++) cmd = cmd (i==3?"":" ") $i; print pid, cmd}' \
  | grep -vE "$ALLOWED" \
  | grep -vE "^\s*$|grep" \
  | head -30)
if [[ -z "$PIDS" ]]; then
  ok "无违规进程"
else
  ng "发现违规进程："
  echo "$PIDS" | sed 's/^/      /'
fi

echo "=== 8. KVM 初始化模式（dmesg） ==="
KVM_INIT=$(dmesg 2>/dev/null | grep -iE "VHE mode|Hyp mode|Protected nVHE|KVM disabled" | tail -1)
[[ -n "$KVM_INIT" ]] \
  && ok "$KVM_INIT" \
  || ng "dmesg 没有 KVM 初始化标志线，状态不明"

echo
if [[ "$FAIL" == "0" ]]; then
  echo "[verify-clean-env] ✓ ALL CLEAN"
  exit 0
else
  echo "[verify-clean-env] ✗ 有失败项，bench 不应进行"
  exit 1
fi
