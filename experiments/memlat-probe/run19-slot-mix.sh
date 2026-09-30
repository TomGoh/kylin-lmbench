#!/bin/sh
# Exp N2: probe3's translation-only chase as root, so that the line also says
# in which 1 GiB physical slots the pages of the buffer lie (slots=).  Fresh
# process per run.  Before each repetition another process allocates a block
# of memory of growing size and is then stopped (it holds the memory and does
# nothing), so that the kernel hands the probe different frames each time.
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 3 minutes.
# Expects ./probe3 and ./bgload.
cd "$(dirname "$0")" || exit 1
E=11,2d,17
echo "# run19 start $(date -Is) uid=$(id -u)" >> meta.log
: > expN2.log
for rep in 1 2 3 4 5 6 7 8 9 10 11 12; do
  hold=$(( (rep - 1) * 192 ))
  pid=""
  if [ "$hold" -gt 0 ]; then
    taskset -c 5 ./bgload w $hold 600 > /dev/null 2>&1 &
    pid=$!
    sleep 2
    kill -STOP $pid
  fi
  for cfg in "16 1" "8 1" "4 4"; do
    set -- $cfg
    echo "N2 rep=$rep hold_mb=$hold $(taskset -c 0 ./probe3 tlb $1 $2 64 $E 1 $rep 2>/dev/null)" >> expN2.log
  done
  [ -n "$pid" ] && kill -KILL $pid
  wait 2>/dev/null
done
echo "# run19 done $(date -Is)" >> meta.log
