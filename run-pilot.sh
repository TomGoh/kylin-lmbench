#!/usr/bin/env bash
# Pilot benchmark driver for KVM/pKVM overhead study.
# All lmbench tools write results to STDERR; we redirect 2>&1 >/dev/null
# so result lines flow into pipelines while real stdout is discarded.
# CSV columns: env,core,bench,variant,iter,value,unit
set -u

ENV_TAG="${ENV_TAG:-pkvm-host}"
CORE="${CORE:-0}"
ITERS="${ITERS:-10}"
LMB="$HOME/lmbench-3.0-a9/bin/aarch64-Linux"

# ---- setup: fixed paths lat_proc/lat_sig/etc require ----
cp -f "$LMB/hello" /tmp/hello 2>/dev/null || true
cp -f "$LMB/hello-s" /tmp/hello-s 2>/dev/null || true
STATFILE=/tmp/lmb_stat;  : > "$STATFILE"
PROTFILE=/tmp/lmb_prot;  : > "$PROTFILE"; printf 'x%.0s' {1..4096} > "$PROTFILE"
MMAPFILE=/tmp/lmb_mmap;  dd if=/dev/zero of="$MMAPFILE" bs=1M count=128 status=none
PFFILE=/tmp/lmb_pfile;   dd if=/dev/zero of="$PFFILE"   bs=1M count=128 status=none

emit() { printf '%s,%s,%s,%s,%d,%s,%s\n' "$ENV_TAG" "$CORE" "$1" "$2" "$3" "$4" "$5"; }
pin()  { taskset -c "$CORE" "$@"; }

# Robust: scan every line containing "microseconds", keep the LAST numeric value.
val_us() {
  awk '/microseconds/{
         for(i=1;i<=NF;i++) if($i=="microseconds"){v=$(i-1)}
       } END{ print v }'
}

run_iter() {
  local i=$1

  # syscalls (stat/open need a file)
  emit lat_syscall null  $i "$(pin "$LMB/lat_syscall" null            2>&1 >/dev/null | val_us)" us
  emit lat_syscall read  $i "$(pin "$LMB/lat_syscall" read            2>&1 >/dev/null | val_us)" us
  emit lat_syscall write $i "$(pin "$LMB/lat_syscall" write           2>&1 >/dev/null | val_us)" us
  emit lat_syscall stat  $i "$(pin "$LMB/lat_syscall" stat $STATFILE  2>&1 >/dev/null | val_us)" us
  emit lat_syscall open  $i "$(pin "$LMB/lat_syscall" open $STATFILE  2>&1 >/dev/null | val_us)" us

  # context switch: -s <KB> <nproc...>; per-nproc line is "<n> <us>"
  for size in 0 16; do
    pin "$LMB/lat_ctx" -s $size 2 8 16 2>&1 >/dev/null \
      | awk -v env="$ENV_TAG" -v core="$CORE" -v iter="$i" -v sz="$size" \
            '$1 ~ /^[0-9]+$/ && NF==2 {
               printf "%s,%s,lat_ctx,sz%sK_p%s,%d,%s,us\n",env,core,sz,$1,iter,$2
             }'
  done

  emit lat_pipe rt $i "$(pin "$LMB/lat_pipe" 2>&1 >/dev/null | val_us)" us
  emit lat_unix rt $i "$(pin "$LMB/lat_unix" 2>&1 >/dev/null | val_us)" us

  emit lat_sig install $i "$(pin "$LMB/lat_sig" install            2>&1 >/dev/null | val_us)" us
  emit lat_sig catch   $i "$(pin "$LMB/lat_sig" catch              2>&1 >/dev/null | val_us)" us
  emit lat_sig prot    $i "$(pin "$LMB/lat_sig" prot $PROTFILE     2>&1 >/dev/null | val_us)" us

  emit lat_pagefault minor $i "$(pin "$LMB/lat_pagefault" $PFFILE 2>&1 >/dev/null | val_us)" us
  emit lat_mmap      64M   $i "$(pin "$LMB/lat_mmap" 64M $MMAPFILE 2>&1 >/dev/null \
                                  | awk 'NF==2 && $1+0>0{v=$2} END{print v}')" us

  emit lat_proc fork  $i "$(pin "$LMB/lat_proc" fork  2>&1 >/dev/null | val_us)" us
  emit lat_proc exec  $i "$(pin "$LMB/lat_proc" exec  2>&1 >/dev/null | val_us)" us
  emit lat_proc shell $i "$(pin "$LMB/lat_proc" shell 2>&1 >/dev/null | val_us)" us

  # memory latency curve (size_MB, ns) -- keep every point; filter in analysis
  pin "$LMB/lat_mem_rd" -P 1 64 128 2>&1 >/dev/null \
    | awk -v env="$ENV_TAG" -v core="$CORE" -v iter="$i" \
          'NF==2 && $1+0>0 {printf "%s,%s,lat_mem_rd,sz%sMB,%d,%s,ns\n",env,core,$1,iter,$2}'

  emit bw_mem rd_64M $i "$(pin "$LMB/bw_mem" 64m rd 2>&1 >/dev/null \
                            | awk 'NF==2{v=$2} END{print v}')" MB/s
}

echo "env,core,bench,variant,iter,value,unit"
for i in $(seq 1 "$ITERS"); do
  echo "  [iter $i/$ITERS on cpu$CORE env=$ENV_TAG]" >&2
  run_iter "$i"
done
