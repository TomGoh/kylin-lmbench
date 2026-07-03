# Pixel 9 Pro XL pKVM/nVHE MADV teardown experiment

Date: 2026-06-29

Plan source: `docs/mmap/pixel-pkvm-mmap-experiment-plan.zh-CN.md`

Device: Pixel 9 Pro XL (`komodo`), serial `47091FDAS009VF`, AOSP userdebug.

## Scope

This run follows the Pixel mmap/teardown plan's minimum closed loop first:

1. Collect Stage 0 metadata for each boot.
2. Run the userspace `MADV_DONTNEED` slope probe in the live KVM mode.
3. Build adjacent `nvhe`/`protected` boot pairs.
4. Analyze both `single` and `batched` probe modes with touched/untouched DiD.
5. Report `per_entry_cost_did_ns_per_op` together with `resolution_floor_ns_per_op`.
6. Restore the phone to protected mode and verify the original `vendor_kernel_boot_b` image.

The phone was already in `nvhe` when this run started, so the sequence starts with
`nvhe-boot01` instead of the plan's suggested `protected-boot01`. This is recorded
as a sequencing deviation, not a change in the estimator.

## Safety State

- Bootloader state before data collection: unlocked (`ro.boot.flash.locked=0`).
- Active slot before data collection: `_b`.
- Current KVM mode before data collection: `nvhe`.
- Only allowed flash target during mode switching: `vendor_kernel_boot_b`.
- Bootloader partitions remain off-limits.

## Inputs

Android probe:

```text
655cab7615f0f12df68479aa022d0b42d49a76eca4b047cbbc21357fc4901ff3  experiments/munmap-tlbi/pixel_madv_entry_slope.android
```

Pixel boot image backups:

```text
da27174be409b06dc61376cb6f1a444f1b4bcea257640e22c5f12836eaab6d3f  /home/haoze/pixel-komodo-boot-backup/vendor_kernel_boot_b.img
3c858cc9cdcabee6c4e9cbd0bfb0b08c00e2fd89c6572bb529b55b1761c62630  /home/haoze/pixel-komodo-boot-backup/vendor_kernel_boot_nvhe.img
```

Host-side verification before collection:

```text
make -C experiments/munmap-tlbi android
python3 -m unittest tests/test_pixel_madv_entry_slope.py tests/test_pixel_madv_analyze.py tests/test_pixel_madv_summarize.py
```

Result: probe was up to date; 5 unit tests passed.

## Collection Parameters

Pilot/main MADV slope command shape:

```bash
OUT=<boot-dir> \
CPU=4 PAGES=256,512,1024,2048,4096,8192 RUNS=30 BLOCKS=1 \
WAIT_THERMAL_MAX_MC=39000 WAIT_THERMAL_POLL_SEC=5 COOLDOWN_SEC=3 \
FREQ_DROP_PCT=100 THERMAL_RISE_MC=1000000 \
bash experiments/munmap-tlbi/pixel-run-madv-entry-slope.sh
```

The runner does not switch KVM mode, reboot, fastboot, or flash. Mode switching is
performed only with `~/.claude/skills/pixel-komodo-pkvm-nvhe/scripts/komodo-flash.sh`.

Reject policy for formal MADV slope data:

- Before each randomized task, the runner waits until max thermal is below 39C
  (`WAIT_THERMAL_MAX_MC=39000`, `WAIT_THERMAL_POLL_SEC=5`).
- Temperature and frequency before/after each task are recorded. The runner also
  records `thermal_gate_start_mc`, `thermal_gate_ready_mc`, and `thermal_wait_sec`.
- Post-task temperature rise and frequency drop are not used as automatic row filters
  (`THERMAL_RISE_MC=1000000`, `FREQ_DROP_PCT=100`).
- A 3 second cooldown remains between randomized tasks.
- If later inspection shows actual throttling, an obvious frequency collapse, or
  high-temperature regime changes, the affected boot will be marked and rerun at the
  boot level rather than deleting one N point from the slope fit.
- Reason: the initial `nvhe` pilot with the default 5% frequency-drop rule rejected
  most whole randomized tasks because the Pixel governor changes `scaling_cur_freq`
  across adb-launched tasks. That pilot is retained under
  `raw/nvhe/boot01-pilot-default-reject/` and excluded from DiD analysis.
- A second `nvhe` pilot with `THERMAL_RISE_MC=3000` rejected the whole
  `single/touched/1024` task because max thermal moved from 37C to 41C within that
  task. This was below throttling-like temperatures but removed one N point from
  the primary slope, so an intermediate pilot tried a 5C per-task rise threshold
  and a 3 second cooldown.
- After review, formal collection replaces task-after thermal-rise rejection with a
  task-before temperature gate. The old per-task rise check is too coarse for this
  device: it can delete a whole randomized N point and damage the slope estimator.
  Temperature remains auditable in the CSV and metadata.

## Planned Boot Order

Current target:

```text
nvhe-boot01
protected-boot01
protected-boot02
nvhe-boot02
```

After two boot pairs, analyze the resolution floor before deciding whether to extend
to four boot pairs.

## Interim Result

Two same-threshold boot pairs were collected with `WAIT_THERMAL_MAX_MC=39000`:

- Pair01: `protected-boot01` vs `nvhe-boot02`
- Pair02: `protected-boot02` vs `nvhe-boot03`

Primary single-page `MADV_DONTNEED` DiD result:

```text
per_entry_median_ns_per_op = 167.039248
resolution_floor_ns_per_op = 31.382061
per_entry_ci95 = [140.097851, 193.980646]
```

Batched `MADV_DONTNEED(base, N*4K)` result:

```text
per_entry_median_ns_per_op = -13.925842
resolution_floor_ns_per_op = 10.200838
per_entry_ci95 = [-24.126680, -3.725005]
```

Interpretation at this stage:

- The single-page probe shows a repeatable protected-side per-entry cost above the
  two-pair resolution floor.
- The batched path does not show a positive protected-side per-entry penalty.
- This supports the plan's expected split: Tensor G4/pKVM can still make forced
  per-entry teardown more expensive, while the real batched teardown path hides that
  cost, consistent with TLB range maintenance being available.

Simpleperf key point (`single/touched/pages=4096`, 30 runs, CPU 4) was collected in
`summary/simpleperf-single-touched-4096.csv`. Page-fault counts matched
(`123201` nvhe vs `123206` protected), while protected had higher cycles and backend
stalls (`568.5M` to `657.8M` cycles; `363.0M` to `444.6M` backend stalls), which is
consistent with extra wait rather than a different page-fault count.

This is still a two-pair pilot-level result. It is strong enough to guide the next
stage, but a final write-up should either extend to four boot pairs or explicitly
state the two-pair resolution floor.

## Running Log

- 2026-06-29: Initial safety/tooling checks complete. Device reachable via adb only
  with elevated USB access from WSL. Starting in `nvhe`.
- 2026-06-29: `nvhe` pilot with default frequency-drop rejection completed with 720
  rows and no CPU migration, but only 270 rows had `reject_reason=ok`. Formal data
  collection therefore disables frequency-based rejection before the first analyzed
  boot sample.
- 2026-06-29: `nvhe` pilot with frequency rejection disabled but 3C thermal-rise
  rejection completed with 720 rows and no CPU migration, but rejected all
  `single/touched/1024` rows. The next pilot increased thermal-rise threshold to
  5C and cooldown to 3 seconds.
- 2026-06-29: `nvhe` pilot with 5C thermal-rise rejection completed with 720 rows,
  all `reject_reason=ok`, and no CPU migration. It is retained under
  `raw/nvhe/boot01-pilot-thermal5c/` but excluded because the final formal policy now
  uses a task-before temperature gate instead of task-after thermal-rise rejection.
- 2026-06-29: Updated the plan and runner to wait before each task until max thermal
  is below 37C.
- 2026-06-29: Formal `nvhe-boot01` completed:
  `raw/nvhe/boot01/raw/nvhe_madv_entry.csv`. It has 720 rows, 24 groups with 30
  rows each, all `status=ok`, all `reject_reason=ok`, and no CPU migration. Thermal
  gate wait time was 0..70 seconds; every task started with `thermal_gate_ready_mc`
  at 36C.
- 2026-06-29: Restored protected mode with `komodo-flash.sh restore`. The first
  verify attempt ran during a transient adb/WSL USB disconnect and produced empty
  fields; it is retained as `logs/protected-boot01-verify.initial-empty.txt`.
  A rerun verified `kvm-arm.mode=protected`, dmesg `Protected KVM`, and
  `vendor_kernel_boot_b` sha256 equal to the original backup
  (`da27174be409b06dc61376cb6f1a444f1b4bcea257640e22c5f12836eaab6d3f`).
- 2026-06-29: First protected collection attempt with the 37C gate did not start
  a task because max thermal sat at 37C and the runner requires `< threshold`.
  It was interrupted before any CSV rows were written and retained as
  `raw/protected/boot01-aborted-gate37/`. The formal gate is raised to 39C for
  subsequent same-threshold data collection. The earlier `nvhe-boot01` remains a
  stricter-gate reference; a same-threshold `nvhe-boot02` will be collected after
  `protected-boot01`.
- 2026-06-29: Formal `protected-boot01` with 39C gate completed:
  `raw/protected/boot01/raw/protected_madv_entry.csv`. It has 720 rows, 24 groups
  with 30 rows each, all `status=ok`, all `reject_reason=ok`, and no CPU migration.
  Thermal gate wait was 0 seconds for all tasks; gate-ready temperatures were
  37..38C and post-task max thermal reached 41C.
- 2026-06-29: Switched back to `nvhe`; initial verify again hit transient adb/WSL
  empty output and is retained as `logs/nvhe-boot02-verify.initial-empty.txt`.
  Rerun verified last-wins `kvm-arm.mode=nvhe`, dmesg `Hyp mode initialized
  successfully`, and partition sha256 equal to the nvhe image
  (`3c858cc9cdcabee6c4e9cbd0bfb0b08c00e2fd89c6572bb529b55b1761c62630`).
- 2026-06-29: Formal `nvhe-boot02` with 39C gate completed:
  `raw/nvhe/boot02/raw/nvhe_madv_entry.csv`. It has 720 rows, 24 groups with 30
  rows each, all `status=ok`, all `reject_reason=ok`, and no CPU migration.
  Thermal gate wait was 0..20 seconds; gate-ready temperatures were 36..38C.
- 2026-06-29: Pair01 (`protected-boot01` vs `nvhe-boot02`) analyzed. Single-page
  DiD `per_entry_cost_did_ns_per_op=193.980646` with per-pair floor
  `53.833962`; batched DiD `-24.126680` with floor `0.128621`. This is a
  one-pair candidate signal only; continuing to a second boot pair before writing
  conclusions.
- 2026-06-29: `protected-boot02` and `nvhe-boot03` completed with 720 rows each,
  24 groups with 30 rows each, all `status=ok`, all `reject_reason=ok`, and no CPU
  migration. Pair02 single-page DiD is `140.097851 ns/op`; batched DiD is
  `-3.725005 ns/op`.
- 2026-06-29: Two-pair summaries written to `summary/single-summary.csv` and
  `summary/batched-summary.csv`; simpleperf key point written to
  `summary/simpleperf-single-touched-4096.csv`.
- 2026-06-29: Final restore to protected completed. `final-protected-verify.txt`
  confirms `kvm-arm.mode=protected` and `vendor_kernel_boot_b` sha256 equals the
  original backup. A post-simpleperf check again reported live `kvm-arm.mode=protected`
  and the same partition hash.
