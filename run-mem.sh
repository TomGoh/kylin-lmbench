#!/usr/bin/env bash
# Supplemental: just the memory-latency curve, multiple strides.
# Append-only — produces additional rows in the same CSV schema.
set -u
ENV_TAG="${ENV_TAG:-pkvm-host}"
CORE="${CORE:-0}"
ITERS="${ITERS:-10}"
LMB="$HOME/lmbench-3.0-a9/bin/aarch64-Linux"
pin() { taskset -c "$CORE" "$@"; }

# Header omitted: this output is appended to an existing CSV.
for i in $(seq 1 "$ITERS"); do
  echo "  [mem iter $i/$ITERS cpu$CORE env=$ENV_TAG]" >&2

  # stride 128: cache-hierarchy curve (prefetcher helps -> optimistic DRAM)
  pin "$LMB/lat_mem_rd" -P 1 64 128 2>&1 >/dev/null \
    | awk -v env="$ENV_TAG" -v core="$CORE" -v iter="$i" \
          'NF==2 && $1+0>0 {printf "%s,%s,lat_mem_rd_s128,sz%sMB,%d,%s,ns\n",env,core,$1,iter,$2}'

  # stride 4096: defeats next-line prefetcher; still TLB-friendly
  pin "$LMB/lat_mem_rd" -P 1 64 4096 2>&1 >/dev/null \
    | awk -v env="$ENV_TAG" -v core="$CORE" -v iter="$i" \
          'NF==2 && $1+0>0 {printf "%s,%s,lat_mem_rd_s4k,sz%sMB,%d,%s,ns\n",env,core,$1,iter,$2}'

  # stride 4096 + thrash: randomized within stride, defeats stride detectors
  # This is our authoritative DRAM-latency measurement.
  pin "$LMB/lat_mem_rd" -t -P 1 64 4096 2>&1 >/dev/null \
    | awk -v env="$ENV_TAG" -v core="$CORE" -v iter="$i" \
          'NF==2 && $1+0>0 {printf "%s,%s,lat_mem_rd_s4k_t,sz%sMB,%d,%s,ns\n",env,core,$1,iter,$2}'
done
