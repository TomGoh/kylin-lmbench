#!/usr/bin/env bash
# Build a full-featured perf matching the running kernel, from that kernel's tools/perf,
# on a Kylin V10 / Phytium board (developed on Kaitian, FTC862, kernel 6.6.30-pkvm-clean).
#
# Run this ON THE BOARD. Assumes the kernel source ("common") is already cloned and
# passwordless sudo is available. See build-perf-on-kaitian.md for the why behind each step.
#
# Usage:  ./build-perf-on-kaitian.sh [COMMON_DIR]
#   COMMON_DIR defaults to ~/common
set -euo pipefail

COMMON="${1:-$HOME/common}"
DEPS="$HOME/perf-deps"
SHIM="$DEPS/btfinc"
ARCHLIB="/usr/lib/$(gcc -dumpmachine)"          # e.g. /usr/lib/aarch64-linux-gnu
LTE_TAG="libtraceevent-1.8.7"                   # pinned release (not moving HEAD)
J="$(nproc)"

[ -f "$COMMON/tools/perf/Makefile.perf" ] || { echo "ERROR: no tools/perf under $COMMON"; exit 1; }

echo "== 0. perf-counter access =="
sudo sysctl -w kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0 >/dev/null

echo "== 1. build dependencies =="
sudo apt-get install -y \
  flex bison pkg-config zlib1g-dev libelf-dev libdw-dev libunwind-dev \
  libcap-dev libzstd-dev liblzma-dev \
  python3-dev libperl-dev libslang2-dev systemtap-sdt-dev libnuma-dev \
  libbabeltrace-dev binutils-dev libpfm4-dev libssl-dev libaio-dev libiberty-dev

echo "== 2. libtraceevent / libtracefs =="
if pkg-config --exists libtraceevent 2>/dev/null; then
  echo "   libtraceevent already present ($(pkg-config --modversion libtraceevent)) — skipping build"
else
  mkdir -p "$SHIM/linux" "$DEPS"

  # 2a. modern btf.h shim, only if the distro header lacks the new BTF kinds
  if ! grep -q BTF_KIND_ENUM64 /usr/include/linux/btf.h 2>/dev/null; then
    for src in "$COMMON/include/uapi/linux/btf.h" "$COMMON/tools/include/uapi/linux/btf.h"; do
      if grep -q BTF_KIND_ENUM64 "$src" 2>/dev/null; then cp "$src" "$SHIM/linux/btf.h"; break; fi
    done
    SHIMFLAG="-I$SHIM"; echo "   using modern btf.h shim"
  else
    SHIMFLAG=""; echo "   distro btf.h is new enough — no shim"
  fi

  # GNU make < 4.3 mis-parses '#' inside $(shell); detect once.
  MAKE_NEEDS_HASH_FIX=0
  case "$(make --version | head -1)" in
    *" 4.0"*|*" 4.1"*|*" 4.2"*) MAKE_NEEDS_HASH_FIX=1 ;;
  esac

  # 2b. libtraceevent (pinned)
  cd "$DEPS"; [ -d libtraceevent ] || git clone --depth 1 --branch "$LTE_TAG" \
    https://git.kernel.org/pub/scm/libs/libtrace/libtraceevent.git
  cd libtraceevent
  [ "$MAKE_NEEDS_HASH_FIX" = 1 ] && sed -i 's/$${f#tep_}/$${f\#tep_}/' scripts/utils.mk || true
  make -j"$J" EXTRA_CFLAGS="$SHIMFLAG"
  sudo make install prefix=/usr libdir="$ARCHLIB" EXTRA_CFLAGS="$SHIMFLAG"

  # 2c. libtracefs (optional: perf ftrace)
  cd "$DEPS"; [ -d libtracefs ] || git clone --depth 1 \
    https://git.kernel.org/pub/scm/libs/libtrace/libtracefs.git
  cd libtracefs
  make -j"$J" EXTRA_CFLAGS="$SHIMFLAG" || echo "   libtracefs build failed (non-fatal)"
  sudo make install prefix=/usr libdir="$ARCHLIB" EXTRA_CFLAGS="$SHIMFLAG" || true
  sudo ldconfig
fi

echo "== 3. build perf (fresh feature detection) =="
cd "$COMMON/tools/perf"
make clean >/dev/null 2>&1 || true
rm -f FEATURE-DUMP                                # survives 'make clean'; caches stale "absent"
make -j"$J" WERROR=0 PYTHON=python3

echo "== 4. install on PATH =="
sudo ln -sf "$COMMON/tools/perf/perf" /usr/local/bin/perf

echo "== done =="
perf version
perf version --build-options | grep -E '\[ on|libtraceevent|dwarf|libpython|libpfm4'
echo "--- smoke ---"
perf stat -e cycles,instructions,r0024 -- sleep 0.2 || true
echo "--- :h (EL2) accepted? ---"
perf stat -e cycles:k,cycles:h -- sleep 0.2 || true
