# 核查报告：audit:final-hygiene

## Summary

Final hygiene and reproducibility audit of kylin-lmbench, branch pkvm-memlat-rootcause (HEAD f44422c8; 64 commits ahead of origin/claude/n90-pkvm-llc-latency-oqwtb0; 217 files changed: 215 added, 2 modified). I found nothing that affects the conclusions. The problems are documentation gaps, incomplete redaction and two prediction commits whose order against their runs cannot be resolved at one-second resolution.

(1) Sensitive data. I scanned all 217 changed files and found no IP addresses (no dotted quad at all, none of 10.42.*), no passwords or credentials, no user e-mail addresses, no /home/... paths and no /tmp/claude-... paths. Smaller leftovers:
- 28 files under docs/memlat/agents carry home-relative workstation paths (klinux, ~/Dev/kylin100-xkernel-boots/..., ~/xhyper-workspace/...).
- About 10 references point to the analyst's scratch area that docs/memlat/agents/README.md says was replaced by <scratch>/. Examples: '<scratch>/paper/paper.txt', '<scratch>/wf6/...', '<scratch>/wf1-results/night3.json', '<scratch>/wf2-results/...'.
- 4 lines quote the device path /root/lmbench-3.0-a9.
- hw-survey-n80.txt:17 and thp-contpte-n80.txt:41 contain the device's root UUID and ostree deployment hash.
- Commit metadata carries the author's e-mail address and the session URL. These are the required attribution lines, not file content.

(2) Derived tables. I ran analyze-device-logs.py, analyze-state-experiments.py, analyze-host-memlat.py and analyze-guest-memlat.py twice each (python3 -B, Python 3.14), writing into my working directory. All 4 outputs are byte-identical to results/memlat-n80-20260930/derived/*.md and identical between the two runs. The only randomness is seeded random.Random in analyze-host-memlat.py. The descriptions of what state-tables.md contains are out of date: the results README line 89 stops at H2–H5, probe README line 170 stops at H2/H3 and G1–G4, and the script docstring lacks H8 and G5.

(3) Logs and scripts. Every log named in both results READMEs exists, including every log of the night listed in the task. In results/memlat-d80f3-20260930, 4 files are present but not described: expH4-d80f3.log, expH4-d80f3-shim.log, expH5-d80f3.log and expH5-d80f3-shim.log. analyze-state-experiments.py reads them for the H4 and H5 tables. Every script named in experiments/memlat-probe/README.zh-CN.md exists ('lib_mem.c' is src/lib_mem.c), and every file in that directory is mentioned. holdcheck.sh is cited in worklog line 1492 and hashed in binaries-n80.txt, but neither the script nor its output is in the repo. meta.log has no entries for run18, run21 or run32 (N, N4 and H8), although the README says it records every batch; the logs of those runs carry their own time stamps.

I compared repo sources with the device sha256 listings in binaries-n80.txt. All match the second listing (00:31) except three, each matching an earlier commit:
- run16: comment-only change.
- layoutshim.c: changed for H8. It behaves the same when SHUFFLE_HEAD_MB is unset; H8 used the e4a1099b version.
- run6-current-state.sh: the device ran 8b708298, which still contained the lmbench H section; HEAD has removed it.

No checksums exist for the H8 or G5 program versions.

(4) Build. In a git-archive copy, make built all 10 programs with gcc 15.2 -O2 -Wall and gave no warnings. layoutshim.so and build-lmbench-tools.sh (lat_mem_rd, bw_mem) also built. All 7 Python files parse and all shell scripts pass sh -n. Small functional checks: lat_mem_rd prints its table, and probe3 in tlb mode prints a result line. probe3's usage message omits the tlb mode.

(5) Prediction timing. I checked the 17 sections from 11.9 onward that were written before their runs. None was committed after its run started, and the prediction text of every one is unchanged at HEAD. Two are ties at one-second resolution:
- 11.27 (H6): commit 572959f2 at 23:42:35; expH6 and meta run29 also start at 23:42:35.
- 11.29 (H7): commit 5f09d5df at 00:08:57; expH7 and meta run31 also start at 00:08:57. 11.29 itself says H7 is an exploratory observation with no hypothesis.

Two more start only 1 s after their commit: 11.13 (V3) and 11.24 (H3).

The worklog header says '正文保留原样' (the body is kept as originally written), but some text was edited afterwards without an entry in the corrections table:
- 9 section-heading times were changed to match commit times (for example 11.9 '20:10' became '19:55').
- The 11.10 X tables were recomputed in 145c5318.
- The E1/E2 reasoning paragraph of 11.23 was hedged in 4eeb2c79, after H2 had run. The H2 predictions (a) to (c) themselves are unchanged.

Separately, the run19 script was changed by e2032e7e at 21:46:36, the same second run19 started, after the N2 prediction (6bf8c291, 21:46:03).

(6) git status is clean. The only untracked path is experiments/memlat-probe/__pycache__ (created 2026-10-02 09:13:53, before my audit), and it is ignored by .gitignore line 48. No stash; one worktree. The local branch's upstream is a branch with a different name, and the 64 commits are not pushed.

## Defects

- **cosmetic** | results/memlat-d80f3-20260930/README.md (Files table, lines 32-37): 4 log files in the directory are not described: expH4-d80f3.log (23:06:19-23:18:16), expH4-d80f3-shim.log, expH5-d80f3.log (23:21:49-23:39:42), expH5-d80f3-shim.log. analyze-state-experiments.py lines 1522-1523 and 1614-1615 read them for the workstation rows of the H4 and H5 tables, and line 39 of the README lists only N, N4, T2, L2 as table sources. Fix: add rows for H4 (run27-lmbench-layout-shim.sh, 23:06-23:18) and H5 (run28-lmbench-layout-strides.sh, 23:21-23:40), say that the -shim logs come from layoutshim.so (adj=na without root), and add 'Exp H4' and 'Exp H5' to line 39. Effect: None on the numbers. A reader cannot tell from the README where the workstation half of the H4 and H5 tables comes from.
- **cosmetic** | results/memlat-n80-20260930/meta.log; README.md line 85: The README says meta.log records the start and end of every batch, but run18 (expN-n80), run21 (expN4-n80) and run32 (expH8) have no entries. The workstation runs (run18, run21, run23, run24, run27, run28) also have no meta file. Fix: change line 85 to '各批次的起止时间（run18、run21、run32 没有写 meta.log，时刻见各日志第一行）', or add the stamps from the logs (expN-n80 21:40:06-21:41:07, expN4-n80 22:07:54-22:09:56, expH8 2026-10-01 00:58:18-01:11:49). Effect: None: the three logs carry their own ISO stamps. Only expN2 and expN5 have no stamps, and both are in meta.log.
- **cosmetic** | docs/memlat/memlat-investigation-worklog.zh-CN.md:1492 (11.29); results/memlat-n80-20260930/binaries-n80.txt (last line): holdcheck.sh (sha256 378e7e5e...) is named as the source of the observation that after holding 2560 MB, Normal-zone Movable free blocks of orders 0-9 are almost gone and 115 order-10 blocks are left. Neither the script nor its output is in the repo. Fix: add experiments/memlat-probe/holdcheck.sh and its output, or state in 11.29 that the output was not archived and cite expH7.log line 49 instead. That line shows the same pattern from a later run (Movable orders 0-9: 1,0,1,1,0,1,0,1,0,0; 104 order-10 blocks). Effect: expH7.log corroborates the qualitative point. The figure '115' has no primary source.
- **cosmetic** | docs/memlat/agents/*.md (28 files with ~/ paths; audit-kernel-alloc.md:54, audit-night-code.md:46, critic-c.md, critic-g.md, investigate-prior-docs.md:226-244, verify-host-b-primary.md, verify-ng-primary.md, verify-ng-adversary.md:44, verify-nn-alloc-adversary.md, verify-prior-c-*.md with <scratch>/ or wf*-results/ paths): Redaction is incomplete. agents/README.md says scratch directories appear as <scratch>/, but reports still cite '<scratch>/paper/paper.txt', '<scratch>/paper/x/word/media/image8.png', '<scratch>/wf6/...', '<scratch>/wf2/...', '<scratch>/wf1-results/night3.json' and '<scratch>/wf2-results/*.md'. Home-relative workstation paths also remain, such as klinux, ~/Dev/kylin100-xkernel-boots/scripts/start_xkernel_pvm.sh and ~/xhyper-workspace/docs/artifacts/n80-20260929-avf-r52/xkpvm-customfw.sh. There are no absolute /home or /tmp/claude paths and no user names. Fix: replace <scratch>/... and wf*-results/... with <scratch>/..., replace ~/Dev/<repo> with the repository name, and say that the paper extract (paper.txt) is not in the repo. Effect: None. The evidence cited at those paths cannot be re-opened from the repository.
- **cosmetic** | results/memlat-n80-20260930/hw-survey-n80.txt:17, thp-contpte-n80.txt:41; docs/memlat/agents/verify-lmb-a-*.md:9-11: The device's /proc/cmdline is archived with its root filesystem UUID (061ec519-...) and ostree deployment checksum. Two reports quote the device path /root/lmbench-3.0-a9. These are not credentials or addresses, but they are host identifiers. Fix (optional): mask the UUID and the ostree hash in the two .txt files. Effect: None.
- **cosmetic** | docs/memlat/memlat-investigation-worklog.zh-CN.md lines 7-8 (header) versus body edits: The header says the body is kept as originally written (正文保留原样), but closed sections were edited later without an entry in the corrections table: (a) 9 '开始之前写下' heading times were rewritten to match commit times (11.9 20:10->19:55, 11.11 20:20->20:13, 11.13 20:40->20:30, 11.18 21:45->21:40, 11.21 22:20->22:19, 11.22 22:33->22:25, 11.24 22:53->22:52, 11.26 23:24->23:21, 11.29 00:12->00:09); (b) the 11.10 result tables were recomputed in 145c5318 (for example +0.6%->+0.5%, +13.1%->+13.3%, 8.21->8.22) after Y had run; (c) the pre-H2 E1/E2 reasoning in 11.23 was changed in 4eeb2c79, after H2 ran (22:38-22:50): '本身随'->'本身可以随', '0.76-0.86'->'0.79-0.90 (升序加降序)', and a hedge was added ('这取决于当时空闲内存的状态，不是总成立...'). Fix: add rows for (a)-(c) to the corrections table, or change the header to say that headings and recomputed figures were adjusted (with commit ids). Effect: None of the edits touches a prediction. Edit (c) makes earlier reasoning look more cautious than it was when H2 started.
- **cosmetic** | docs/memlat/memlat-investigation-worklog.zh-CN.md 11.27 (commit 572959f2) and 11.29 (commit 5f09d5df): Each commit's time equals the first stamp of its run to the second: H6 at 23:42:35 (expH6.log line 1, meta 'run29 start'), H7 at 00:08:57 (expH7.log first epoch, meta 'run31 start'). The order of commit and run cannot be shown at 1-s resolution. The device and workstation clocks are not synchronised by any recorded means; they agree within about 1 s judging by parallel starts (expH4 23:06:20 versus expH4-d80f3 23:06:19). Fix: record the launch command and its order (commit, then start) in 11.27 and 11.29, or say that the two are simultaneous within clock resolution. Effect: No section was committed after its run started. For H6 and H7 the 'written before' claim holds only within about 1 s, and H7 is declared exploratory in its own text.
- **cosmetic** | experiments/memlat-probe/run6-current-state.sh (HEAD) versus the device run (binaries-n80.txt listing 2: 65261aee = commit 8b708298): The device ran the 8b708298 version, which also contained the lmbench H section (stopped by hand at 18:44, meta.log line 10). HEAD's run6 (5cca9000) removed that section. run16-vm-shared-repeat.sh also differs from the device version, in comments only (77c3bf31 versus 53ac7a80). No checksums were recorded for the program versions used in H8 and G5 (layoutshim.c e4a1099b, lmb-frames.py, nocsample, run32, run33). Fix: name in the results README the commit of each run script that was actually used, and add a third checksum listing for H8 and G5, or cite the commits e4a1099b and 57d3a637. Effect: None found. The layoutshim change keeps the old behaviour when SHUFFLE_HEAD_MB is unset.
- **cosmetic** | experiments/memlat-probe/run_all.sh:3, run2.sh:3, run3.sh:3: These three scripts hard-code 'cd /tmp/kx-memprobe' (the device working directory). Every other script uses cd "$(dirname "$0")", and README.zh-CN.md line 103 says scripts run in their own directory. Fix: replace the line with cd "$(dirname "$0")" || exit 1. Effect: None. Re-running these scripts elsewhere fails or writes to the wrong place.
- **cosmetic** | experiments/memlat-probe/README.zh-CN.md lines 143-149 and 170; analyze-state-experiments.py docstring lines 2-53; results/memlat-n80-20260930/README.md line 89: Stale descriptions: run27, run28 and run29 sit in the table '不改系统设置、但还没有执行的' (not yet executed) while being marked as executed; run-noc-all.sh appears in two tables. Line 170 lists analyze-state coverage only up to H2/H3 plus G1-G4, and the README line 89 stops at H2-H5. state-tables.md actually has sections H6 (line 944), H7 (963), H8 (1026) and G5 (1062), and the docstring omits H8 and G5. Fix: move run27-29 into the executed table, remove the duplicate run-noc-all row, and update the three coverage lists to 'R ... H2-H8, G5, two-factor check'. Effect: None.
- **cosmetic** | experiments/memlat-probe/probe3.c:277; Makefile clean target: The usage message reads '<seq|rand>' although tlb mode exists (line 281; the header comment at line 12 is correct). 'make clean' does not remove layoutshim.so. Fix: print '<seq|rand|tlb>' and add layoutshim.so to clean. Effect: None.
- **cosmetic** | docs/memlat/memlat-investigation-worklog.zh-CN.md:3: The header says the last sections were written on the early morning of 2026-10-01, but 11.32-11.34 were written on 2026-10-02 (commits 8a0d6446, 57d3a637, e2f62bea). Fix: update the date line. Effect: None.
- **cosmetic** | git config branch.pkvm-memlat-rootcause (remote origin, merge refs/heads/claude/n90-pkvm-llc-latency-oqwtb0): The local branch tracks a branch with a different name and is 64 commits ahead and unpushed. The commit times that support the 'written before the run' claims exist only in the local repository; the reflog agrees with them (64 of 65 entries match the commit time to the second; the mismatch is the branch-creation entry). Fix: push to a branch of the same name (git push -u origin pkvm-memlat-rootcause) so that a remote timestamp exists. Effect: Prediction timing cannot be attested by any third party until the branch is pushed.

## Discrepancies

- docs/memlat/agents/README.md says scratch paths are written as <scratch>/, but <scratch>/..., <scratch>/wf1-results/... and <scratch>/wf2-results/... references remain in at least 11 reports.
- Worklog header '正文保留原样' versus 9 heading-time edits, the 11.10 table recomputation (145c5318) and the 11.23 reasoning edit after H2 (4eeb2c79); none is in the corrections table.
- results/memlat-n80-20260930/README.md line 85 says meta.log has every batch, but run18, run21 and run32 are missing.
- results/memlat-n80-20260930/README.md line 89, probe README line 170 and the analyze-state-experiments.py docstring under-describe what state-tables.md contains (H6, H7, H8, G5).
- Probe README lists run27-29 under 'not yet executed' while saying they were executed.
- binaries-n80.txt (00:31) versus HEAD: run6-current-state.sh, run16-vm-shared-repeat.sh and layoutshim.c differ from the versions hashed on the device. The device versions are commits 8b708298, 77c3bf31 and be9a2b4b; layoutshim then changed for H8 in e4a1099b.

## Threats to validity

- Commit times are set by the workstation and log stamps by the device. No clock-offset measurement is archived. Parallel starts (expH4 23:06:20 on the device, expH4-d80f3 23:06:19 on the workstation) suggest the clocks agree within about 1 s, but this is not proven, so the 0-1 s margins (V3, H3, H6, H7) cannot be resolved.
- Commit timestamps and the reflog are local and unpushed. A rewritten history would not be detectable from the repository alone, though I found no amend or rebase in the reflog and author date equals committer date for all 64 commits.
- My checks were limited to one-second resolution and covered sections 11.9 to 11.33 only; predictions before 11.9 were not audited.
- I regenerated the tables with Python 3.14 on the workstation only. analyze-host-memlat.py uses seeded random.Random; byte-identical output under other Python versions was not tested.
- The sensitive-data scan is pattern-based (IPs, e-mail, paths, credential keywords, MAC, UUID, ssh/adb/sudo). Free-text identifiers in other forms could be missed; binary files: none among the changed files.
- The build check used gcc 15.2 on x86-free aarch64 Ubuntu 7.0; the device used gcc 12.3. The binaries were not compared with the device hashes because the compilers differ.

## Recomputed tables

| worklog section | experiment | pre-run commit (time, +0800) | first run stamp (source) | margin | prediction text at HEAD |
|---|---|---|---|---:|---|
| 11.9 | X | b3620723 19:55:05 | 19:56:23 (meta run14 start; expX3 first epoch) | +78 s | unchanged (heading time only) |
| 11.11 | Y | 02d88f61 20:13:15 | 20:13:29 (expY.log) | +14 s | unchanged (heading time only) |
| 11.13 | V3 | 77c3bf31 20:30:27 | 20:30:28 (expV3.log, meta run16) | +1 s | unchanged (heading time only) |
| 11.16 | Z | 6c31518e 21:05:18 | 21:05:49 (expZ.log) | +31 s | unchanged |
| 11.18 | N | c28d91db 21:39:48 | 21:40:06 (expN-n80), 21:40:17 (expN-d80f3) | +18 s | unchanged (heading time only) |
| 11.19 | N2 | 6bf8c291 21:46:03 | 21:46:36 (meta run19; log has no stamps) | +33 s | unchanged; run19 script changed by e2032e7e at 21:46:36 |
| 11.20 | N3, N4 | b44c13ae 22:05:01 | 22:05:24 (expN3), 22:05:34 (expN4-d80f3), 22:07:54 (expN4-n80) | +23 s | unchanged |
| 11.21 | N5, T2 | 4694b8d5 22:18:41 | 22:18:55 (meta run22), 22:19:06 (expT2) | +14 s | unchanged (heading time only) |
| 11.22 | L2 | f2cae329 22:25:21 | 22:25:32 (expL2-d80f3), 22:29:10 (expL2-n80) | +11 s | unchanged (heading time only) |
| 11.23 | H2 | b88b579d 22:37:56 | 22:38:31 (expH2 first epoch) | +35 s | predictions (a)-(c) unchanged; preceding E1/E2 paragraph edited in 4eeb2c79 after the run |
| 11.24 | H3 | 4eeb2c79 22:51:53 | 22:51:54 (expH3) | +1 s | unchanged (heading time only) |
| 11.25 | H4 | be9a2b4b 23:05:44 | 23:06:19 (expH4-d80f3), 23:06:20 (expH4) | +35 s | unchanged |
| 11.26 | H5 | 95270037 23:20:59 | 23:21:18 (expH5), 23:21:49 (expH5-d80f3) | +19 s | unchanged (heading time only) |
| 11.27 | H6 | 572959f2 23:42:35 | 23:42:35 (expH6, meta run29) | 0 s (tie) | unchanged |
| 11.29 | H7 | 5f09d5df 00:08:57 | 00:08:57 (expH7 first epoch, meta run31) | 0 s (tie) | unchanged (heading time only); declared exploratory |
| 11.31 | H8 | e4a1099b 00:57:43 | 00:58:18 (expH8 '## start') | +35 s | unchanged |
| 11.33 | G5 | 57d3a637 08:48:35 (10-02) | 08:49:22 (meta run33, expG5-noc-samples) | +47 s | unchanged |

| derived table | regenerated by | identical to committed | run1 == run2 | runtime |
|---|---|---|---|---|
| device-tables.md | analyze-device-logs.py | yes | yes | 0.16 s |
| state-tables.md | analyze-state-experiments.py | yes | yes | 11 s |
| host-n90-tables.md | analyze-host-memlat.py (seeded RNG) | yes | yes | 41-43 s |
| guest-n90-tables.md | analyze-guest-memlat.py | yes | yes | 0.8 s |
