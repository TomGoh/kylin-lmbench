# Eliminating the KYSEC asymmetry (why guest beats host, and how to fix it)

## The problem

On KylinOS the pKVM **guest consistently benchmarks *faster* than its own
host** on syscall-class microbenchmarks (`lat_syscall null/read/write/stat/
open/fstat`, `lat_sig install`) — typically by **14–26%**. A guest sits on
*one more* layer than the host; it cannot get cheaper by adding a hypervisor.
So a "faster guest" is a methodology red flag, not a pKVM win.

Root cause (see `docs/findings-2026-06-01.md`): the **KYSEC security stack is
asymmetric** between the two sides.

| Mechanism | Host | Guest (stock) | Effect on a syscall |
|-----------|------|---------------|---------------------|
| `ksaf`/`kycp` LSM module | loaded | loaded | hook fires on both |
| `ksaf-policy-init.service` | active | **inactive** | host walks full policy; guest short-circuits |
| `auditd.service` | active | **failed** | host emits+consumes audit records |
| audit rules | ≥1 | **0** | host evaluates rules per op |
| `/sys/fs/box` | present | **absent** | host has sandbox infra |
| BPF programs | many | **0** | host runs cgroup hooks |

Net: ~84 extra cycles per syscall are charged to the **host** for KYSEC work
the **guest never does**. That, not the hypervisor, is the 14–26% delta.

The genuine pKVM cost lives in a different group — `lat_proc fork`,
`lat_sig prot` (mprotect), `lat_pipe`, `lat_unix`, `lat_pagefault minor` — at
**+2.8% to +3.5%**, where the guest *is* slower. But as long as KYSEC is
asymmetric, even that number is measured against a guest baseline that KYSEC
has already pulled ~26% faster, so it's a lower bound, not the truth.

## The fix: turn KYSEC off on BOTH sides

We want a `class=off` "pure hypervisor" baseline on host **and** guest. KYSEC's
cost comes from the **kernel-side ksaf policy + audit subsystem**, which is
gated by the boot cmdline — so this needs a cmdline edit + reboot on each side.
Stopping userspace daemons at runtime is **not** enough (the LSM policy stays
loaded in the kernel and keeps walking the long path).

The three flags to remove from the kernel cmdline are:

```
lsm=ksaf  security=box  audit=1
```

### Host

The target boots from ostree. Append a cmdline override that drops the three
flags, then reboot:

```bash
# inspect current kargs
sudo ostree admin kargs --help   # confirm subcommand exists on this build

# remove the three KYSEC flags (adjust to the exact tokens in /proc/cmdline)
sudo ostree admin kargs --delete=lsm=ksaf --delete=security=box --delete=audit=1
sudo systemctl reboot
```

If `ostree admin kargs` is unavailable on this build, edit the bootloader
entry directly (e.g. `/boot/loader/entries/*.conf` `options` line, or
`grubby --update-kernel=ALL --remove-args="lsm=ksaf security=box audit=1"`)
and reboot. Keep everything else — `kvm-arm.mode=protected`,
`transparent_hugepage=never`, `randomize_va_space=0`,
`systemd.unified_cgroup_hierarchy=1`, `psi=1` — unchanged.

### Guest

The guest cmdline is set by the VMM launch (crosvm `--params`, on the host
side, in your `/home/test/pvm/` launch script). Remove the same three tokens
from the kernel params crosvm passes, e.g.:

```
crosvm run ... \
  --params "... transparent_hugepage=never randomize_va_space=0" \
  ...
```

i.e. drop `lsm=ksaf security=box audit=1` from the `--params` string. No guest
reboot machinery is needed — just relaunch the guest with the new params.

## Verify before you trust any delta

Both sides ship `kysec-probe.sh`. Run it on each and confirm the **`class=`
token matches** (target: `off`):

```bash
# host
./kysec-probe.sh            # -> ... class=off

# guest (inside the guest)
/opt/lmbench/kysec-probe.sh # -> ... class=off
```

`bench.sh` now runs the probe automatically, records the fingerprint in
`results/<env>-<stamp>-summary.txt`, and **warns** if the class isn't what
`EXPECT_KYSEC` expects (default `off`). The guest run records its fingerprint
in `results/last-run.meta`. After scraping results back, eyeball both:

```bash
grep KYSEC_FP results/*-summary.txt results/last-run.meta
# both lines must end in class=off
```

If either side still says `class=full` or `class=partial`, the cmdline edit
didn't take — do not compare the runs.

## What you should see after the fix

With KYSEC off on both sides, the syscall-fastpath group (`lat_syscall *`,
`lat_sig install`) should **collapse to near-parity** — the 14–26% "guest is
faster" gap is gone, because the host is no longer paying for policy the guest
skips. The expected ordering returns: **guest ≥ host (guest a few % slower)**,
and the residual is the real pKVM tax. The stage-2/trap group (`fork`,
`mprotect`, `pipe`, `unix`, minor pagefault) should still show the **+3.5%**
band — now as a clean, unconfounded hypervisor cost.

If the guest is *still* faster after both sides report `class=off`, the next
suspect is **CPU frequency**: the guest's vCPU follows the host pCPU frequency,
and the guest can't lock it itself. Confirm the host was frequency-locked
(`prepare-host.sh`, `performance` governor, min==max) *while the guest ran*,
and that the guest vCPU was pinned to a core with the same locked ceiling as
the host benchmark used.

## Alternative (production-realistic) path

If you later need numbers that reflect the *shipping* security posture rather
than a pure-hypervisor baseline, do the opposite: get KYSEC to `class=full`
inside the guest (debug why `ksaf-policy-init` / `auditd` / `/dev/box` /
`kysec2-kbox-load` fail to start in the guest), so both sides run the full
stack. That is higher effort but gives the real-world host-vs-guest delta.
This file documents the fast `class=off` route chosen for first establishing
the true hypervisor overhead.
