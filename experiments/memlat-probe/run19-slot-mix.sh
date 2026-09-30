#!/bin/sh
# Exp N2: probe3's translation-only chase as root, so that the line also says
# in which 1 GiB physical slots the pages of the buffer lie (slots=).  Fresh
# process per run; a small hold-back allocation of varying size in front of
# each run makes the kernel hand out different frames from run to run.
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 3 minutes.
cd "$(dirname "$0")" || exit 1
E=11,2d,17
echo "# run19 start $(date -Is) uid=$(id -u)" >> meta.log
: > expN2.log
for rep in 1 2 3 4 5 6 7 8 9 10 11 12; do
  for cfg in "16 1" "8 1" "4 4"; do
    set -- $cfg
    echo "N2 rep=$rep $(taskset -c 0 ./probe3 tlb $1 $2 64 $E 1 $rep 2>/dev/null)" >> expN2.log
  done
done
echo "# run19 done $(date -Is)" >> meta.log
