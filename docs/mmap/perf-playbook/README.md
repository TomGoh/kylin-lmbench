# Perf-only pKVM mmap re-investigation

A **zero-kernel-patch, perf-only** redo of the pKVM `lat_mmap` investigation, runnable on any
installed pKVM board. Replaces the original's two custom hypervisor hypercalls with stock `perf`
(`:h` EL2 modifier; TLB-walk/stall counters). First target: **Kaitian** (Phytium FTC862).

## Contents

1. **[perf-only-mmap-investigation-playbook.md](perf-only-mmap-investigation-playbook.md)** —
   the design spec: goal, environment controls, Stage 0–6 perf-event mapping, decision tree,
   fallbacks, status. **Start here.**

2. **[build-perf-on-kaitian.md](build-perf-on-kaitian.md)** — fully reproducible runbook for
   compiling a *matched, full-featured* `perf` from `common/tools/perf` on Kaitian, including the
   five traps we hit (old btf.h, GNU make 4.2.1 `#`-bug, unpackaged libtraceevent, install-path,
   stale FEATURE-DUMP) and exact package versions.

3. **[build-perf-on-kaitian.sh](build-perf-on-kaitian.sh)** — the runbook as an idempotent script
   (probes for each trap, so it also works on boards that don't hit them).

## Why

The original deep investigation ([../pkvm-mmap-overview.zh-CN.md](../pkvm-mmap-overview.zh-CN.md))
needed a patched hypervisor for two of its five stages. A stock board can't be patched — so this
playbook proves (or disproves) the same root cause using only perf, which is what makes it a
reusable procedure rather than a one-off.

## Status (2026-06-24)

Design approved; **perf built & validated on Kaitian**; investigation stages pending.
