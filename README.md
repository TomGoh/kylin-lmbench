# lmbench for KVM / pKVM overhead measurement

This is a fork of [lmbench 3.0-a9](http://www.bitmover.com/lmbench/) instrumented for
**measuring the runtime cost of running workloads under KVM and protected-KVM (pKVM)
virtualization on aarch64** — specifically targeting a Phytium D3000M host with pKVM
enabled (`kvm-arm.mode=protected` in the kernel cmdline).

Upstream lmbench is preserved unchanged in the initial git commit. All local additions
sit on top as a single feature commit, so a `git diff main~1` shows exactly what was
added.

## Dependencies

Build and runtime:

| Package | Purpose | Required? |
|---------|---------|-----------|
| `gcc`, `make` | build lmbench | yes |
| `libtirpc-dev` | Sun RPC headers (glibc ≥ 2.26 / Ubuntu 18.04+ / Debian Buster+ / RHEL 8+) | yes on modern distros; older distros (e.g. Kylin V10) still ship the headers in `/usr/include/rpc/` and don't need it — `scripts/build` auto-detects |
| `rpcbind` | RPC service registry for `lat_rpc` | yes if `BENCHMARK_RPC=YES`; `prepare-host.sh` starts it automatically |
| `python3` (≥ 3.6) | run `parse-lmbench.py` | yes |
| `net-tools` | `netstat` + `ifconfig` for the metadata dump lmbench writes at the top of every report | optional — without them you get warnings but data lines are fine |
| `taskset` (part of `util-linux`) | pin invocations to a specific CPU | yes; usually preinstalled |

Install one-liners:

```bash
# Debian / Ubuntu
sudo apt install build-essential libtirpc-dev rpcbind python3 net-tools

# RHEL / CentOS / Fedora
sudo dnf install gcc make libtirpc-devel rpcbind python3 net-tools

# Kylin V10 SP1 (our target) — legacy RPC headers already shipped,
# libtirpc-dev not required; the rest:
sudo apt install build-essential rpcbind python3 net-tools
```

If you skip `libtirpc-dev` on a glibc-2.26+ system, `make build` will fail
with `fatal error: rpc/rpc.h: No such file or directory` while compiling
`lat_rpc.c`.

## Quick start

```bash
# 1. build upstream lmbench (one-time)
make build

# 2a. host run: full suite, locked to 1.9 GHz, with prep
ENV_TAG=pkvm-host CORES=0,3 ITERS=10 ./bench.sh

# 2b. inside a KVM guest (no prep — cpufreq isn't writable from guest)
ENV_TAG=kvm-guest CORES=0,1 ITERS=10 CONFIG=configs/CONFIG.kvm-guest \
  ./bench.sh --no-prep

# 2c. inside a pKVM protected guest
ENV_TAG=pkvm-guest CORES=0,1 ITERS=10 CONFIG=configs/CONFIG.pkvm-guest \
  ./bench.sh --no-prep

# 3. results
ls results/
#   <env>-cpu<N>-iter{1..10}.txt   raw lmbench reports (stderr capture)
#   <env>-cpu<N>.csv                parsed long-format CSV
#   <env>-<timestamp>-summary.txt   run metadata (kernel, cmdline, freqs)
```

For experimental rationale (why these benchmarks, why locked 1.9 GHz, why these
cores), see [`docs/EXPERIMENT.md`](docs/EXPERIMENT.md).
For pipeline internals (how the scripts flow, how to add a new environment), see
[`docs/PIPELINE.md`](docs/PIPELINE.md).

**Final paper-grade findings**（实际跑出来的 4-config × N=10 干净对照数据 +
分析）见 [`docs/findings-2026-06-03/`](docs/findings-2026-06-03/)：
- [`SUMMARY.md`](docs/findings-2026-06-03/SUMMARY.md) ── 6 个 finding 综合
- [`lmbench-N10-4config.xlsx`](docs/findings-2026-06-03/lmbench-N10-4config.xlsx) ── 全部指标对照表
- 4 个 per-config 报告 + pkvm mmap +42% / 访问 +3-7% 专题

## Repository layout

```
bench.sh             ★ primary driver: prepare + N×lmbench + parse → CSV
prepare-host.sh        idempotent: locks CPU freq, disables THP/ASLR/deep-idle, starts rpcbind
parse-lmbench.py       state-machine parser: lmbench text report → long-format CSV
configs/
  CONFIG.template          annotated template explaining every field
  CONFIG.host              Phytium D3000M @ 1.9 GHz, full suite (incl. RPC/loopback)
  CONFIG.kvm-guest         2-vCPU 4 GB guest under QEMU/KVM (run inside guest)
  CONFIG.pkvm-guest        2-vCPU 4 GB guest under crosvm/pKVM (run inside guest)
  CONFIG.test              minimal subset for pipeline / parser validation (~90s)
docs/
  EXPERIMENT.md          why we measure what we measure
  PIPELINE.md            how the scripts work end-to-end
  PATCHES.md             what we changed in upstream lmbench
run-pilot.sh           legacy pilot (custom subset, not lmbench-driven); kept as smoke test
run-mem.sh             companion to run-pilot.sh: multi-stride memory latency
bench-host.sh          older orchestrator from the pilot era (superseded by bench.sh)
results/               generated; gitignored except for .gitkeep
bin/                   build output; gitignored
scripts/, src/, …      upstream lmbench (modified: scripts/build, scripts/os; see docs/PATCHES.md)
```

## Hardware assumption

Built and tested against **Phytium D3000M** (8 cores, 2 clusters of 4 cores each,
2 "big" cores at 2.9 GHz max + 6 "little" at 1.9 GHz max). Configs lock all cores
to 1.9 GHz so that frequency is not a confounding variable across environments.
For other aarch64 hardware, copy `configs/CONFIG.host` to a new name and
adjust `MHZ`, `PROCESSORS`, `TOTAL_MEM`, `LINE_SIZE`.

## License

Upstream lmbench is GPLv2 with an additional restriction that modified-source
benchmark results may not be published as "lmbench results" — see `COPYING`.
The local additions (`bench.sh`, `parse-lmbench.py`, `configs/`, `docs/`) are
contributed under the same terms.
