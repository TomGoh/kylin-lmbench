#!/bin/bash
# run-core-scaling.sh — cluster-aware online-core sweep for the pKVM munmap TLBI
# broadcast hypothesis.
#
# Vary how many cores participate in the Inner-Shareable domain and measure the
# per-page munmap-only time. The local page-free + local-invalidation cost is
# core-count-independent, so if the pKVM munmap penalty is the cross-core DVM
# broadcast / dsb-ish completion wait, munmap time scales with the online-core
# count and steps up at the cluster boundary; if it is a purely local cost it
# stays flat. Run once per boot mode (protected, then nvhe) and diff.
#
# N80 topology: 8 cores, 1 socket, 2 clusters {0,1,2,3}=56 {4,5,6,7}=572,
# bench core cpu0 in cluster 56. The default SETS use the `0,1` vs `0,4` pair
# (same remote count, intra- vs cross-cluster) as the cleanest fabric probe.
#
# Usage (on the target board):  ./run-core-scaling.sh
# Env overrides: CORE SIZE ITERS FILE FREQ BENCH SETS POINTS OUTDIR
set -u

DIR=$(cd "$(dirname "$0")" && pwd)
CORE=${CORE:-0}
SIZE=${SIZE:-64}
ITERS=${ITERS:-100}
FILE=${FILE:-/tmp/munmap-corescaling-backing.bin}
FREQ=${FREQ:-1800000}                       # locked freq (kHz); N80 = 1.8 GHz
NCPU=$(nproc --all)
MODE=$(grep -o 'kvm-arm.mode=[a-z]*' /proc/cmdline | cut -d= -f2); MODE=${MODE:-vhe}
OUTDIR=${OUTDIR:-$DIR/results/corescaling-$MODE}

# cpu0 always online. cluster-aware sets; 0,1 vs 0,4 isolate intra- vs cross-cluster.
SETS=${SETS:-"0 0,1 0,4 0,1,2,3 0,1,2,3,4 0,1,2,3,4,5,6,7"}
# fixed per-page points "touch_mb:stride_kb" (both stay below the 2MB full-flush
# threshold, so munmap takes the per-page TLBI / broadcast-heavy path).
POINTS=${POINTS:-"1.0:4 6.4:16"}

# --- locate or build the benchmark ---
if   [ -n "${BENCH:-}" ] && [ -x "${BENCH:-}" ]; then :
elif [ -x "$DIR/munmap_only" ]; then BENCH="$DIR/munmap_only"
elif [ -x /tmp/munmap_only ];   then BENCH=/tmp/munmap_only
elif [ -f "$DIR/munmap_only.c" ]; then gcc -O2 -o "$DIR/munmap_only" "$DIR/munmap_only.c" && BENCH="$DIR/munmap_only"
else echo "FATAL: no munmap_only binary or source found near $DIR" >&2; exit 1
fi

relock() {  # re-lock governor+freq on ALL online cpus: a hotplug-onlined core
            # returns at the default governor, which would silently change freq.
  for g in /sys/devices/system/cpu/cpu*/cpufreq; do
    echo performance | sudo tee "$g/scaling_governor" >/dev/null 2>&1
    echo "$FREQ"      | sudo tee "$g/scaling_max_freq" >/dev/null 2>&1
    echo "$FREQ"      | sudo tee "$g/scaling_min_freq" >/dev/null 2>&1
  done
}
cluster_of() { cat "/sys/devices/system/cpu/cpu$1/topology/cluster_id" 2>/dev/null; }

# --- env controls (THP/ASLR; freq locked per-iteration via relock) ---
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled >/dev/null 2>&1
echo 0     | sudo tee /proc/sys/kernel/randomize_va_space          >/dev/null 2>&1
dd if=/dev/zero of="$FILE" bs=1M count="$SIZE" status=none
mkdir -p "$OUTDIR"
CSV="$OUTDIR/corescaling-$MODE.csv"

echo "# mode=$MODE size=${SIZE}MB iters=$ITERS bench=$BENCH freq=${FREQ}kHz" | tee "$CSV"
echo "set,n_online,clusters,touch_mb,stride_kb,munmap_mean_us,munmap_min_us" | tee -a "$CSV"

for cpuset in $SETS; do
  want=",$cpuset,"
  for c in $(seq 1 $((NCPU-1))); do
    f="/sys/devices/system/cpu/cpu$c/online"; [ -e "$f" ] || continue
    if [[ "$want" == *",$c,"* ]]; then echo 1 | sudo tee "$f" >/dev/null 2>&1
    else                                 echo 0 | sudo tee "$f" >/dev/null 2>&1; fi
  done
  relock
  sleep 1
  n=$(nproc)
  clusters=$(for c in $(echo "$cpuset" | tr ',' ' '); do cluster_of "$c"; done | sort -un | tr '\n' '/' | sed 's:/$::')
  for p in $POINTS; do
    tm=${p%:*}; st=${p#*:}
    out=$(taskset -c "$CORE" "$BENCH" file "$SIZE" "$ITERS" "$FILE" "$tm" "$st")
    mean=$(echo "$out" | grep -o 'mean=[0-9.]*' | cut -d= -f2)
    min=$(echo "$out"  | grep -o 'min=[0-9.]*'  | cut -d= -f2)
    echo "$cpuset,$n,$clusters,$tm,$st,$mean,$min" | tee -a "$CSV"
  done
done

# restore all cores online + re-lock
for c in $(seq 1 $((NCPU-1))); do echo 1 | sudo tee "/sys/devices/system/cpu/cpu$c/online" >/dev/null 2>&1; done
relock
rm -f "$FILE"
echo "# done. all cores restored online. CSV: $CSV" >&2
