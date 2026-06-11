#!/bin/bash
# 开/关 hypervisor __hyp_printk 事件追踪(trace_hyp_printk / trace_debug! 的事件载体)。
#
# 仅 protected 模式可用(hyp tracefs 由 hyp_trace.c:958 门控;nvhe 下 buffer load 走
# share/donate hcall 会在未初始化 host_mmu 上 panic,勿放宽)。
#
# !! 有性能影响:只在短窗采证时开,采完立即 `trace_hyp.sh 0` 关闭 !!
# gate / perf 的计时窗口内必须保持 OFF,否则读数被污染。
#
# 用法: trace_hyp.sh <0|1>   (0=关, 1=开)
set -eu

[ "$#" -eq 1 ] && { [ "$1" = 0 ] || [ "$1" = 1 ]; } || {
    echo "Usage: $0 <mode: 0=disable | 1=enable>" >&2
    exit 1
}

# tracefs 在 Kylin V10 挂于 debugfs 下;允许 TRACEFS= 覆盖根路径。
TRACE_ROOT=${TRACEFS:-/sys/kernel/debug/tracing}
T="$TRACE_ROOT/hypervisor"
[ -d "$T" ] || {
    echo "ERROR: $T 不存在(需 protected 模式 + CONFIG_TRACING/PROTECTED_NVHE_FTRACE)" >&2
    exit 1
}

echo "$1" > "$T/tracing_on"
echo "$1" > "$T/events/hypervisor/__hyp_printk/enable"

status=$([ "$1" -eq 1 ] && echo "ENABLED" || echo "DISABLED")
echo "Hypervisor __hyp_printk tracing $status  ($T)"
