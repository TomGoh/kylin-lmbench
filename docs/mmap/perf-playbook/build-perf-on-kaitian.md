# Building a matched `perf` from the `common` kernel source on Kaitian

| | |
|---|---|
| Date | 2026-06-24 |
| Board | Kaitian (`ssh Kaitian` → 10.42.27.22), user `test`, home `/home/test` |
| Distro | Kylin V10 SP1 (Kylin-Desktop V10-SP1), gcc 9.3.0, **GNU Make 4.2.1** |
| Kernel | `6.6.30-pkvm-clean`, booted `kvm-arm.mode=protected` |
| CPU | Phytium **FTC862** (implementer `0x70`, part `0x862`), 8 cores — *same core as N80* |
| Goal | A **full-featured** `perf` that exactly matches the running 6.6.30 kernel, built from the kernel's own `tools/perf`, **without modifying the `common` source** |
| Result | `perf 6.6.30.gda966ce9a047` at `/usr/local/bin/perf`; all features on except `libbfd` (license-default-off) and `debuginfod` |

> **Why build from source instead of `apt install`?** The Kylin repo only ships `perf`
> for its own distro kernel (5.4.18). The running kernel is 6.6.30. `perf stat` counting
> rides the stable `perf_event_open` ABI and would *mostly* work cross-version, but the
> symbolic event tables, the `:h` (EL2) exception-level modifier, and raw-event encodings
> are tied to the perf **build**. The perf-only pKVM mmap playbook leans on exactly those,
> so we build perf from *this* kernel's `tools/perf`.

> **"Without modifying `common`"** is preserved: we build inside the board's *clone* of
> `common` (`/home/test/common`); the dev-box `common` is never touched. The build only
> writes object files into that clone's `tools/perf/` tree.

---

## TL;DR — the clean procedure

If you just want to redo it, run [`build-perf-on-kaitian.sh`](build-perf-on-kaitian.sh) on the
board, or follow these steps (each is explained in detail below). Assumes `common` is already
cloned at `/home/test/common` and the board has passwordless `sudo`.

```bash
# 0. perf-counter access
sudo sysctl -w kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0

# 1. build dependencies (Kylin repo)
sudo apt-get install -y \
  flex bison pkg-config zlib1g-dev libelf-dev libdw-dev libunwind-dev \
  libcap-dev libzstd-dev liblzma-dev \
  python3-dev libperl-dev libslang2-dev systemtap-sdt-dev libnuma-dev \
  libbabeltrace-dev binutils-dev libpfm4-dev libssl-dev libaio-dev libiberty-dev

# 2. libtraceevent + libtracefs are NOT packaged and were removed from the kernel
#    tree in v6.2 -> build them from kernel.org, into a standard prefix.
mkdir -p ~/perf-deps && cd ~/perf-deps
#    2a. modern btf.h shim (distro btf.h is 5.4-era; libtraceevent needs >=6.0 BTF kinds)
mkdir -p ~/perf-deps/btfinc/linux
cp /home/test/common/include/uapi/linux/btf.h ~/perf-deps/btfinc/linux/btf.h
SHIM=-I/home/test/perf-deps/btfinc
#    2b. libtraceevent, pinned to a release (NOT moving HEAD)
git clone --depth 1 --branch libtraceevent-1.8.7 \
  https://git.kernel.org/pub/scm/libs/libtrace/libtraceevent.git
cd libtraceevent
sed -i 's/$${f#tep_}/$${f\#tep_}/' scripts/utils.mk      # GNU make 4.2.1 '#'-in-$(shell) fix
make -j"$(nproc)" EXTRA_CFLAGS="$SHIM"
sudo make install prefix=/usr libdir=/usr/lib/aarch64-linux-gnu EXTRA_CFLAGS="$SHIM"
#    2c. libtracefs (perf ftrace)
cd ~/perf-deps && git clone --depth 1 https://git.kernel.org/pub/scm/libs/libtrace/libtracefs.git
cd libtracefs
make -j"$(nproc)" EXTRA_CFLAGS="$SHIM"
sudo make install prefix=/usr libdir=/usr/lib/aarch64-linux-gnu EXTRA_CFLAGS="$SHIM"
sudo ldconfig

# 3. build perf (fresh feature detection!)
cd /home/test/common/tools/perf
make clean >/dev/null 2>&1; rm -f FEATURE-DUMP     # FEATURE-DUMP survives clean and caches stale "absent"
make -j"$(nproc)" WERROR=0 PYTHON=python3

# 4. put it on PATH
sudo ln -sf /home/test/common/tools/perf/perf /usr/local/bin/perf
perf version --build-options
```

---

## Why each non-obvious step is there (the four traps we hit)

The clean procedure above already encodes the fixes. This section records the *failures* that
forced each one, so a future redo on a different board recognises the symptom and knows the cause.

### Trap 1 — `jevents`/python and `python3-config`
First build died at:
```
Makefile.config:881: *** ERROR: No python interpreter needed for jevents generation.
```
then, after pointing it at python3, at:
```
Makefile.config:285: *** /usr/bin/python3-config not found.
```
`jevents` (the PMU-event-JSON → C generator) needs a Python interpreter, and perl/python
*scripting* support needs the `-config` helpers. **Fix:** install `python3-dev` (provides
`python3-config`) and pass `PYTHON=python3` (perf's auto-detect didn't find it on this board).
For a *full* perf we also install `libperl-dev`, `libslang2-dev`, `systemtap-sdt-dev`,
`libnuma-dev`, `libbabeltrace-dev`, `binutils-dev`, `libpfm4-dev`, `libssl-dev`, `libaio-dev`,
`libiberty-dev` — each lights up one feature in `perf version --build-options`.

### Trap 2 — `libtraceevent` is mandatory but unpackaged
```
Makefile.config:1144: *** ERROR: libtraceevent is missing.
```
6.6 perf treats **libtraceevent as a hard requirement** (it parses tracepoint formats for
`perf trace`/`sched`/`lock`/`kmem` and tracepoint events). The Kylin repo has **no
`libtraceevent-dev`**, and the in-tree `tools/lib/traceevent` was **removed from the kernel in
v6.2**. **Fix:** build libtraceevent (and libtracefs, for `perf ftrace`) from kernel.org.
Kaitian can reach `git.kernel.org` directly, so we clone on the board.

### Trap 3 — distro `btf.h` is too old for modern libtraceevent
```
trace-btf.c:70:3: error: 'BTF_KIND_FLOAT' undeclared
                  ('BTF_KIND_DECL_TAG', 'BTF_KIND_TYPE_TAG', 'BTF_KIND_ENUM64' too)
```
libtraceevent's `trace-btf.c` references BTF kinds added to the kernel in 5.13–6.0, but the
board's `/usr/include/linux/btf.h` is **5.4-era** (Kylin's userspace headers). **Fix:** shim
*just that one header* from the 6.6 source we already have:
`cp common/include/uapi/linux/btf.h ~/perf-deps/btfinc/linux/btf.h` and build with
`EXTRA_CFLAGS=-I~/perf-deps/btfinc`. Because the shim dir contains only `linux/btf.h`,
`<linux/btf.h>` resolves to the 6.6 version while every other `<linux/*>` still comes from the
distro — a one-header override, no system-header surgery.

### Trap 4 — GNU Make 4.2.1 `#`-in-`$(shell)` comment bug
```
scripts/utils.mk:187: *** unterminated call to function 'shell': missing ')'.
```
`utils.mk` has `$(shell ... [ "$${f#tep_}" = "$$f" ] ... )`. **GNU Make < 4.3 treats the `#`
inside a `$(shell ...)` as a comment**, swallowing the closing `)`. Make 4.3 fixed exactly this.
Kaitian has Make 4.2.1. **Fix (no second `make` needed):** escape the `#` as `\#` — make passes
a literal `#` through to the shell:
`sed -i 's/$${f#tep_}/$${f\#tep_}/' scripts/utils.mk`.
We also **pin libtraceevent to release 1.8.7** rather than the moving HEAD (1.9.0-dev had an
additional static-lib Makefile regression, and a playbook should build against a fixed version).

### Trap 5 — install location and perf's stale feature cache
After installing libtraceevent to the default `/usr/local/lib64`, perf *still* reported it
missing. Two compounding causes:
1. **`/usr/local/lib64` is not in the default linker search path**, so perf's feature-check
   *link* of `test-libtraceevent.c` failed even though `pkg-config` could see the `.pc`.
   **Fix:** install to a **standard prefix** — `make install prefix=/usr
   libdir=/usr/lib/aarch64-linux-gnu` — so the `.so` lands in `/usr/lib/aarch64-linux-gnu`
   (a default linker path) and headers in `/usr/include/traceevent`. Then perf needs **no**
   `PKG_CONFIG_PATH` or `-L` at all.
2. **perf's `FEATURE-DUMP` cache survives `make clean`** and had recorded
   `feature-libtraceevent=0` from the pre-install build. **Fix:** `rm -f FEATURE-DUMP` before
   rebuilding whenever you add a dependency mid-stream.

---

## Exact environment & versions (this build)

- `common` HEAD: `da966ce9a047bedffb02e0bdc87f3ccb5fb3f9d9`
- perf: `perf version 6.6.30.gda966ce9a047`, symlink `/usr/local/bin/perf` → `/home/test/common/tools/perf/perf`
- libtraceevent **1.8.7** (pinned tag), libtracefs **1.8.3** (HEAD at build time)
- `.so` in `/usr/lib/aarch64-linux-gnu` (+ leftover copies in `/usr/local/lib64` from the first
  attempt — harmless; `sudo rm /usr/local/lib64/libtrace*` to tidy)
- `.pc` discoverable by default `pkg-config` (`/usr/local/lib/aarch64-linux-gnu/pkgconfig/`)

Dev packages installed from the Kylin repo (`archive.kylinos.cn`, `10.1-kylin`):
```
flex=2.6.4-6.2  bison=2:3.5.1+dfsg-1  pkg-config=0.29.1-1kylin4
zlib1g-dev=1:1.2.11.dfsg-2kylin1.5k0.2  libelf-dev=0.176-1.1kylin0.1  libdw-dev=0.176-1.1kylin0.1
libunwind-dev=1.2.1-9build1k4  libcap-dev=1:2.32-1kylin0.2  libzstd-dev=1.4.4+dfsg-3kylin0.1
liblzma-dev=5.2.4-1kylin2.1  python3-dev=3.8.2-0kylin2  libpython3-dev=3.8.2-0kylin2
libperl-dev=5.30.0-9kylin0.5k0.3  libslang2-dev=2.3.2-4  systemtap-sdt-dev=4.2-3
libnuma-dev=2.0.12-1  libbabeltrace-dev=1.5.8-1build1kylin0  binutils-dev=2.34-6kylin1.11
libpfm4-dev=4.10.1+git20-g7700f49-2  libssl-dev=1.1.1f-1kylin2.23k0.6  libaio-dev=0.3.112-5kylin0k1
libiberty-dev=20200409-1kylin0k1
```

## Validation (Stage-0 capability probe)

```
$ perf version --build-options    # all on EXCEPT libbfd (license default), debuginfod
   dwarf, libelf, libnuma, libperl, libpython, libslang, libcrypto, libunwind,
   bpf, aio, zstd, libpfm4, libtraceevent : [ on ]

$ perf stat -e cycles,instructions -- sleep 0.2      # counting works
$ perf stat -e cycles:u,cycles:k,cycles:h -- sleep 0.2
   cycles:u=259,939   cycles:k=690,240   cycles:h=0    # :h (EL2) ACCEPTED, 0 during sleep (correct)
$ perf stat -e r0024 -- sleep 0.2                     # raw STALL_BACKEND works (362k)
```

Event-name notes for FTC862 (use in the playbook):
- present by name: `stall_backend`, `stall_frontend`, `l1d_tlb`, `l2d_tlb_refill`, `mem_access`
- **not** named: `dtlb_walk` → use the architected raw code **`r0034`**

The `:h` modifier being **accepted** (not `<not supported>`) is the key result: it means the
perf-native EL2 attribution (playbook Stage 3) is viable *without a custom hypercall*. Still to
confirm: that `cycles:h` goes **non-zero** under a known-EL2 workload (faulting fresh pages →
host stage-2 abort), which distinguishes "EL2 counting works" from "pKVM silently zeroes it."

## Re-applying after a kernel rebuild / on another board

- The perf binary is tied to the `common` checkout it was built from; rebuild it if `common`
  changes materially. `perf_event_paranoid`/`kptr_restrict` reset on reboot — re-apply (or
  persist via `/etc/sysctl.d/`).
- On a board with **GNU Make ≥ 4.3**, skip the Trap-4 `sed`. On one with **`libtraceevent-dev`
  packaged**, skip the whole §2. On one with **modern userspace headers**, skip the Trap-3 shim.
  The script probes for these.
