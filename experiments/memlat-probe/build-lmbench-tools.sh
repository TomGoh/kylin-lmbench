#!/bin/sh
# Build lmbench's own lat_mem_rd and bw_mem from ../../src without the rest of
# the suite (no RPC, no network tests).  The sources are used unmodified.
#   sh build-lmbench-tools.sh [source dir]      # default ../../src
# lib_sched.c is compiled without HAVE_SCHED_SETAFFINITY: with LMBENCH_SCHED
# unset or DEFAULT it does nothing either way, and newer compilers reject the
# pointer type it passes to sched_setaffinity().
SRC=${1:-$(dirname "$0")/../../src}
FLAGS="-O -D_GNU_SOURCE -include stdint.h -DNO_RPC -DRUSAGE -DHAVE_uint=1 -DHAVE_int64_t=1 -DHAVE_uint64_t=1 -DHAVE_socklen_t -DHAVE_off64_t -DHAVE_DRAND48"
LIB="$SRC/lib_timing.c $SRC/lib_mem.c $SRC/lib_stats.c $SRC/lib_debug.c $SRC/getopt.c $SRC/lib_sched.c"
for t in lat_mem_rd bw_mem; do
  ${CC:-gcc} $FLAGS -w -I"$SRC" -o $t "$SRC/$t.c" $LIB -lm || exit 1
done
echo "built: lat_mem_rd bw_mem ($(${CC:-gcc} --version | head -1))"
