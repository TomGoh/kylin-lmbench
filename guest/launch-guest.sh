#!/usr/bin/env bash
# Launch a guest VM under crosvm, reusing the host kernel + a pre-built
# rootfs image. Defaults match our EXPERIMENT.md choices: 2 vCPUs pinned
# to two little cores in the same cluster, 4 GiB RAM, virtio-blk root,
# no balloon/rng/pmu/usb noise, console on stdin/stdout.
#
# Modes (one of):
#   (default)                   non-protected guest under whatever host mode
#   --protected                 protected guest via pvmfw (requires --bios)
#   --protected-no-fw           protected without pvmfw (EXPERIMENTAL; crosvm
#                               --protected-vm-without-firmware)
#
# Knobs (env vars):
#   CROSVM      path to crosvm binary           (default: ~/pvm/crosvm)
#   KERNEL      path to vmlinuz                 (default: /boot/vmlinuz)
#   ROOTFS      path to rwroot image            (default: ~/pvm/rootfs.img)
#   BIOS        path to pvmfw.bin (--protected) (default: ~/pvm/pvmfw.bin)
#   CORES       host cores to pin to            (default: 0,1)
#   CPUS        number of vCPUs                 (default: 2)
#   MEM_MIB     guest RAM in MiB                (default: 4096)
#   EXTRA_PARAMS  extra kernel cmdline args     (default: empty)
set -euo pipefail

CROSVM="${CROSVM:-$HOME/pvm/crosvm}"
KERNEL="${KERNEL:-/boot/vmlinuz}"
ROOTFS="${ROOTFS:-$HOME/pvm/rootfs.img}"
BIOS="${BIOS:-$HOME/pvm/pvmfw.bin}"
CORES="${CORES:-0,1}"
CPUS="${CPUS:-2}"
MEM_MIB="${MEM_MIB:-4096}"
EXTRA_PARAMS="${EXTRA_PARAMS:-}"

PROT_MODE="none"
for arg in "$@"; do
  case "$arg" in
    --protected)        PROT_MODE="pvmfw" ;;
    --protected-no-fw)  PROT_MODE="nofw"  ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

[ -x "$CROSVM" ] || { echo "crosvm not executable: $CROSVM" >&2; exit 1; }
[ -f "$KERNEL" ] || { echo "kernel not found: $KERNEL" >&2; exit 1; }
[ -f "$ROOTFS" ] || { echo "rootfs not found: $ROOTFS — run mkrootfs.sh first" >&2; exit 1; }
if [ "$PROT_MODE" = "pvmfw" ]; then
  [ -f "$BIOS" ] || { echo "pvmfw not found: $BIOS" >&2; exit 1; }
fi

# Guest kernel cmdline — field-by-field aligned with the host /proc/cmdline.
# Only differences from host: no kvm-arm.mode= (irrelevant to guest), no
# BOOT_IMAGE/ostree/UUID/resume (different boot path), no splash (no console
# graphics).  THP/ASLR explicitly disabled in addition to bench-in-guest.sh's
# runtime sysfs writes, for boot-time consistency.
PARAMS="console=ttyAMA0 root=/dev/vda rw"
PARAMS="$PARAMS transparent_hugepage=never randomize_va_space=0"
PARAMS="$PARAMS no_console_suspend"
# --- LSM / audit stack identical to host ---
PARAMS="$PARAMS security=box lsm=ksaf audit=1"
# --- scheduler / cgroup hooks (host has psi=1 and v2 unified hierarchy) ---
PARAMS="$PARAMS psi=1 systemd.unified_cgroup_hierarchy=1"
# --- quieter boot to match host's quiet loglevel=0 ---
PARAMS="$PARAMS quiet loglevel=0"
[ -n "$EXTRA_PARAMS" ] && PARAMS="$PARAMS $EXTRA_PARAMS"

# Build crosvm argv as an array — quoting matters for params with spaces.
# --disable-sandbox: skip minijail, run all virtio devices in one process.
#   Required because crosvm needs /var/empty to chroot into otherwise; and
#   for benchmarking we want fewer host-side worker threads = less noise.
# --block path=...,root=true: modern equivalent of --rwroot (rwroot is dprctd).
ARGS=(
  run
  --disable-sandbox
  -c "num-cores=${CPUS}"
  -m "size=${MEM_MIB}"
  --no-balloon --no-rng --no-pmu --no-usb
  --serial "type=stdout,hardware=serial,console=true,stdin=true,earlycon=true"
  --block "path=${ROOTFS},root=true"
  -p "$PARAMS"
)

case "$PROT_MODE" in
  pvmfw) ARGS+=( --protected-vm --bios "$BIOS" ) ;;
  nofw)  ARGS+=( --protected-vm-without-firmware ) ;;
esac

ARGS+=( "$KERNEL" )

echo "[launch-guest] taskset -c $CORES $CROSVM ${ARGS[*]}" >&2
exec taskset -c "$CORES" "$CROSVM" "${ARGS[@]}"
