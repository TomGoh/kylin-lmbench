#!/usr/bin/env python3
"""Tabulate the N80 platform-state experiments of the evening of 2026-09-30.

  Exp R   sequential stride 256, chain built once versus rewritten before
          every interval as lmbench does             (expR.log)
  Exp BG  the headline points with memory traffic from other cores (expBG.log)
  Exp H   lmbench's own lat_mem_rd, repeated sweeps, buffer on 4 KiB pages
          (expH-rand.log, expH-seq256.log, expH-seqall.log, expH-noc-samples.log)
  Exp S   random chase on pages from one 1 GiB physical slot at a time
          (expS.log, iomem-n80.txt)
  Exp V   the same, separately for pages that share a 2 MiB region with the
          running protected VM and pages that do not (expV.log, vm-frames-n80.txt)
  Exp V2, V3  the same at working sets from 2 to 64 MB, four page sets per size
          (expV2.log, expV3.log)
  Exp W   sequential chase over sorted and shuffled page sets, by class (expW.log)
  Exp X   the form of the timed loop: one load in a loop against lmbench's 100
          loads in a row (expX1.log, expX2.log, expX3.log)
  Exp Y   the layout effect at 8 MB for every stride (expY.log)
  Exp Z   a chase dominated by address translation (expZ.log)
  Exp N   the same chase as an unprivileged program, on the N80 and on a
          workstation with the same cores that has no host stage-2
          (expN-n80.log, ../memlat-d80f3-20260930/expN-d80f3.log)
  Exp N2  the same as root with other frames each time (expN2.log)
  Exp N3  page sets that mix two GiB slots in a fixed proportion (expN3.log)
  Exp N4  pages first touched in chain order or in ascending virtual order
          (expN4-n80.log, ../memlat-d80f3-20260930/expN4-d80f3.log)
  Exp N5  the share of probe3's pages in 2 MiB regions of the running VM, and
          one fit over all clean probe3 runs of N2, N4 and N5 (expN5.log)
  Exp T2  first-touch order on the workstation, unprivileged
          (../memlat-d80f3-20260930/expT2.log)
  Exp L2  sorted, reversed and shuffled virtual order of pages taken from
          huge pages, on the N80 and on the workstation
          (expL2-n80.log, ../memlat-d80f3-20260930/expL2-d80f3.log)
  Exp H2, H3  lmbench's own lat_mem_rd with memory held back by another
          process, so that its children get frames from larger free blocks;
          H2 with probe3 before and after every sweep, H3 with the layout of
          lmbench's own buffers read from /proc/<pid>/pagemap
          (expH2.log, expH3.log, expH3-frames.log)
  Exp H4  lmbench's own lat_mem_rd on a buffer whose physical layout is set
          by a preloaded library, on the N80 and on the workstation
          (expH4.log, expH4-shim.log, ../memlat-d80f3-20260930/expH4-d80f3.log)
  Exp H5  the same for the other strides of the paper's command, next to
          the two levels of the N90 host data per stride
          (expH5.log, ../memlat-d80f3-20260930/expH5-d80f3.log)
  Exp G1-G4  the interconnect-frequency experiments, if their logs exist
          (expG1.log, expG2.log, expG3.log, expG4-*.log)

The N90 host data of June are printed next to Exp H for comparison; they come
from results/n90-day3-host and are a different machine.

Standard library only.  Usage:  python3 analyze-state-experiments.py [repo_root]
"""
import collections
import csv
import math
import os
import re
import statistics as st
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..")
DEV = os.path.join(ROOT, "results", "memlat-n80-20260930")
HOST = os.path.join(ROOT, "results", "n90-day3-host")
D80 = os.path.join(ROOT, "results", "memlat-d80f3-20260930")


def kv(line):
    d = {}
    for k, v in re.findall(r"(\w+)=([^\s]+)", line):
        v = re.sub(r"\(mux[\d.]+\)", "", v)
        try:
            d[k] = float(v)
        except ValueError:
            d[k] = v
    return d


def probe_rows(name):
    path = os.path.join(DEV, name)
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            if "ns_min=" in line:
                out.append(kv(line))
    return out


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(x, y):
    if len(x) < 3:
        return float("nan")
    mx, my = st.mean(x), st.mean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def largest_gap(v):
    """Largest gap between neighbouring sorted values, relative to the lower one."""
    s = sorted(v)
    best = (0.0, s[0], s[0])
    for a, b in zip(s, s[1:]):
        if (b - a) / a > best[0]:
            best = ((b - a) / a, a, b)
    return best


def lmbench_sweeps(name):
    """-> list of (header dict, {stride: {size_mb: ns}})"""
    path = os.path.join(DEV, name)
    if not os.path.exists(path):
        return []
    sweeps = []
    cur = None
    stride = None
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("## "):
                cur = (kv(line), collections.OrderedDict())
                sweeps.append(cur)
                stride = None
                continue
            if cur is None:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith('"stride='):
                stride = int(parts[1].split("=")[1])
                cur[1][stride] = collections.OrderedDict()
            elif len(parts) == 3 and stride is not None:
                try:
                    cur[1][stride][float(parts[1])] = float(parts[2])
                except ValueError:
                    pass
    return sweeps


def n90(bench):
    files = {"kvmoff": "n90-kvmoff-noLSM-full-cpu0.csv", "nvhe": "n90-nvhe-noLSM-full-cpu0.csv",
             "vhe": "n90-vhe-noLSM-full-cpu0.csv", "pkvm": "n90-pkvm-noLSM-try2-cpu0.csv",
             "nvhe-noisy": "n90-nvhe-noisy-full-cpu0.csv"}
    out = {}
    for cfg, name in files.items():
        d = collections.defaultdict(list)
        with open(os.path.join(HOST, name)) as fh:
            for r in csv.DictReader(fh):
                if r["bench"] == bench:
                    m = re.match(r"stride(\d+)_sz([\d.]+)MB", r["variant"])
                    d[(int(m.group(1)), float(m.group(2)))].append(float(r["value"]))
        out[cfg] = d
    return out


def exp_r():
    rows = probe_rows("expR.log")
    if not rows:
        return
    print("## Exp R: sequential stride 256, fresh process per point, 20 laps; interconnect pinned at 1800 MHz\n")
    print("rebuild 0 = chain built once; rebuild 1 = chain rewritten before every timed interval, as lmbench does.  "
          "ns = minimum of 11 intervals.  adjacency = fraction of virtually adjacent pages that are also physically "
          "adjacent, in either direction.  In every lap the rebuild 1 process ran right after the rebuild 0 process and "
          "received its frames in reverse order, so at 64 MB (and 16 MB) rebuild 1 always has a descending and rebuild 0 an "
          "ascending layout: the rebuild setting is aliased with the direction of the layout and with run order.\n")
    print("| size | rebuild | n | min | median | max | max / min | CV | largest gap between neighbouring values | "
          "median adjacency | L3 refills per access | page walks per access |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|")
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["size_mb"], int(r["rebuild"]))].append(r)
    for k in sorted(by):
        rs = by[k]
        v = [r["ns_min"] for r in rs]
        g = largest_gap(v)
        adj = [r["contig_frac"] + r["rcontig_frac"] for r in rs]
        print(f"| {k[0]:g} MB | {k[1]} | {len(v)} | {min(v):.2f} | {st.median(v):.2f} | {max(v):.2f} | {max(v) / min(v):.3f} | "
              f"{100 * st.pstdev(v) / st.mean(v):.1f}% | {100 * g[0]:.1f}% ({g[1]:.2f} to {g[2]:.2f}) | {st.median(adj):.3f} | "
              f"{st.median(r['ev2a'] for r in rs):.3f} | {st.median(r['ev2d'] for r in rs):.4f} |")
    print("\nRank correlation of the latency with the physical layout (both rebuild settings pooled).  lap = position of the "
          "process in the run (1 to 20); the partial correlation removes the lap trend from both variables:\n")
    print("| size | n | rho(ns, adjacency) | rho(ns, distinct 2 MiB regions) | rho(adjacency, lap) | rho(ns, lap) | "
          "partial rho(ns, adjacency) given lap | adjacency range | ns range |")
    print("|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for sz in sorted({k[0] for k in by}):
        rs = by[(sz, 0)] + by[(sz, 1)]
        ns = [r["ns_min"] for r in rs]
        adj = [r["contig_frac"] + r["rcontig_frac"] for r in rs]
        mb = [r["mb2_regions"] for r in rs]
        lap = list(range(1, len(by[(sz, 0)]) + 1)) + list(range(1, len(by[(sz, 1)]) + 1))
        rxy, rxz, ryz = spearman(ns, adj), spearman(ns, lap), spearman(adj, lap)
        part = (rxy - rxz * ryz) / math.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
        print(f"| {sz:g} MB | {len(rs)} | {rxy:+.2f} | {spearman(ns, mb):+.2f} | {ryz:+.2f} | {rxz:+.2f} | {part:+.2f} | "
              f"{min(adj):.2f}-{max(adj):.2f} | {min(ns):.2f}-{max(ns):.2f} |")
    # consecutive processes reuse the frames the previous one freed, in reverse order
    one = both = 0
    pairs = 0
    seq = [r for r in rows]
    for a, b in zip(seq, seq[1:]):
        if a["size_mb"] == b["size_mb"]:
            pairs += 1
            if abs(a["contig_frac"] - b["rcontig_frac"]) < 0.02:
                one += 1
                if abs(a["rcontig_frac"] - b["contig_frac"]) < 0.02:
                    both += 1
    print(f"\nFrame reuse: in {one} of {pairs} pairs of consecutive processes at the same size, the ascending adjacency of "
          f"the first equals the descending adjacency of the second within 0.02 (in {both} of them the reverse relation "
          "holds as well), which indicates that the second process received the frames the first one had just freed, "
          "in reverse order.  Frame numbers were not logged by probe3.\n")


def exp_bg():
    path = os.path.join(DEV, "expBG.log")
    if not os.path.exists(path):
        return
    by = collections.defaultdict(list)
    with open(path) as fh:
        for line in fh:
            if "ns_min=" in line:
                d = kv(line)
                by[(d["mode"], d["size_mb"], d["bg"])].append(d)
    print("## Exp BG: memory traffic from other cores; interconnect pinned at 1800 MHz\n")
    print("Background: none; r1 = one other core reading 256 MB in a loop; w1 = one other core writing; "
          "w2 = two other cores writing.  Median of the runs (ns per access, minimum of 11 intervals), change against none.\n")
    print("| test on cpu0 | none | r1 | w1 | w2 |")
    print("|---|---:|---:|---:|---:|")
    for mode, sz in (("seq", 4.0), ("seq", 8.0), ("seq", 64.0), ("rand", 8.0), ("rand", 64.0)):
        base = st.median(r["ns_min"] for r in by[(mode, sz, "none")])
        cells = []
        for bg in ("none", "r1", "w1", "w2"):
            v = [r["ns_min"] for r in by[(mode, sz, bg)]]
            m = st.median(v)
            cells.append(f"{m:.2f}" if bg == "none" else f"{m:.2f} ({100 * (m / base - 1):+.0f}%)")
        label = ("sequential stride 256" if mode == "seq" else "random") + f", {sz:g} MB"
        print(f"| {label} | " + " | ".join(cells) + " |")
    print()


def noc_samples(name):
    path = os.path.join(DEV, name)
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            p = line.split()
            if len(p) == 2:
                out.append((float(p[0]), int(p[1])))
    return out


def exp_h(prefix="expH", title="Exp H: lmbench's own lat_mem_rd on the N80, interconnect pinned at 1800 MHz"):
    rand = lmbench_sweeps(prefix + "-rand.log")
    seq = lmbench_sweeps(prefix + "-seq256.log")
    seqall = lmbench_sweeps(prefix + "-seqall.log")
    if not (rand or seq or seqall):
        return
    print(f"## {title}\n")
    samples = noc_samples(prefix + "-noc-samples.log")
    if samples:
        c = collections.Counter(f for _, f in samples)
        print("Interconnect frequency samples during these runs (value: count): " +
              ", ".join(f"{k}: {v}" for k, v in sorted(c.items())) + "\n")
    labels = []
    for s in rand + seq + seqall:
        lab = s[0].get("thp", s[0].get("state", "?"))
        if lab not in labels:
            labels.append(lab)
    host_rand = n90("lat_mem_rd_rand")
    host_seq = n90("lat_mem_rd_load")
    sizes = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]

    if rand:
        print("### Random access (lat_mem_rd -t -P 1 64 16), ns per access\n")
        head = "| size |"
        sep = "|---:|"
        for lab in labels:
            n = sum(1 for s in rand if s[0].get("thp", s[0].get("state")) == lab)
            if n:
                head += f" N80 {lab}: median of {n} sweeps (range) |"
                sep += "---:|"
        head += " N90 host, fast state (non-quiesced nVHE) | N90 host, quiesced nVHE | N90 host, quiesced protected |"
        sep += "---:|---:|---:|"
        print(head)
        print(sep)
        for sz in sizes:
            line = f"| {sz} MB |"
            for lab in labels:
                v = [s[1][16][float(sz)] for s in rand
                     if s[0].get("thp", s[0].get("state")) == lab and 16 in s[1] and float(sz) in s[1][16]]
                if any(s[0].get("thp", s[0].get("state")) == lab for s in rand):
                    line += f" {st.median(v):.1f} ({min(v):.1f}-{max(v):.1f}) |" if v else " n/a |"
            line += (f" {st.median(host_rand['nvhe-noisy'][(16, float(sz))]):.1f} |"
                     f" {st.median(host_rand['nvhe'][(16, float(sz))]):.1f} |"
                     f" {st.median(host_rand['pkvm'][(16, float(sz))]):.1f} |")
            print(line)
        print("\nThe N80 was in protected mode with its core at 1.9 GHz; the N90 core ran at 1.8 GHz. "
              "Core-bound parts differ by 5.6% for that reason alone.\n")

    allseq = []
    for s in seq + seqall:
        if 256 in s[1]:
            allseq.append(s)
    if allseq:
        print("### Sequential access, stride 256 (lat_mem_rd -P 1 64 256 and the stride-256 part of the full command), ns per access\n")
        print("'high' = more than 12% above the median of the lower half of the values of that row, the rule used for the N90 data.\n")
        print("| buffer pages | size | n | min | median | max | max / min | CV | largest gap between neighbouring values | high | "
              "N90 quiesced hosts: high of 40 | N90 quiesced hosts: min-max |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|")
        for lab in labels:
            for sz in (4, 6, 8, 12, 16, 24, 32, 48, 64):
                v = [s[1][256][float(sz)] for s in allseq
                     if s[0].get("thp", s[0].get("state")) == lab and float(sz) in s[1][256]]
                if not v:
                    continue
                low = sorted(v)[:max(1, len(v) // 2)]
                thr = 1.12 * st.median(low)
                g = largest_gap(v)
                pool = sorted(sum((host_seq[c][(256, float(sz))] for c in ("kvmoff", "nvhe", "vhe", "pkvm")), []))
                pthr = 1.12 * st.median(pool[:len(pool) // 2])
                cv = 100 * st.pstdev(v) / st.mean(v) if len(v) > 1 else 0.0
                print(f"| {lab} | {sz} MB | {len(v)} | {min(v):.2f} | {st.median(v):.2f} | {max(v):.2f} | {max(v) / min(v):.3f} | "
                      f"{cv:.1f}% | {100 * g[0]:.1f}% ({g[1]:.2f} to {g[2]:.2f}) | {sum(x > thr for x in v)}/{len(v)} | "
                      f"{sum(x > pthr for x in pool)}/40 | {pool[0]:.2f}-{pool[-1]:.2f} |")
        v8 = [s[1][256][8.0] for s in allseq if s[0].get("thp", s[0].get("state")) == labels[0] and 8.0 in s[1][256]]
        if v8:
            print(f"\n8 MB values in the order taken ({labels[0]}): " + " ".join(f"{x:.2f}" for x in v8))
        print()

    if seqall:
        print("### Sequential access at 8 MB for every stride (full command), ns per access\n")
        print("| stride | " + " | ".join(f"sweep {i + 1}" for i in range(len(seqall))) + " |")
        print("|---:|" + "---:|" * len(seqall))
        for stv in (16, 32, 64, 128, 256, 512, 1024):
            print(f"| {stv} | " + " | ".join(f"{s[1].get(stv, {}).get(8.0, float('nan')):.2f}" for s in seqall) + " |")
        print()


def exp_g1():
    path = os.path.join(DEV, "expG1.log")
    if not os.path.exists(path):
        return
    rows = []
    bw = []
    with open(path) as fh:
        for line in fh:
            d = kv(line)
            if "ns_min" in d:
                rows.append(d)
            elif "mb_per_s" in d:
                bw.append(d)
    print("## Exp G1: interconnect pinned at fixed frequencies\n")
    freqs = sorted({int(r["set"]) for r in rows}, reverse=True)
    for mode, stride, title in (("rand", 16, "Random access, ns per access (median over seeds and passes)"),
                                ("seq", 256, "Sequential stride 256, ns per access (median)")):
        print(f"### {title}\n")
        print("| size | " + " | ".join(f"{f // 1000} MHz" for f in freqs) + f" | {freqs[-1] // 1000} MHz / {freqs[0] // 1000} MHz |")
        print("|---:|" + "---:|" * (len(freqs) + 1))
        for sz in sorted({r["size_mb"] for r in rows if r["mode"] == mode and r["stride"] == stride and r["rebuild"] == 0}):
            cells = []
            for f in freqs:
                v = [r["ns_min"] for r in rows if r["mode"] == mode and r["stride"] == stride and r["rebuild"] == 0
                     and r["size_mb"] == sz and int(r["set"]) == f]
                cells.append(st.median(v) if v else float("nan"))
            print(f"| {sz:g} MB | " + " | ".join(f"{c:.2f}" for c in cells) + f" | {cells[-1] / cells[0]:.3f} |")
        print()
    if bw:
        print("### Streaming rate over 256 MB, MB/s\n")
        print("| | " + " | ".join(f"{f // 1000} MHz" for f in freqs) + " |")
        print("|---|" + "---:|" * len(freqs))
        for m in ("r", "w"):
            print(f"| {'read' if m == 'r' else 'write'} | " +
                  " | ".join(f"{st.median([b['mb_per_s'] for b in bw if b['mode'] == m and int(b['set']) == f]):.0f}" for f in freqs) + " |")
        print()


def exp_g2():
    path = os.path.join(DEV, "expG2.log")
    if not os.path.exists(path):
        return
    rows = []
    with open(path) as fh:
        for line in fh:
            d = kv(line)
            if "ns_min" in d:
                d["_noc"] = [int(x) for x in str(d.get("noc", "")).split(",") if x.strip("-").isdigit()]
                d["_reps"] = [float(x) for x in str(d.get("reps", "")).split(",") if x]
                rows.append(d)
    print("## Exp G2: one governor after another, chain rewritten before every interval\n")
    print("| governor | test | size | rebuild | n | min | median | max | max / min | interconnect frequency after the intervals (MHz: count) | "
          "rho(interval time, frequency) over all intervals |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    keys = collections.OrderedDict()
    for r in rows:
        keys.setdefault((r["gov"], r["mode"], r["size_mb"], int(r["rebuild"])), []).append(r)
    for k, rs in keys.items():
        v = [r["ns_min"] for r in rs]
        c = collections.Counter(f // 1000 for r in rs for f in r["_noc"])
        t = [x for r in rs for x in r["_reps"]]
        f = [x for r in rs for x in r["_noc"]]
        rho = f"{spearman(t, f):+.2f}" if len(t) == len(f) and len(set(f)) > 1 else "n/a"
        print(f"| {k[0]} | {k[1]} | {k[2]:g} MB | {k[3]} | {len(v)} | {min(v):.2f} | {st.median(v):.2f} | {max(v):.2f} | "
              f"{max(v) / min(v):.3f} | {', '.join(f'{a}: {b}' for a, b in sorted(c.items()))} | {rho} |")
    print()


def exp_s():
    path = os.path.join(DEV, "expS.log")
    if not os.path.exists(path):
        return
    # System RAM ranges and reserved sub-ranges of the N80 (root view of /proc/iomem)
    ram, resv = [], []
    iomem = os.path.join(DEV, "iomem-n80.txt")
    if os.path.exists(iomem):
        with open(iomem) as fh:
            for line in fh:
                m = re.match(r"(\s*)([0-9a-f]+)-([0-9a-f]+) : (.+)", line)
                if not m:
                    continue
                lo, hi, what = int(m.group(2), 16), int(m.group(3), 16) + 1, m.group(4)
                if not m.group(1) and what == "System RAM":
                    ram.append((lo, hi))
                elif m.group(1):
                    resv.append((lo, hi, what))

    def cover(slot, ranges):
        lo, hi = slot << 30, (slot + 1) << 30
        return sum(max(0, min(hi, b) - max(lo, a)) for a, b in ranges)

    runs = collections.OrderedDict()
    cur = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("## "):
                d = kv(line)
                cur = (int(d["rep"]), int(d["size_mb"]), d["pick"])
                runs[cur] = []
            elif line.startswith("slot=") and cur is not None:
                d = kv(line)
                d["_slot"] = int(str(line.split()[0].split("=")[1]), 16)
                runs[cur].append(d)
    print("## Exp S: random chase on pages taken from one 1 GiB physical slot at a time; interconnect pinned at 1800 MHz\n")
    print("Each slot is measured twice per run: pass 2 uses the same data pages after moving them to a new virtual range "
          "(new page-table pages).  ns = median of 5 full cycles.  'RAM in slot' and 'kernel or reserved inside' come from "
          "/proc/iomem; a slot that is not entirely ordinary RAM cannot be one 1 GiB stage-2 block.  This table is NOT a "
          "comparison of 1 GiB with 2 MiB blocks: a protected VM was running and had pages in eight further slots "
          "(vm-frames-n80.txt), and one donated page turns a slot's 1 GiB block into 2 MiB blocks.  Only the slots at "
          "0x22c0000000 and 0x2300000000 can still have been 1 GiB blocks; see the slot table further down.\n")
    for (size, pick) in sorted({(k[1], k[2]) for k in runs}):
        keys = [k for k in runs if k[1] == size and k[2] == pick]
        print(f"### {size} MB per slot, pages picked: {'lowest addresses of the slot' if pick == 'low' else 'spread evenly over the slot'}, "
              f"{len(keys)} run(s)\n")
        print("| slot (physical base) | RAM in slot | kernel or reserved inside | runs x passes | ns: median (min-max) | cycles | "
              "page walks per access | L1 refills | L2 refills | L3 refills | adjacency | distinct 2 MiB regions |")
        print("|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|")
        slots = sorted({d["_slot"] for k in keys for d in runs[k]})
        for s in slots:
            rs = [d for k in keys for d in runs[k] if d["_slot"] == s]
            ns = [d["ns_med"] for d in rs]
            ramc = cover(s, ram) / (1 << 30) if ram else float("nan")
            rv = cover(s, [(a, b) for a, b, _ in resv]) / (1 << 20) if resv else float("nan")
            m = lambda key: st.median(d[key] for d in rs)
            print(f"| 0x{s << 30:x} | {100 * ramc:.0f}% | {rv:.0f} MB | {len(rs)} | {st.median(ns):.1f} ({min(ns):.1f}-{max(ns):.1f}) | "
                  f"{m('ev11'):.1f} | {m('ev2d'):.3f} | {m('ev3'):.3f} | {m('ev17'):.3f} | {m('ev2a'):.3f} | {m('contig_frac'):.2f} | "
                  f"{m('mb2_regions'):.0f} |")
        # pass 1 against pass 2
        d1 = [d["ns_med"] for k in keys for d in runs[k] if d["pass"] == 1]
        d2 = [d["ns_med"] for k in keys for d in runs[k] if d["pass"] == 2]
        if len(d1) == len(d2) and d1:
            diff = [b - a for a, b in zip(d1, d2)]
            print(f"\nPass 2 minus pass 1 over all slots and runs: median {st.median(diff):+.2f} ns, "
                  f"range {min(diff):+.2f} to {max(diff):+.2f} ns (n = {len(diff)}).\n")


def exp_v():
    path = os.path.join(DEV, "expV.log")
    if not os.path.exists(path):
        return
    runs = collections.OrderedDict()
    cur = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("## "):
                d = kv(line)
                cur = (int(d["rep"]), int(d["size_mb"]), d["pick"])
                runs[cur] = []
            elif line.startswith("slot=") and cur is not None:
                d = kv(line)
                d["_slot"] = int(str(line.split()[0].split("=")[1]), 16)
                runs[cur].append(d)
    print("## Exp V: host pages that share a 2 MiB region with the memory of the running protected VM, against pages that do not\n")
    vmf = os.path.join(DEV, "vm-frames-n80.txt")
    if os.path.exists(vmf):
        print("Where the VM's memory sits (vm-frames-n80.txt):\n")
        print("```")
        with open(vmf) as fh:
            for line in fh:
                if line.startswith(("mapping", "  slot", "wrote")):
                    print(line.rstrip()[:160])
        print("```\n")
    print("class shared = the page lies in a 2 MiB region that also holds VM pages (host stage-2 split to 4 KiB there); "
          "class clear = it does not.  Same process, same GiB slot, same way of picking pages.  "
          "ns = median of 5 full cycles; two passes per set.\n")
    for (size, pick) in sorted({(k[1], k[2]) for k in runs}):
        keys = [k for k in runs if k[1] == size and k[2] == pick]
        print(f"### {size} MB per set, pages picked: {'lowest addresses' if pick == 'low' else 'spread evenly'}, {len(keys)} run(s)\n")
        print("| slot (physical base) | class | measurements | ns: median (min-max) | cycles | page walks per access | L1 refills | "
              "L2 refills | L3 refills | distinct 2 MiB regions | shared minus clear: ns | cycles | L2 refills |")
        print("|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        slots = sorted({d["_slot"] for k in keys for d in runs[k]})
        diffs = []
        for s in slots:
            stat = {}
            for cls in ("clear", "shared"):
                rs = [d for k in keys for d in runs[k] if d["_slot"] == s and d["class"] == cls]
                if rs:
                    stat[cls] = rs
            for cls in ("clear", "shared"):
                if cls not in stat:
                    continue
                rs = stat[cls]
                ns = [d["ns_med"] for d in rs]
                m = lambda key, rr=rs: st.median(d[key] for d in rr)
                tail = " | | |"
                if cls == "shared" and "clear" in stat:
                    c = stat["clear"]
                    mc = lambda key: st.median(d[key] for d in c)
                    tail = f" {m('ns_med') - mc('ns_med'):+.1f} | {m('ev11') - mc('ev11'):+.1f} | {m('ev17') - mc('ev17'):+.3f} |"
                    diffs.append((s, m('ns_med') - mc('ns_med'), m('ev11') - mc('ev11'), m('ev17') - mc('ev17'), m('ev3') - mc('ev3')))
                print(f"| 0x{s << 30:x} | {cls} | {len(rs)} | {st.median(ns):.1f} ({min(ns):.1f}-{max(ns):.1f}) | {m('ev11'):.1f} | "
                      f"{m('ev2d'):.3f} | {m('ev3'):.3f} | {m('ev17'):.3f} | {m('ev2a'):.3f} | {m('mb2_regions'):.0f} |{tail}")
        clear_all = [d["ns_med"] for k in keys for d in runs[k] if d["class"] == "clear"]
        if clear_all:
            print(f"\nclass clear over all slots: {min(clear_all):.1f}-{max(clear_all):.1f} ns, median {st.median(clear_all):.1f} ns "
                  f"(n = {len(clear_all)}).")
        if diffs:
            print("shared minus clear, per slot: " + "; ".join(f"0x{s << 30:x}: {a:+.1f} ns, {b:+.1f} cycles, {c:+.3f} L2 refills, {e:+.3f} L1 refills"
                                                                 for s, a, b, c, e in diffs) + ".")
        print()


def exp_v2():
    path = os.path.join(DEV, "expV2.log")
    if not os.path.exists(path):
        return
    rows = []
    size = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("## "):
                size = kv(line)["size_mb"]
            elif line.startswith("slot=") and size is not None:
                d = kv(line)
                d["_slot"] = int(str(line.split()[0].split("=")[1]), 16)
                d["_size"] = size
                rows.append(d)
    print("## Exp V2: shared against clear at working-set sizes from 2 MB to 64 MB\n")
    print("Per size: class clear over all slots (median and range of the per-set medians, two passes per set) and class shared "
          "over the slots that have enough shared pages.  extra = shared median minus clear median.  Below 6 MB the chase "
          "needs no page walks; there the spread of class clear across slots (different L3 placement) is the noise level.\n")
    print("| size | pages | page walks per access: clear / shared | clear: ns median (min-max), n | shared: ns median (min-max), n, slots | "
          "extra ns | extra cycles | extra cycles per walk | L2 refills: clear / shared | extra L2 refills |")
    print("|---:|---:|---|---|---|---:|---:|---:|---|---:|")
    m = lambda rs, key: st.median(r[key] for r in rs)
    for sz in sorted({r["_size"] for r in rows}):
        clear = [r for r in rows if r["_size"] == sz and r["class"] == "clear"]
        sh = [r for r in rows if r["_size"] == sz and r["class"] == "shared"]
        if not clear or not sh:
            continue
        cn = [r["ns_med"] for r in clear]
        sn = [r["ns_med"] for r in sh]
        slots = ", ".join(f"0x{s << 30:x}" for s in sorted({r["_slot"] for r in sh}))
        dc = m(sh, "ev11") - m(clear, "ev11")
        w = m(sh, "ev2d")
        per = f"{dc / w:.1f}" if w > 0.02 else "no walks"
        print(f"| {sz:g} MB | {int(sz * 256)} | {m(clear, 'ev2d'):.3f} / {w:.3f} | {st.median(cn):.1f} ({min(cn):.1f}-{max(cn):.1f}), {len(cn)} | "
              f"{st.median(sn):.1f} ({min(sn):.1f}-{max(sn):.1f}), {len(sn)}, {slots} | {st.median(sn) - st.median(cn):+.1f} | {dc:+.1f} | {per} | "
              f"{m(clear, 'ev17'):.3f} / {m(sh, 'ev17'):.3f} | {m(sh, 'ev17') - m(clear, 'ev17'):+.3f} |")
    print()


def exp_v3():
    """Exp V2 and its repetitions (Exp V3): one line per size, one value per page set (run)."""
    runs = []
    for name, tag in (("expV2.log", "V2"), ("expV3.log", "V3")):
        path = os.path.join(DEV, name)
        if not os.path.exists(path):
            continue
        hdr = None
        with open(path) as fh:
            for line in fh:
                if line.startswith("## "):
                    hdr = kv(line)
                    hdr["_rows"] = []
                    hdr["_tag"] = tag
                    hdr.setdefault("seed", 31.0)
                    runs.append(hdr)
                elif line.startswith("slot=") and hdr is not None:
                    d = kv(line)
                    d["_slot"] = int(str(line.split()[0].split("=")[1]), 16)
                    hdr["_rows"].append(d)
    if not any(r["_tag"] == "V3" for r in runs):
        return
    print("## Exp V3: the shared-against-clear comparison repeated with other page sets\n")
    print("From 6 MB upward one page set of class shared per run (two passes), all from slot 0x20c0000000 and all drawn from the "
          "same population of about 50 thousand pool pages; below 6 MB several slots have a shared set.  Class clear from every "
          "slot of the same run.  extra = median of the shared sets minus the median of class clear in the same run; 'same slot' "
          "compares each shared set with the clear set of its own slot (median over the slots).  Runs: V2 and V3; the seed "
          "changes the order of the chase, not which pages are selected.\n")
    m = lambda rs, key: st.median(r[key] for r in rs)
    for pick in ("even", "low"):
        sel = [r for r in runs if r["pick"] == pick]
        if not sel:
            continue
        print(f"### Pages picked: {'spread evenly over the pool pages of the slot' if pick == 'even' else 'lowest addresses (physically contiguous)'}\n")
        print("| size | runs | slots with a shared set | extra ns per run | median (min-max) | relative | same slot: extra ns per run | "
              "extra cycles per run | page walks per access: clear / shared | extra L2 refills per run | "
              "distinct 2 MiB regions of the shared set |")
        print("|---:|---:|---|---|---|---:|---|---|---|---|---|")
        for sz in sorted({r["size_mb"] for r in sel}):
            ex, exs, cyc, l2, reg, wc, ws, rel, nsl = [], [], [], [], [], [], [], [], []
            for r in sel:
                if r["size_mb"] != sz:
                    continue
                sh = [x for x in r["_rows"] if x["class"] == "shared"]
                cl = [x for x in r["_rows"] if x["class"] == "clear"]
                if not sh or not cl:
                    continue
                # every slot that has a shared set counts (below 6 MB several slots have one)
                ex.append(m(sh, "ns_med") - m(cl, "ns_med"))
                rel.append(100 * (m(sh, "ns_med") / m(cl, "ns_med") - 1))
                per_slot = []
                for slot in sorted({x["_slot"] for x in sh}):
                    same = [x for x in cl if x["_slot"] == slot]
                    if same:
                        per_slot.append(m([x for x in sh if x["_slot"] == slot], "ns_med") - m(same, "ns_med"))
                if per_slot:
                    exs.append(st.median(per_slot))
                cyc.append(m(sh, "ev11") - m(cl, "ev11"))
                l2.append(m(sh, "ev17") - m(cl, "ev17"))
                reg.append(m(sh, "mb2_regions"))
                nsl.append(len({x["_slot"] for x in sh}))
                wc.append(m(cl, "ev2d"))
                ws.append(m(sh, "ev2d"))
            if not ex:
                continue
            print(f"| {sz:g} MB | {len(ex)} | {', '.join(str(x) for x in nsl)} | {', '.join(f'{x:+.1f}' for x in ex)} | {st.median(ex):+.1f} ({min(ex):+.1f} to {max(ex):+.1f}) | "
                  f"{st.median(rel):+.1f}% | {', '.join(f'{x:+.1f}' for x in exs)} | {', '.join(f'{x:+.1f}' for x in cyc)} | "
                  f"{st.median(wc):.3f} / {st.median(ws):.3f} | {', '.join(f'{x:+.2f}' for x in l2)} | {', '.join(f'{x:.0f}' for x in reg)} |")
        print()


# GiB slots (PFN >> 18) that held no VM page, no memory-region boundary and no hypervisor pool on
# 2026-09-30, i.e. the only ones that could still be mapped by one 1 GiB host stage-2 block
GB_CANDIDATES = (0x8b, 0x8c)


def exp_slots():
    """Slot effect in the random chase: the two 1 GiB-candidate slots against the other slots."""
    runs = collections.defaultdict(list)
    for name in ("expS.log", "expV.log", "expV2.log", "expV3.log"):
        path = os.path.join(DEV, name)
        if not os.path.exists(path):
            continue
        hdr = None
        n = 0
        with open(path) as fh:
            for line in fh:
                if line.startswith("## "):
                    hdr = kv(line)
                    n += 1
                elif line.startswith("slot=") and hdr is not None:
                    d = kv(line)
                    if d.get("class") == "shared":
                        continue
                    d["_slot"] = int(str(line.split()[0].split("=")[1]), 16)
                    runs[(name, n, hdr.get("pick", "low"), d["size_mb"])].append(d)
    if not runs:
        return
    print("## Slot effect in the random chase: the two GiB slots that can still be 1 GiB stage-2 blocks against the others\n")
    print("Slots 0x22c0000000 and 0x2300000000 hold no VM page, no memory-region boundary and no hypervisor pool; every other "
          "slot is mapped by 2 MiB blocks at most (kernel source plus vm-frames-n80.txt; the stage-2 table itself was not read).  "
          "Per run: median over these two slots minus median over the other slots, class clear (or all).  Logs: expS, expV, expV2, expV3.\n")
    print("| size | pages picked | runs | difference per run (ns) | median ns | median cycles | median L2 refills | page walks per access |")
    print("|---:|---|---:|---|---:|---:|---:|---:|")
    m = lambda rs, key: st.median(r[key] for r in rs)
    for pick in ("even", "low"):
        for sz in sorted({k[3] for k in runs if k[2] == pick}):
            dn, dc, dl, w = [], [], [], []
            for k, rows in sorted(runs.items(), key=lambda kv_: str(kv_[0])):
                if k[2] != pick or k[3] != sz:
                    continue
                a = [r for r in rows if r["_slot"] in GB_CANDIDATES]
                b = [r for r in rows if r["_slot"] not in GB_CANDIDATES]
                if not a or not b:
                    continue
                dn.append(m(a, "ns_med") - m(b, "ns_med"))
                dc.append(m(a, "ev11") - m(b, "ev11"))
                dl.append(m(a, "ev17") - m(b, "ev17"))
                w.append(m(b, "ev2d"))
            if dn:
                print(f"| {sz:g} MB | {'spread evenly' if pick == 'even' else 'lowest addresses'} | {len(dn)} | "
                      f"{' '.join(f'{x:+.1f}' for x in dn)} | {st.median(dn):+.2f} | {st.median(dc):+.2f} | {st.median(dl):+.3f} | {st.median(w):.3f} |")
    print()


def exp_z():
    rows = frames2_rows("expZ.log")
    if not rows:
        return
    print("## Exp Z: a chase dominated by address translation (frames2 tlb<L>: another page on every hop, L cache lines per page)\n")
    print("cycles = user-mode CPU cycles per hop (median of the per-set medians, two passes per set).  '2 MiB slots' are all "
          "slots except 0x22c0000000 and 0x2300000000, the two that can still be 1 GiB stage-2 blocks.  shared = pages in "
          "2 MiB regions that also hold pages of the running VM (4 KiB stage-2 leaves).\n")
    cfgs = sorted({(r["_size"], r["stride"]) for r in rows}, key=lambda c: (c[0] * 256 * c[1], c[0]))
    m = lambda rs, key: st.median(r[key] for r in rs)
    print("| pages x lines per page | lines | class clear, 2 MiB slots: cycles (ns) | page walks | L2 refills | "
          "1 GiB-candidate slots minus 2 MiB slots, per run: cycles | median | class shared minus clear, per run: cycles | median | "
          "extra L2 refills of class shared |")
    print("|---|---:|---|---:|---:|---|---:|---|---:|---:|")
    base = {}
    for size, lines in cfgs:
        sel = [r for r in rows if r["_size"] == size and r["stride"] == lines]
        seeds = sorted({r["seed_"] for r in sel}) if "seed_" in sel[0] else [None]
        dg, ds, dl = [], [], []
        for seed in seeds:
            run = [r for r in sel if r.get("seed_") == seed]
            clear = [r for r in run if r["class"] in ("clear", "all")]
            two = [r for r in clear if r["_slot"] not in GB_CANDIDATES]
            one = [r for r in clear if r["_slot"] in GB_CANDIDATES]
            sh = [r for r in run if r["class"] == "shared"]
            if two and one:
                dg.append(m(one, "ev11") - m(two, "ev11"))
            if two and sh:
                ds.append(m(sh, "ev11") - m(two, "ev11"))
                dl.append(m(sh, "ev17") - m(two, "ev17"))
        two = [r for r in sel if r["class"] in ("clear", "all") and r["_slot"] not in GB_CANDIDATES]
        base[(size, lines)] = m(two, "ev11")
        print(f"| {int(size * 256)} x {lines:g} | {int(size * 256 * lines)} | {m(two, 'ev11'):.2f} ({m(two, 'ns_med'):.2f}) | "
              f"{m(two, 'ev2d'):.3f} | {m(two, 'ev17'):.3f} | {' '.join(f'{x:+.2f}' for x in dg)} | "
              + (f"{st.median(dg):+.2f}" if dg else "") + f" | {' '.join(f'{x:+.1f}' for x in ds)} | "
              + (f"{st.median(ds):+.1f}" if ds else "") + " | " + (f"{st.median(dl):+.3f}" if dl else "") + " |")
    ref = base.get((4.0, 4.0))
    if ref is not None:
        print("\nCost of one page walk with a block-mapped stage-2 (class clear, 2 MiB slots): cycles per hop minus the "
              f"no-walk reference (1024 pages x 4 lines, {ref:.2f} cycles), for configurations with the same 4096 lines of data:\n")
        for size, lines in cfgs:
            if int(size * 256 * lines) == 4096 and (size, lines) != (4.0, 4.0):
                print(f"- {int(size * 256)} pages x {lines:g} lines: {base[(size, lines)] - ref:+.1f} cycles per hop")
    print()


def exp_w():
    path = os.path.join(DEV, "expW.log")
    if not os.path.exists(path):
        return
    rows = []
    hdr = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("## "):
                hdr = kv(line)
            elif line.startswith("slot=") and hdr is not None:
                d = kv(line)
                d["_slot"] = int(str(line.split()[0].split("=")[1]), 16)
                d["_size"] = hdr["size_mb"]
                d["_pick"] = hdr["pick"]
                rows.append(d)
    print("## Exp W: sequential chase (stride 256) over the same kind of page set in sorted and in shuffled virtual order, by page class\n")
    print("sorted = virtual order follows ascending physical address; shuffled = the same selection rule, pages mapped in a random "
          "virtual order.  clear = stage-2 block mappings; shared = 4 KiB stage-2 leaves (2 MiB regions shared with the VM).  "
          "ns = median over sets (slots) and the two passes.\n")
    print("selection step = pool pages of the class in the slot per selected page (1 for the lowest-address sets): with evenly "
          "spread pages every step-th pool page in ascending frame order is taken.  It is not a physical distance; frame "
          "numbers per page were not logged.\n")
    print("| size | pages picked | class | slots | sorted: ns (min-max) | shuffled: ns (min-max) | shuffled vs sorted | "
          "page walks per access: sorted / shuffled | L2 refills: sorted / shuffled | adjacency when sorted | selection step (min-max) |")
    print("|---:|---|---|---:|---|---|---:|---|---|---:|---|")
    m = lambda rs, key: st.median(r[key] for r in rs)
    for sz in sorted({r["_size"] for r in rows}):
        for pick in ("low", "even"):
            for cls in ("clear", "shared"):
                so = [r for r in rows if r["_size"] == sz and r["_pick"] == pick and r["class"] == cls and r["order"] == "sorted"]
                sh = [r for r in rows if r["_size"] == sz and r["_pick"] == pick and r["class"] == cls and r["order"] == "shuffled"]
                if not so or not sh:
                    continue
                a = [r["ns_med"] for r in so]
                b = [r["ns_med"] for r in sh]
                nslots = len({r["_slot"] for r in so})
                print(f"| {sz:g} MB | {'lowest addresses' if pick == 'low' else 'spread evenly'} | {cls} | {nslots} | "
                      f"{st.median(a):.2f} ({min(a):.2f}-{max(a):.2f}) | {st.median(b):.2f} ({min(b):.2f}-{max(b):.2f}) | "
                      f"{100 * (st.median(b) / st.median(a) - 1):+.1f}% | {m(so, 'ev2d'):.4f} / {m(sh, 'ev2d'):.4f} | "
                      f"{m(so, 'ev17'):.3f} / {m(sh, 'ev17'):.3f} | {m(so, 'contig_frac'):.2f} | "
                      + ("1" if pick == "low" else
                         f"{min(r['frames_in_class'] for r in so) / (sz * 256):.1f}-{max(r['frames_in_class'] for r in so) / (sz * 256):.1f}")
                      + " |")
    # the same slot for both classes, where shared exists
    print("\nSame slot, both classes (slot 0x20c0000000 where available).  With evenly spread pages the two classes of one "
          "slot have different selection steps, so this comparison is not at equal spacing:\n")
    print("| size | pages picked | order | clear: ns | shared: ns | shared vs clear |")
    print("|---:|---|---|---:|---:|---:|")
    for sz in sorted({r["_size"] for r in rows}):
        for pick in ("low", "even"):
            for order in ("sorted", "shuffled"):
                slots = {r["_slot"] for r in rows if r["_size"] == sz and r["_pick"] == pick and r["class"] == "shared" and r["order"] == order}
                for s in sorted(slots):
                    c = [r["ns_med"] for r in rows if r["_size"] == sz and r["_pick"] == pick and r["class"] == "clear"
                         and r["order"] == order and r["_slot"] == s]
                    h = [r["ns_med"] for r in rows if r["_size"] == sz and r["_pick"] == pick and r["class"] == "shared"
                         and r["order"] == order and r["_slot"] == s]
                    if c and h:
                        print(f"| {sz:g} MB | {'lowest addresses' if pick == 'low' else 'spread evenly'} | {order} | {st.median(c):.2f} | "
                              f"{st.median(h):.2f} | {100 * (st.median(h) / st.median(c) - 1):+.1f}% |")
    print()


def frames2_rows(name):
    """frames2 output lines, each with the fields of the '## ' header line that precedes it."""
    path = os.path.join(DEV, name)
    if not os.path.exists(path):
        return []
    rows = []
    hdr = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("## "):
                hdr = kv(line)
            elif line.startswith("slot=") and hdr is not None:
                d = kv(line)
                d["_slot"] = int(str(line.split()[0].split("=")[1]), 16)
                d["_size"] = hdr["size_mb"]
                d["_pick"] = hdr["pick"]
                d["seed_"] = hdr.get("seed", hdr.get("rep"))
                d.setdefault("chase", "loop")
                rows.append(d)
    return rows


def exp_x():
    rows = probe_rows("expX1.log")
    ref = lmbench_sweeps("expX3.log")
    if not rows:
        return
    print("## Exp X: the form of the timed loop (one load instruction in a loop against lmbench's 100 loads in a row)\n")
    print("X1 = probe3, fresh process per point, chain rewritten before every interval; ns = minimum of 11 intervals, "
          "median over the processes.  X3 = lmbench's own lat_mem_rd in the same session (3 sweeps, 4 KiB pages).  "
          "adjacency = fraction of virtually adjacent pages that are physically adjacent, in either direction.\n")
    print("### Sequential, stride 256\n")
    print("| size | n | loop: ns (min-max) | unrolled: ns (min-max) | lmbench's own: ns (min-max) | unrolled / loop | "
          "unrolled / lmbench | loop / lmbench | cycles: loop / unrolled | median adjacency |")
    print("|---:|---:|---|---|---|---:|---:|---:|---|---:|")
    sizes = sorted({r["size_mb"] for r in rows if r["mode"] == "seq"})
    lm = collections.defaultdict(list)
    for _, per_stride in ref:
        for sz, ns in per_stride.get(256, {}).items():
            lm[sz].append(ns)

    def near(sz):
        # lmbench prints sizes with 5 decimals (0.02344), probe3 with 3 (0.023)
        for k in lm:
            if abs(k - sz) <= 0.001:
                return lm[k]
        return []
    for sz in sizes:
        lo = [r for r in rows if r["mode"] == "seq" and r["size_mb"] == sz and r["chase"] == "loop"]
        un = [r for r in rows if r["mode"] == "seq" and r["size_mb"] == sz and r["chase"] == "unrolled"]
        a = [r["ns_min"] for r in lo]
        b = [r["ns_min"] for r in un]
        c = near(sz)
        adj = st.median(r["contig_frac"] + r["rcontig_frac"] for r in lo + un)
        label = f"{sz:g} MB" if sz >= 0.1 else f"{sz * 1024:.0f} KiB"
        print(f"| {label} | {len(a)} + {len(b)} | {st.median(a):.3f} ({min(a):.3f}-{max(a):.3f}) | "
              f"{st.median(b):.3f} ({min(b):.3f}-{max(b):.3f}) | "
              + (f"{st.median(c):.3f} ({min(c):.3f}-{max(c):.3f})" if c else "") + " | "
              f"{st.median(b) / st.median(a):.3f} | " + (f"{st.median(b) / st.median(c):.3f}" if c else "") + " | "
              + (f"{st.median(a) / st.median(c):.3f}" if c else "")
              + f" | {st.median(r['ev11'] for r in lo):.2f} / {st.median(r['ev11'] for r in un):.2f} | {adj:.2f} |")
    print("\n### Random (lmbench -t pattern, stride 16)\n")
    print("| size | seeds | loop: ns (min-max) | unrolled: ns (min-max) | unrolled / loop |")
    print("|---:|---:|---|---|---:|")
    for sz in sorted({r["size_mb"] for r in rows if r["mode"] == "rand"}):
        a = [r["ns_min"] for r in rows if r["mode"] == "rand" and r["size_mb"] == sz and r["chase"] == "loop"]
        b = [r["ns_min"] for r in rows if r["mode"] == "rand" and r["size_mb"] == sz and r["chase"] == "unrolled"]
        print(f"| {sz:g} MB | {len(a)} | {st.median(a):.2f} ({min(a):.2f}-{max(a):.2f}) | "
              f"{st.median(b):.2f} ({min(b):.2f}-{max(b):.2f}) | {st.median(b) / st.median(a):.3f} |")

    h = [per_stride for hd, per_stride in lmbench_sweeps("expH-seq256.log") if hd.get("thp") == "off"]
    rr = probe_rows("expR.log")
    if h and ref:
        print("\n### lmbench's own lat_mem_rd, stride 256: Exp H (18:45 to 19:13) against Exp X3 (19:56 to 20:07), same platform state\n")
        print("Between the two the free memory of the machine became fragmented (hours of experiments that shuffle "
              "and free gigabytes of pages).  The adjacency column is what probe3, which allocates in the same "
              "way, recorded at about the same time (Exp R for the earlier, Exp X1 for the later session).\n")
        print("| size | Exp H: ns, median of the sweeps | adjacency then (Exp R) | Exp X3: ns, median of 3 | adjacency now (Exp X1) | change |")
        print("|---:|---:|---:|---:|---:|---:|")
        for sz in (4.0, 6.0, 8.0, 12.0, 16.0, 64.0):
            a = [s[256][sz] for s in h if sz in s.get(256, {})]
            c = near(sz)
            ra = [r["contig_frac"] + r["rcontig_frac"] for r in rr if r["size_mb"] == sz]
            xa = [r["contig_frac"] + r["rcontig_frac"] for r in rows if r["mode"] == "seq" and r["size_mb"] == sz]
            if a and c:
                print(f"| {sz:g} MB | {st.median(a):.2f} | {st.median(ra):.2f} | {st.median(c):.2f} | {st.median(xa):.2f} | "
                      f"{100 * (st.median(c) / st.median(a) - 1):+.1f}% |")

    x2 = frames2_rows("expX2.log")
    if x2:
        print("\n### X2: the same pages in sorted and in shuffled virtual order (as Exp W), sequential stride 256, by loop form\n")
        print("ns = median of 5 full cycles, median over slots and the two passes.  adjacent pages = lowest addresses of the "
              "slot; non-adjacent pages = spread evenly over the slot's pool pages.\n")
        print("| size | loop form | class | slots | adjacent pages, sorted: ns (min-max) | same pages, shuffled: ns (min-max) | "
              "shuffled vs sorted | non-adjacent pages, sorted / shuffled: ns | adjacency of the sorted adjacent set |")
        print("|---:|---|---|---:|---|---|---:|---|---:|")
        for sz in sorted({r["_size"] for r in x2}):
            for chase in ("loop", "unrolled"):
                for cls in ("clear", "shared"):
                    def sel(pick, order):
                        return [r for r in x2 if r["_size"] == sz and r["chase"] == chase and r["class"] == cls
                                and r["_pick"] == pick and r["order"] == order]
                    so, sh = sel("low", "sorted"), sel("low", "shuffled")
                    if not so or not sh:
                        continue
                    a = [r["ns_med"] for r in so]
                    b = [r["ns_med"] for r in sh]
                    es, eh = sel("even", "sorted"), sel("even", "shuffled")
                    ev = (f"{st.median(r['ns_med'] for r in es):.2f} / {st.median(r['ns_med'] for r in eh):.2f}"
                          if es and eh else "")
                    print(f"| {sz:g} MB | {chase} | {cls} | {len({r['_slot'] for r in so})} | "
                          f"{st.median(a):.2f} ({min(a):.2f}-{max(a):.2f}) | {st.median(b):.2f} ({min(b):.2f}-{max(b):.2f}) | "
                          f"{100 * (st.median(b) / st.median(a) - 1):+.1f}% | {ev} | {st.median(r['contig_frac'] for r in so):.2f} |")
    print()


def exp_y():
    rows = frames2_rows("expY.log")
    if not rows:
        return
    print("## Exp Y: the layout effect at 8 MB for every stride (frames2, lmbench's loop form, physically adjacent pages)\n")
    print("sorted = virtual order follows ascending physical address; shuffled = the same pages in a random virtual "
          "order.  ns = median of 5 full cycles, median over slots and the two passes.\n")
    print("| stride | accesses per page | slots | sorted: ns (min-max) | shuffled: ns (min-max) | shuffled - sorted (ns) | "
          "shuffled vs sorted | per page crossing (ns) | page walks per access: sorted / shuffled | "
          "L2 refills: sorted / shuffled | L3 refills: sorted / shuffled |")
    print("|---:|---:|---:|---|---|---:|---:|---:|---|---|---|")
    m = lambda rs, key: st.median(r[key] for r in rs)
    for stride in sorted({r["stride"] for r in rows}):
        so = [r for r in rows if r["stride"] == stride and r["order"] == "sorted"]
        sh = [r for r in rows if r["stride"] == stride and r["order"] == "shuffled"]
        if not so or not sh:
            continue
        a = [r["ns_med"] for r in so]
        b = [r["ns_med"] for r in sh]
        d = st.median(b) - st.median(a)
        print(f"| {stride:g} | {4096 / stride:g} | {len({r['_slot'] for r in so})} | {st.median(a):.2f} ({min(a):.2f}-{max(a):.2f}) | "
              f"{st.median(b):.2f} ({min(b):.2f}-{max(b):.2f}) | {d:+.2f} | {100 * (st.median(b) / st.median(a) - 1):+.1f}% | "
              f"{d * 4096 / stride:+.1f} | {m(so, 'ev2d'):.4f} / {m(sh, 'ev2d'):.4f} | {m(so, 'ev17'):.3f} / {m(sh, 'ev17'):.3f} | "
              f"{m(so, 'ev2a'):.3f} / {m(sh, 'ev2a'):.3f} |")
    print()


def ols2(x1, x2, y):
    """Least squares y = a + b1 x1 + b2 x2 -> (a, b1, b2, se(b1), se(b2), R^2)."""
    n = len(y)
    m1, m2, my = st.mean(x1), st.mean(x2), st.mean(y)
    s11 = sum((a - m1) ** 2 for a in x1)
    s22 = sum((a - m2) ** 2 for a in x2)
    s12 = sum((a - m1) * (b - m2) for a, b in zip(x1, x2))
    s1y = sum((a - m1) * (c - my) for a, c in zip(x1, y))
    s2y = sum((a - m2) * (c - my) for a, c in zip(x2, y))
    det = s11 * s22 - s12 ** 2
    b1 = (s1y * s22 - s2y * s12) / det
    b2 = (s2y * s11 - s1y * s12) / det
    a = my - b1 * m1 - b2 * m2
    sse = sum((c - (a + b1 * u + b2 * v)) ** 2 for u, v, c in zip(x1, x2, y))
    sst = sum((c - my) ** 2 for c in y)
    s2 = sse / (n - 3)
    return a, b1, b2, math.sqrt(s2 * s22 / det), math.sqrt(s2 * s11 / det), 1 - sse / sst


def ols1(x, y):
    """Least squares y = a + b x -> (a, b, se(b))."""
    n = len(y)
    mx, my = st.mean(x), st.mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    a = my - b * mx
    sse = sum((c - (a + b * u)) ** 2 for u, c in zip(x, y))
    return a, b, math.sqrt(sse / (n - 2) / sxx)


def tagged_rows(path, tag):
    """Lines 'TAG key=value ...' of a probe3 log; slots= is split into the shares used below."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            if not line.startswith(tag + " ") or "ns_min=" not in line:
                continue
            d = kv(line)
            if isinstance(d.get("slots"), str):
                slots = {int(a, 16): int(b) for a, b in (x.split(":") for x in d["slots"].split(","))}
                n = sum(slots.values())
                d["_cand"] = sum(slots.get(c, 0) for c in GB_CANDIDATES) / n
                d["_vmslot"] = slots.get(0x83, 0) / n
            out.append(d)
    return out


def cfg_label(r):
    return f"{int(r['pages'])} x {int(r['stride'])}"


def exp_n():
    a = tagged_rows(os.path.join(DEV, "expN-n80.log"), "N")
    b = tagged_rows(os.path.join(D80, "expN-d80f3.log"), "N")
    a = [r for r in a if r["mode"] == "tlb"]
    b = [r for r in b if r["mode"] == "tlb"]
    if not a or not b:
        return
    print("## Exp N: the translation-only chase as an unprivileged program, with and without a host stage-2\n")
    print("Same source (probe3 tlb) on the N80 (kvm-arm.mode=protected, kernel 6.6.0-79) and on a D80F3 workstation with the same "
          "cores (KVM in VHE mode, no host stage-2, kernel 7.0.0-34).  cycles = 4 x ns / (ns per hop of a chase inside the L1 cache, "
          "taken in the same process); the PMU columns exist for the N80 only.  Median over the processes (min-max).  "
          "Pages are first touched in chain order here; see Exp N4 for what that does to the 4096 x 1 row.\n")
    print("| pages x lines per page | data lines | N80: cycles | N80 PMU: cycles | page walks per hop | L2 refills per hop (min-max) | "
          "D80F3: cycles | per CPU | N80 - D80F3 |")
    print("|---|---:|---|---:|---:|---|---|---|---:|")
    cfgs = sorted({(r["pages"], r["stride"]) for r in a}, key=lambda c: (c[0] * c[1], c[0]))
    for pg, ln in cfgs:
        x = [r for r in a if (r["pages"], r["stride"]) == (pg, ln)]
        y = [r for r in b if (r["pages"], r["stride"]) == (pg, ln)]
        if not x or not y:
            continue
        ca = [r["cyc_est"] for r in x]
        cb = [r["cyc_est"] for r in y]
        per = " ".join(f"{st.median(r['cyc_est'] for r in y if r['cpu'] == c):.2f}" for c in sorted({r["cpu"] for r in y}))
        l2 = [r["ev17"] for r in x]
        print(f"| {int(pg)} x {int(ln)} | {int(pg * ln)} | {st.median(ca):.2f} ({min(ca):.2f}-{max(ca):.2f}), {len(ca)} | "
              f"{st.median(r['ev11'] for r in x):.2f} | {st.median(r['ev2d'] for r in x):.3f} | {st.median(l2):.3f} ({min(l2):.3f}-{max(l2):.3f}) | "
              f"{st.median(cb):.2f} ({min(cb):.2f}-{max(cb):.2f}), {len(cb)} | {per} | {st.median(ca) - st.median(cb):+.2f} |")
    print()


def exp_n2():
    rows = tagged_rows(os.path.join(DEV, "expN2.log"), "N2")
    if not rows:
        return
    print("## Exp N2: the same chase as root, with other frames in every repetition\n")
    print("Before each repetition a stopped process holds back (repetition - 1) x 192 MB, so the probe gets other frames.  "
          "share = share of the pages of the working set in the two 1 GiB-candidate slots (0x22c0000000, 0x2300000000); "
          "regions = distinct 2 MiB regions of the working set.  One process per cell.\n")
    cfgs = sorted({(r["pages"], r["stride"]) for r in rows}, key=lambda c: (-c[0] * c[1], -c[0]))
    print("| rep | held back | " + " | ".join(f"{int(p)} x {int(l)}: share | regions | cycles | walks | L2 refills" for p, l in cfgs) + " |")
    print("|---:|---:|" + "---:|" * (5 * len(cfgs)))
    for rep in sorted({r["rep"] for r in rows}):
        cells = []
        for pg, ln in cfgs:
            r = [x for x in rows if x["rep"] == rep and (x["pages"], x["stride"]) == (pg, ln)][0]
            cells.append(f"{r['_cand']:.3f} | {int(r['mb2_regions'])} | {r['ev11']:.2f} | {r['ev2d']:.3f} | {r['ev17']:.3f}")
        hold = [x for x in rows if x["rep"] == rep][0]["hold_mb"]
        print(f"| {int(rep)} | {int(hold)} MB | " + " | ".join(cells) + " |")
    print("\nPer configuration, over the 12 repetitions:\n")
    print("| pages x lines | cycles (min-max) | r(cycles, share) | r(cycles, regions) | r(share, regions) | r(cycles, L2 refills) | "
          "cycles = a + b x share + c x regions/100: a | b (s.e.) | c (s.e.) | R^2 |")
    print("|---|---|---:|---:|---:|---:|---:|---|---|---:|")
    for pg, ln in cfgs:
        sel = [x for x in rows if (x["pages"], x["stride"]) == (pg, ln)]
        y = [x["ev11"] for x in sel]
        f = [x["_cand"] for x in sel]
        g = [x["mb2_regions"] / 100 for x in sel]
        a0, b1, b2, se1, se2, r2 = ols2(f, g, y)
        print(f"| {int(pg)} x {int(ln)} | {min(y):.2f}-{max(y):.2f} | {pearson(y, f):+.2f} | {pearson(y, g):+.2f} | {pearson(f, g):+.2f} | "
              f"{pearson(y, [x['ev17'] for x in sel]):+.2f} | {a0:.2f} | {b1:+.2f} ({se1:.2f}) | {b2:+.2f} ({se2:.2f}) | {r2:.2f} |")
    print()


def exp_n3():
    path = os.path.join(DEV, "expN3.log")
    if not os.path.exists(path):
        return
    rows = []
    hdr = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("## "):
                hdr = kv(line)
            elif line.startswith("mix=") and hdr is not None:
                d = kv(line)
                d["_pair"] = str(line.split()[0].split("=")[1])
                d["_seed"] = hdr["seed"]
                rows.append(d)
    if not rows:
        return
    print("## Exp N3: page sets that mix two GiB slots in a fixed proportion (frames2, 2048 pages x 1 line, class clear)\n")
    print("A = a slot that can still be a 1 GiB stage-2 block, B = a slot mapped with 2 MiB blocks.  cycles = median over the "
          "three repetitions of the mean of the two passes (min-max of the repetitions).  'minus 0%' is taken within each repetition.\n")
    m = lambda rs, key: st.median(r[key] for r in rs)

    def per_seed(pair, pct, size, key="ev11"):
        out = []
        for seed in sorted({r["_seed"] for r in rows}):
            v = [r[key] for r in rows if r["_pair"] == pair and r["pct_a"] == pct and r["size_mb"] == size and r["_seed"] == seed]
            if v:
                out.append(st.mean(v))
        return out

    print("| A : B | share of A | cycles (min-max) | minus 0%, per repetition | median | linear between the 0% and 100% medians | "
          "page walks per hop | L2 refills per hop | 2 MiB regions |")
    print("|---|---:|---|---|---:|---:|---:|---:|---:|")
    main_pairs = [p for p in ("0x8b:0x88", "0x8c:0x89") if any(r["_pair"] == p for r in rows)]
    for pair in main_pairs:
        base = per_seed(pair, 0.0, 8.0)
        top = per_seed(pair, 100.0, 8.0)
        for pct in sorted({r["pct_a"] for r in rows if r["_pair"] == pair and r["size_mb"] == 8.0}):
            v = per_seed(pair, pct, 8.0)
            d = [a - b for a, b in zip(v, base)]
            sel = [r for r in rows if r["_pair"] == pair and r["pct_a"] == pct and r["size_mb"] == 8.0]
            lin = (st.median(top) - st.median(base)) * pct / 100
            print(f"| {pair} | {pct:g}% | {st.median(v):.2f} ({min(v):.2f}-{max(v):.2f}) | {' '.join(f'{x:+.2f}' for x in d)} | "
                  f"{st.median(d):+.2f} | {lin:+.2f} | {m(sel, 'ev2d'):.3f} | {m(sel, 'ev17'):.4f} | {m(sel, 'mb2_regions'):.0f} |")
    x, y = [], []
    for pair in main_pairs:
        for seed in sorted({r["_seed"] for r in rows}):
            for pct in sorted({r["pct_a"] for r in rows if r["_pair"] == pair and r["size_mb"] == 8.0}):
                v = [r["ev11"] for r in rows if r["_pair"] == pair and r["pct_a"] == pct and r["size_mb"] == 8.0 and r["_seed"] == seed]
                if v:
                    x.append(pct / 100)
                    y.append(st.mean(v))
    a0, b, se = ols1(x, y)
    a2, b1, b2, se1, se2, r2 = ols2(x, [v * v for v in x], y)
    print(f"\nStraight line through the {len(x)} points of the two pairs: cycles = {a0:.2f} + {b:.2f} (s.e. {se:.2f}) x share.  "
          f"With a quadratic term added: {b1:+.2f} (s.e. {se1:.2f}) x share {b2:+.2f} (s.e. {se2:.2f}) x share^2.\n")
    print("Controls and the no-walk configuration:\n")
    print("| set | configuration | cycles per repetition | median | page walks per hop |")
    print("|---|---|---|---:|---:|")
    for pair, label in (("0x8b:0x8c", "two 1 GiB-candidate slots, half each"), ("0x88:0x89", "two 2 MiB slots, half each")):
        v = per_seed(pair, 50.0, 8.0)
        if v:
            sel = [r for r in rows if r["_pair"] == pair and r["size_mb"] == 8.0]
            print(f"| {label} | 2048 x 1 | {' '.join(f'{c:.2f}' for c in v)} | {st.median(v):.2f} | {m(sel, 'ev2d'):.3f} |")
    for pct in sorted({r["pct_a"] for r in rows if r["size_mb"] == 4.0}):
        v = per_seed("0x8b:0x88", pct, 4.0)
        sel = [r for r in rows if r["_pair"] == "0x8b:0x88" and r["size_mb"] == 4.0 and r["pct_a"] == pct]
        print(f"| 0x8b:0x88, {pct:g}% of A | 1024 x 4 (no walks) | {' '.join(f'{c:.2f}' for c in v)} | {st.median(v):.2f} | {m(sel, 'ev2d'):.3f} |")
    print()


def exp_n4():
    a = tagged_rows(os.path.join(DEV, "expN4-n80.log"), "N4")
    b = tagged_rows(os.path.join(D80, "expN4-d80f3.log"), "N4")
    if not a:
        return
    print("## Exp N4: pages first touched in chain order (as in Exp N and N2) or in ascending virtual order (TLB_PREFAULT=1)\n")
    print("N80 as root with memory held back as in N2, 8 repetitions, one process per cell.  l2over = share of the data lines "
          "that lie in an L2 set holding more than 8 of them, computed from the frame numbers before the timed part.\n")
    cfgs = sorted({(r["pages"], r["stride"]) for r in a}, key=lambda c: (c[0] * c[1] > 4096, c[0], c[1]))
    print("### N80: 4096 x 1, per repetition\n")
    print("| rep | held back | chain order: l2over | L2 refills per hop | cycles | ascending order: l2over | L2 refills per hop | cycles |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    sel = [r for r in a if (r["pages"], r["stride"]) == (4096.0, 1.0)]
    for rep in sorted({r["rep"] for r in sel}):
        c = [r for r in sel if r["rep"] == rep and r["prefault"] == 0][0]
        p = [r for r in sel if r["rep"] == rep and r["prefault"] == 1][0]
        print(f"| {int(rep)} | {int(c['hold_mb'])} MB | {c['l2over']:.3f} | {c['ev17']:.3f} | {c['ev11']:.2f} | "
              f"{p['l2over']:.3f} | {p['ev17']:.3f} | {p['ev11']:.2f} |")
    c0 = [r for r in sel if r["prefault"] == 0]
    print(f"\nChain order, 4096 x 1: r(L2 refills, l2over) = {pearson([r['ev17'] for r in c0], [r['l2over'] for r in c0]):+.3f}, "
          f"r(cycles, L2 refills) = {pearson([r['ev11'] for r in c0], [r['ev17'] for r in c0]):+.3f} over {len(c0)} repetitions.\n")
    print("### N80: all configurations\n")
    print("| pages x lines | data lines | chain order: cycles (min-max) | page walks per hop | L2 refills per hop | "
          "ascending order: cycles (min-max) | page walks per hop | L2 refills per hop | difference of the medians: cycles | walks |")
    print("|---|---:|---|---:|---:|---|---:|---:|---:|---:|")
    for pg, ln in cfgs:
        x = [r for r in a if (r["pages"], r["stride"]) == (pg, ln) and r["prefault"] == 0]
        y = [r for r in a if (r["pages"], r["stride"]) == (pg, ln) and r["prefault"] == 1]
        cx = [r["ev11"] for r in x]
        cy = [r["ev11"] for r in y]
        mm = lambda rs, key: st.median(r[key] for r in rs)
        print(f"| {int(pg)} x {int(ln)} | {int(pg * ln)} | {st.median(cx):.2f} ({min(cx):.2f}-{max(cx):.2f}) | {mm(x, 'ev2d'):.3f} | {mm(x, 'ev17'):.3f} | "
              f"{st.median(cy):.2f} ({min(cy):.2f}-{max(cy):.2f}) | {mm(y, 'ev2d'):.3f} | {mm(y, 'ev17'):.3f} | "
              f"{st.median(cy) - st.median(cx):+.2f} | {mm(y, 'ev2d') - mm(x, 'ev2d'):+.3f} |")
    # cost of one page walk: (cycles - no-walk reference with the same number of data lines) / walks per hop
    ref = {}
    for pf in (0.0, 1.0):
        v = [r["ev11"] for r in a if (r["pages"], r["stride"]) == (1024.0, 2.0) and r["prefault"] == pf]
        if v:
            ref[pf] = st.median(v)
    w = [r for r in a if (r["pages"], r["stride"]) == (2048.0, 1.0)]
    if ref and w:
        print("\n### N80: 2048 x 1, cycles per page walk = (cycles - cycles of 1024 x 2) / page walks per hop\n")
        print("| rep | chain order: share in the two candidate slots | regions | cycles | walks | cycles per walk | "
              "ascending order: share | regions | cycles | walks | cycles per walk |")
        print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        pw = {0.0: [], 1.0: []}
        for rep in sorted({r["rep"] for r in w}):
            cells = []
            for pf in (0.0, 1.0):
                r = [x for x in w if x["rep"] == rep and x["prefault"] == pf][0]
                c = (r["ev11"] - ref[pf]) / r["ev2d"]
                pw[pf].append((r["_cand"], c))
                cells.append(f"{r['_cand']:.3f} | {int(r['mb2_regions'])} | {r['ev11']:.2f} | {r['ev2d']:.3f} | {c:.2f}")
            print(f"| {int(rep)} | " + " | ".join(cells) + " |")
        allp = pw[0.0] + pw[1.0]
        a0, b0, se0 = ols1([p[0] for p in allp], [p[1] for p in allp])
        print(f"\nCycles per walk against the share of pages in the two candidate slots, both orders ({len(allp)} processes): "
              f"{a0:.2f} + {b0:.2f} (s.e. {se0:.2f}) x share; r = {pearson([p[0] for p in allp], [p[1] for p in allp]):+.2f}.\n")
    if b:
        print("### D80F3 (no host stage-2, unprivileged, no PMU): cycles from the L1 reference\n")
        print("| pages x lines | chain order: cycles (min-max), n | ascending order: cycles (min-max), n | difference of the medians | "
              "N80 ascending order - D80F3 ascending order |")
        print("|---|---|---|---:|---:|")
        for pg, ln in cfgs:
            x = [r["cyc_est"] for r in b if (r["pages"], r["stride"]) == (pg, ln) and r["prefault"] == 0]
            y = [r["cyc_est"] for r in b if (r["pages"], r["stride"]) == (pg, ln) and r["prefault"] == 1]
            n80 = [r["cyc_est"] for r in a if (r["pages"], r["stride"]) == (pg, ln) and r["prefault"] == 1]
            if not x or not y:
                continue
            print(f"| {int(pg)} x {int(ln)} | {st.median(x):.2f} ({min(x):.2f}-{max(x):.2f}), {len(x)} | "
                  f"{st.median(y):.2f} ({min(y):.2f}-{max(y):.2f}), {len(y)} | {st.median(y) - st.median(x):+.2f} | "
                  f"{st.median(n80) - st.median(y):+.2f} |")
    print()


def exp_n5():
    rows = tagged_rows(os.path.join(DEV, "expN5.log"), "N5")
    if not rows:
        return
    print("## Exp N5: which stage-2 class the pages of probe3's own buffer are in, and what a page walk costs it\n")
    print("N80 as root, memory held back as in N2, one process per cell.  candidate share = pages in the two 1 GiB-candidate "
          "slots; shared share = pages in 2 MiB regions that hold pages of the running VM (region list taken at the start; "
          "the list taken at the end is identical).  cycles per walk = (cycles - median cycles of 1024 x 2 at the same touch "
          "order) / page walks per hop.  model = 24.1 + 4.0 x candidate share + 9.5 x shared share, the three class values "
          "measured with frames2 (written down before the run).\n")
    ref = {}
    for pf in (0.0, 1.0):
        v = [r["ev11"] for r in rows if r["pages"] == 1024.0 and r["prefault"] == pf and r["ev17"] < 0.05]
        ref[pf] = st.median(v)
    print("| rep | held back | touch order | candidate share | shared share | 2 MiB regions | cycles | page walks per hop | "
          "L2 refills per hop | cycles per walk | model | measured - model |")
    print("|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    ok = tot = 0
    for r in rows:
        if r["pages"] != 2048.0:
            continue
        pw = (r["ev11"] - ref[r["prefault"]]) / r["ev2d"]
        model = 24.1 + 4.0 * r["_cand"] + 9.5 * r["shared_frac"]
        dirty = r["ev17"] >= 0.05
        if not dirty:
            tot += 1
            ok += abs(pw - model) <= 1.0
        print(f"| {int(r['rep'])} | {int(r['hold_mb'])} MB | {'ascending' if r['prefault'] else 'chain'} | {r['_cand']:.3f} | "
              f"{r['shared_frac']:.3f} | {int(r['mb2_regions'])} | {r['ev11']:.2f} | {r['ev2d']:.3f} | {r['ev17']:.3f} | "
              + (f"{pw:.2f} | {model:.2f} | {pw - model:+.2f} |" if not dirty else "(L2 refills: not a translation measurement) | | |"))
    n_dirty = sum(1 for r in rows if r["pages"] == 2048.0 and r["ev17"] >= 0.05)
    print(f"\nWithin 1.0 cycle of the model: {ok} of {tot} processes ({n_dirty} further processes had 0.5 L2 refills per hop and are left out).  "
          f"Shared share: {min(r['shared_frac'] for r in rows):.3f} to {max(r['shared_frac'] for r in rows):.3f}.\n")

    # one fit over every clean 2048 x 1 process of N2, N4 and N5
    allr = []
    for name, tag in (("expN2.log", "N2"), ("expN4-n80.log", "N4"), ("expN5.log", "N5")):
        for r in tagged_rows(os.path.join(DEV, name), tag):
            if r["pages"] == 2048.0 and r["stride"] == 1.0 and r["ev17"] < 0.05:
                r["_tag"] = tag
                allr.append(r)
    if len(allr) > 5:
        ref2 = 13.97
        print("### All clean probe3 runs of 2048 x 1 (Exp N2, N4, N5): cycles per walk against candidate share and number of 2 MiB regions\n")
        print(f"cycles per walk = (cycles - {ref2}) / page walks per hop; {ref2} is the median of 1024 x 2 in N4 and N5.\n")
        print("| runs | n | cycles per walk (min-max) | a | b: per unit candidate share (s.e.) | c: per 100 regions (s.e.) | R^2 | r(share, regions) |")
        print("|---|---:|---|---:|---|---|---:|---:|")
        for label, sel in (("N2 + N4 + N5", allr), ("N2", [r for r in allr if r["_tag"] == "N2"]),
                           ("N4", [r for r in allr if r["_tag"] == "N4"]), ("N5", [r for r in allr if r["_tag"] == "N5"])):
            y = [(r["ev11"] - ref2) / r["ev2d"] for r in sel]
            f = [r["_cand"] for r in sel]
            g = [r["mb2_regions"] / 100 for r in sel]
            a0, b1, b2, se1, se2, r2 = ols2(f, g, y)
            print(f"| {label} | {len(sel)} | {min(y):.2f}-{max(y):.2f} | {a0:.2f} | {b1:+.2f} ({se1:.2f}) | {b2:+.3f} ({se2:.3f}) | {r2:.2f} | {pearson(f, g):+.2f} |")
    print()


def exp_t2():
    rows = tagged_rows(os.path.join(D80, "expT2.log"), "T2")
    if not rows:
        return
    print("## Exp T2: first-touch order on the workstation (no host stage-2, unprivileged, frame numbers not readable)\n")
    print("probe2, sequential chase, stride 256; a stopped process holds back memory so that the buffer comes from larger free "
          "blocks.  ns = median of three processes (min-max).\n")
    print("| size | held back | ascending first touch | random | descending | random vs ascending | descending vs ascending |")
    print("|---:|---:|---|---|---|---:|---:|")
    for sz in sorted({r["size_mb"] for r in rows}):
        for hold in sorted({r["hold_mb"] for r in rows}):
            v = {t: [r["ns_min"] for r in rows if r["size_mb"] == sz and r["hold_mb"] == hold and r["touch"] == t]
                 for t in ("asc", "rand", "desc")}
            m = {t: st.median(x) for t, x in v.items()}
            cell = lambda t: f"{m[t]:.2f} ({min(v[t]):.2f}-{max(v[t]):.2f})"
            print(f"| {sz:g} MB | {int(hold)} MB | {cell('asc')} | {cell('rand')} | {cell('desc')} | "
                  f"{100 * (m['rand'] / m['asc'] - 1):+.1f}% | {100 * (m['desc'] / m['asc'] - 1):+.1f}% |")
    print()


def exp_l2():
    sets = (("N80 (kvm-arm.mode=protected, kernel 6.6.0-79, root)", tagged_rows(os.path.join(DEV, "expL2-n80.log"), "L2")),
            ("D80F3 workstation (no host stage-2, kernel 7.0.0-34, unprivileged)", tagged_rows(os.path.join(D80, "expL2-d80f3.log"), "L2")))
    if not any(rows for _, rows in sets):
        return
    print("## Exp L2: the same frames in sorted, reversed and shuffled virtual order, pages taken from transparent huge pages\n")
    print("thplayout: the pool is faulted in as 2 MiB huge pages, then every 4 KiB page is moved into a new range that starts "
          "one page after a 2 MiB boundary (4 KiB page-table entries, no contiguous-PTE folding).  sorted = the order of the "
          "pool, i.e. ascending physical address inside every 2 MiB block; aligned = sorted without the one-page offset.  "
          "Sequential chase, chain written once; ns = median of the processes (min-max), cycles = 4 x ns / L1 reference.\n")
    for title, rows in sets:
        if not rows:
            continue
        bad = sum(1 for r in rows if r["thp_kb"] != r["size_mb"] * 1024)
        print(f"### {title}\n")
        print(f"{len(rows)} lines; lines whose pool was not fully backed by huge pages: {bad}.\n")
        has_pfn = any(isinstance(r.get("contig_frac"), float) for r in rows)
        has_pmu = any(isinstance(r.get("ev2d"), float) for r in rows)
        print("| loop form | stride | size | sorted: ns | cycles | shuffled: ns | cycles | shuffled vs sorted | extra cycles per page crossing | "
              "reversed vs sorted | aligned vs sorted |"
              + (" adjacency: sorted / reversed (descending) / shuffled |" if has_pfn else "")
              + (" page walks per access: sorted / shuffled / aligned | L2 refills: sorted / shuffled |" if has_pmu else ""))
        print("|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|" + ("---|" if has_pfn else "") + ("---|---|" if has_pmu else ""))
        for ch, stv, sz in sorted({(r["chase"], r["stride"], r["size_mb"]) for r in rows}):
            v = collections.defaultdict(list)
            for r in rows:
                if (r["chase"], r["stride"], r["size_mb"]) == (ch, stv, sz):
                    v[r["layout"]].append(r)
            med = lambda lay, key: st.median(r[key] for r in v[lay])
            rng = lambda lay: f"{med(lay, 'ns_min'):.2f} ({min(r['ns_min'] for r in v[lay]):.2f}-{max(r['ns_min'] for r in v[lay]):.2f}), {len(v[lay])}"
            rel = lambda lay: f"{100 * (med(lay, 'ns_min') / med('sorted', 'ns_min') - 1):+.1f}%" if v.get(lay) else ""
            line = (f"| {ch} | {stv:g} | {sz:g} MB | {rng('sorted')} | {med('sorted', 'cyc_est'):.2f} | {rng('shuffled')} | "
                    f"{med('shuffled', 'cyc_est'):.2f} | {rel('shuffled')} | "
                    f"{(med('shuffled', 'cyc_est') - med('sorted', 'cyc_est')) * 4096 / stv:+.0f} | {rel('reversed')} | {rel('aligned')} |")
            if has_pfn:
                line += (f" {med('sorted', 'contig_frac'):.3f} / "
                         + (f"{med('reversed', 'rcontig_frac'):.3f}" if v.get("reversed") else "-")
                         + f" / {med('shuffled', 'contig_frac'):.3f} |")
            if has_pmu:
                line += (f" {med('sorted', 'ev2d'):.4f} / {med('shuffled', 'ev2d'):.4f} / "
                         + (f"{med('aligned', 'ev2d'):.4f}" if v.get("aligned") else "-")
                         + f" | {med('sorted', 'ev17'):.3f} / {med('shuffled', 'ev17'):.3f} |")
            print(line)
        print()


def held_sweeps(name):
    """Sweeps of run25/run26: -> list of dicts {rep, hold, noc, pre, post, t0, rows: {size_mb: (time, ns)}}."""
    path = os.path.join(DEV, name)
    if not os.path.exists(path):
        return []
    out = []
    cur = None
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("## rep="):
                d = kv(line)
                cur = {"rep": int(d["rep"]), "hold": int(d["hold_mb"]), "noc": d.get("noc"), "gov": d.get("gov"),
                       "t0": d.get("start"), "pre": None, "post": None, "rows": collections.OrderedDict(), "noc_end": None}
                out.append(cur)
            elif line.startswith("## end") and cur is not None:
                cur["noc_end"] = kv(line).get("noc")
            elif line.startswith("P ") and cur is not None:
                cur[line.split()[1]] = kv(line)
            elif cur is not None:
                p = line.split()
                if len(p) == 3:
                    try:
                        cur["rows"][float(p[1])] = (float(p[0]), float(p[2]))
                    except ValueError:
                        pass
    return out


def exp_h2():
    sw = held_sweeps("expH2.log")
    if not sw:
        return
    print("## Exp H2: lmbench's own lat_mem_rd (stride 256) with memory held back, probe3 before and after every sweep\n")
    print("A stopped process holds back the given amount before the sweep.  probe3 (sequential, stride 256, 8 MB, lmbench's loop "
          "form, chain rewritten before every interval) runs right before and right after the sweep and reports the adjacency of "
          "its own buffer (ascending / descending).  lmbench: lat_mem_rd -P 1 64 256 under nothp.  Interconnect: "
          + ", ".join(sorted({f"{s['gov']} {s['noc']:.0f}" for s in sw})) + " at the start of every sweep.\n")
    print("| rep | held back | probe3 before: adjacency asc / desc | ns | lmbench 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 32 MB | 64 MB | "
          "probe3 after: adjacency asc / desc | ns |")
    print("|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for x in sw:
        pre, post = x["pre"], x["post"]
        cell = lambda sz: f"{x['rows'][sz][1]:.2f}" if sz in x["rows"] else ""
        print(f"| {x['rep']} | {x['hold']} MB | {pre['contig_frac']:.2f} / {pre['rcontig_frac']:.2f} | {pre['ns_min']:.2f} | "
              + " | ".join(cell(sz) for sz in (4.0, 6.0, 8.0, 12.0, 16.0, 32.0, 64.0))
              + f" | {post['contig_frac']:.2f} / {post['rcontig_frac']:.2f} | {post['ns_min']:.2f} |")
    pr = [(p["contig_frac"] + p["rcontig_frac"], p["ns_min"]) for x in sw for p in (x["pre"], x["post"]) if p]
    hi = [n for a, n in pr if a >= 0.8]
    lo = [n for a, n in pr if a <= 0.3]
    print(f"\nprobe3, 8 MB: {len(hi)} runs with total adjacency of at least 0.8: median {st.median(hi):.2f} ns "
          f"({min(hi):.2f}-{max(hi):.2f})" if hi else "\nprobe3: no run with adjacency of at least 0.8", end="")
    if lo:
        print(f"; {len(lo)} runs with at most 0.3: median {st.median(lo):.2f} ns ({min(lo):.2f}-{max(lo):.2f})"
              + (f"; ratio {st.median(hi) / st.median(lo):.3f}" if hi else ""), end="")
    print(f".  Spearman rho(ns, total adjacency) over the {len(pr)} probe3 runs: {spearman([n for _, n in pr], [a for a, _ in pr]):+.2f}.\n")
    print("lmbench's own values by the amount held back (median, min-max over the sweeps):\n")
    print("| held back | sweeps | 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 24 MB | 32 MB | 48 MB | 64 MB |")
    print("|---:|---:|---|---|---|---|---|---|---|---|---|")
    for hold in sorted({x["hold"] for x in sw}):
        sel = [x for x in sw if x["hold"] == hold]
        cells = []
        for sz in (4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0):
            v = [x["rows"][sz][1] for x in sel if sz in x["rows"]]
            cells.append(f"{st.median(v):.2f} ({min(v):.2f}-{max(v):.2f})" if v else "")
        print(f"| {hold} MB | {len(sel)} | " + " | ".join(cells) + " |")
    print()


def exp_h3():
    sw = held_sweeps("expH3.log")
    path = os.path.join(DEV, "expH3-frames.log")
    if not sw or not os.path.exists(path):
        return
    fr = []
    with open(path) as fh:
        for line in fh:
            if line.startswith("t="):
                fr.append(kv(line))
    print("## Exp H3: lmbench's own lat_mem_rd (stride 256), with the physical layout of its own buffers\n")
    print("As H2, and a watcher reads /proc/<pid>/pagemap of every lat_mem_rd child a quarter of a second after it appeared.  "
          "adjacency = fraction of virtually adjacent pages of the child's buffer that are physically adjacent (ascending / "
          "descending); runs = maximal runs of physically adjacent pages.  A child is matched to the lmbench output line of the "
          "same size that was printed after the child was sampled.\n")
    pts = collections.defaultdict(list)     # size -> list of (hold, rep, ns, asc, desc, runs, regions, longest run, pages)
    for x in sw:
        for sz, (t, ns) in x["rows"].items():
            # the child of this size (its buffer holds one page more than the size: malloc's header page):
            # sampled before the line was printed, and the latest such
            cand = [f for f in fr if abs(f["size_mb"] - sz) < 0.01 and f["t"] <= t]
            if not cand:
                continue
            f = max(cand, key=lambda c: c["t"])
            if t - f["t"] > 3.0:
                continue
            pts[sz].append((x["hold"], x["rep"], ns, f["contig_frac"], f["rcontig_frac"], f["runs"], f["mb2_regions"],
                            f["longest_run"], f["pages"]))
    for size in (8.0, 16.0, 64.0):
        print(f"### The {size:g} MB point, every sweep\n")
        print("| rep | held back | lmbench ns | adjacency of its buffer: asc / desc | runs of adjacent pages | longest run (pages) | 2 MiB regions |")
        print("|---:|---:|---:|---|---:|---:|---:|")
        for hold, rep, ns, a, d, runs, reg, longest, _ in sorted(pts.get(size, []), key=lambda p: (p[1], p[0])):
            print(f"| {rep} | {hold} MB | {ns:.2f} | {a:.3f} / {d:.3f} | {runs:.0f} | {longest:.0f} | {reg:.0f} |")
        print()
    print("### By size: latency against the adjacency of lmbench's own buffer\n")
    print("| size | sweeps matched | total adjacency (min-max) | ns (min-max) | Spearman rho(ns, total adjacency) | "
          "sweeps with adjacency >= 0.8: n, median ns | sweeps with adjacency <= 0.3: n, median ns | ratio |")
    print("|---:|---:|---|---|---:|---|---|---:|")
    for sz in sorted(pts):
        if sz < 2.0:
            continue
        v = pts[sz]
        adj = [p[3] + p[4] for p in v]
        ns = [p[2] for p in v]
        hi = [p[2] for p in v if p[3] + p[4] >= 0.8]
        lo = [p[2] for p in v if p[3] + p[4] <= 0.3]
        rho = spearman(ns, adj) if len(set(adj)) > 2 else float("nan")
        print(f"| {sz:g} MB | {len(v)} | {min(adj):.2f}-{max(adj):.2f} | {min(ns):.2f}-{max(ns):.2f} | {rho:+.2f} | "
              + (f"{len(hi)}, {st.median(hi):.2f}" if hi else "0") + " | " + (f"{len(lo)}, {st.median(lo):.2f}" if lo else "0") + " | "
              + (f"{st.median(hi) / st.median(lo):.3f}" if hi and lo else "") + " |")
    print()


def layout_sweeps(path):
    """Sweeps of run27: -> list of {rep, layout, noc, rows: {size_mb: ns}}."""
    if not os.path.exists(path):
        return []
    out = []
    cur = None
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("## rep="):
                d = kv(line)
                cur = {"rep": int(d["rep"]), "layout": d["layout"], "noc": d.get("noc"), "gov": d.get("gov"), "rows": {}}
                out.append(cur)
            elif line.startswith("##"):
                continue
            elif cur is not None:
                p = line.split()
                if len(p) == 3:
                    try:
                        cur["rows"][float(p[1])] = float(p[2])
                    except ValueError:
                        pass
    return out


def exp_h4():
    sets = (("N80 (kvm-arm.mode=protected, kernel 6.6.0-79, root)", os.path.join(DEV, "expH4.log"), os.path.join(DEV, "expH4-shim.log")),
            ("D80F3 workstation (no host stage-2, kernel 7.0.0-34, unprivileged)", os.path.join(D80, "expH4-d80f3.log"),
             os.path.join(D80, "expH4-d80f3-shim.log")))
    if not any(os.path.exists(a) for _, a, _ in sets):
        return
    print("## Exp H4: lmbench's own lat_mem_rd (stride 256) on a buffer whose physical layout is set\n")
    print("The unmodified lat_mem_rd binary with layoutshim.so preloaded: its 64 MB buffer consists of 4 KiB pages taken from "
          "2 MiB huge pages, in physical order (sorted), in random order within every 8 MB (shuffled8: the first 8 MB use the "
          "same frames as sorted), or in random order over the whole buffer (shuffled).  natural = without the library, under "
          "nothp, as in Exp H.  ns = lmbench's own figure; median over the repetitions (min-max).\n")
    names = ("sorted", "shuffled8", "shuffled", "natural")
    for title, path, shim in sets:
        sw = layout_sweeps(path)
        if not sw:
            continue
        print(f"### {title}\n")
        noc = sorted({f"{x['gov']} {x['noc']:.0f}" for x in sw if isinstance(x.get("noc"), float)})
        if noc:
            print("Interconnect at the start of every sweep: " + ", ".join(noc) + ".\n")
        if os.path.exists(shim):
            rows = []
            with open(shim) as fh:
                for line in fh:
                    if line.startswith("pid="):
                        rows.append(dict(re.findall(r"(\w+)=([^\s]+)", line)))
            if rows:
                ok = sum(1 for r in rows if int(r["thp_kb"]) == int(r["pages"]) * 4)
                print(f"Buffers built by the library: {len(rows)}; fully backed by huge pages before being taken apart: {ok}.")
                for lay, chunk in (("sorted", None), ("shuffled", "2048"), ("shuffled", "other")):
                    sel = [r for r in rows if r["layout"] == lay and (chunk is None or (r["shuffle_pages"] == "2048") == (chunk == "2048"))]
                    vals = [tuple(float(v) for v in r["adj2048"].split("/")) for r in sel if r.get("adj2048", "na") != "na"]
                    if vals:
                        label = lay if chunk is None else ("shuffled8" if chunk == "2048" else "shuffled")
                        print(f"Adjacency of the first 2048 pages, {label}: ascending {min(v[0] for v in vals):.4f}-{max(v[0] for v in vals):.4f}, "
                              f"descending {min(v[1] for v in vals):.4f}-{max(v[1] for v in vals):.4f} ({len(vals)} buffers).")
                print()
        sizes = (2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0)
        print("| size | " + " | ".join(names) + " | shuffled8 / sorted | shuffled / sorted | natural / sorted |")
        print("|---:|" + "---|" * len(names) + "---:|---:|---:|")
        for sz in sizes:
            v = {n: [x["rows"][sz] for x in sw if x["layout"] == n and sz in x["rows"]] for n in names}
            if not v["sorted"]:
                continue
            cell = lambda n: f"{st.median(v[n]):.2f} ({min(v[n]):.2f}-{max(v[n]):.2f})" if v[n] else ""
            rat = lambda n: f"{st.median(v[n]) / st.median(v['sorted']):.3f}" if v[n] else ""
            print(f"| {sz:g} MB | " + " | ".join(cell(n) for n in names) + f" | {rat('shuffled8')} | {rat('shuffled')} | {rat('natural')} |")
        print("\nThe 8 MB point in every repetition (ns): "
              + "; ".join(f"rep {rep}: " + ", ".join(f"{n} {x['rows'][8.0]:.2f}" for n in names for x in sw
                                                        if x["rep"] == rep and x["layout"] == n and 8.0 in x["rows"])
                          for rep in sorted({x["rep"] for x in sw})) + ".\n")


def layout_stride_sweeps(path):
    """Sweeps of run28: -> list of {rep, layout, rows: {(stride, size_mb): ns}}."""
    if not os.path.exists(path):
        return []
    out = []
    cur = None
    stride = None
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("## rep="):
                d = kv(line)
                cur = {"rep": int(d["rep"]), "layout": d["layout"], "noc": d.get("noc"), "gov": d.get("gov"), "rows": {}}
                out.append(cur)
                stride = None
            elif line.startswith("##") or cur is None:
                continue
            else:
                p = line.split()
                if len(p) >= 2 and p[1].startswith('"stride='):
                    stride = int(p[1].split("=")[1])
                elif len(p) == 3 and stride is not None:
                    try:
                        cur["rows"][(stride, float(p[1]))] = float(p[2])
                    except ValueError:
                        pass
    return out


def n90_levels(stride, size):
    """The N90 quiesced hosts at one point: (low median, n low, high median or None, n high) with the 12% rule."""
    host = n90("lat_mem_rd_load")
    pool = sorted(sum((host[c][(stride, float(size))] for c in ("kvmoff", "nvhe", "vhe", "pkvm")), []))
    thr = 1.12 * st.median(pool[:len(pool) // 2])
    lo = [x for x in pool if x <= thr]
    hi = [x for x in pool if x > thr]
    return st.median(lo), len(lo), (st.median(hi) if hi else None), len(hi)


def exp_h5():
    sets = (("N80 (kvm-arm.mode=protected, kernel 6.6.0-79, root)", os.path.join(DEV, "expH5.log"), os.path.join(DEV, "expH4.log")),
            ("D80F3 workstation (no host stage-2, kernel 7.0.0-34, unprivileged)", os.path.join(D80, "expH5-d80f3.log"),
             os.path.join(D80, "expH4-d80f3.log")))
    if not any(os.path.exists(a) for _, a, _ in sets):
        return
    print("## Exp H5: lmbench's own lat_mem_rd on sorted and on shuffled pages, every stride of the paper's command\n")
    print("As H4 (layoutshim.so; shuffled = random order within every 8 MB, the same frames as sorted).  Strides 16, 32, 64, "
          "128, 512, 1024 from run28 (two repetitions per layout), stride 256 from H4 (four).  ns = lmbench's own figure, "
          "median of the repetitions.  The N90 columns are the two levels of the four quiesced host boots of June 2026 at the "
          "same point (40 values; high = more than 12% above the median of the lower half).\n")
    for title, path, h4 in sets:
        sw = layout_stride_sweeps(path)
        if not sw:
            continue
        for x in layout_sweeps(h4):
            if x["layout"] in ("sorted", "shuffled8"):
                sw.append({"rep": x["rep"], "layout": x["layout"], "rows": {(256, k): v for k, v in x["rows"].items()}})
        print(f"### {title}\n")
        for size in (8.0, 12.0, 6.0, 4.0, 64.0):
            print(f"{size:g} MB:\n")
            print("| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | "
                  "N90: low level, n | N90: high level, n | N90: high / low |")
            print("|---:|---|---|---:|---:|---|---|---:|")
            for stv in (16, 32, 64, 128, 256, 512, 1024):
                a = [x["rows"][(stv, size)] for x in sw if x["layout"] == "sorted" and (stv, size) in x["rows"]]
                b = [x["rows"][(stv, size)] for x in sw if x["layout"] == "shuffled8" and (stv, size) in x["rows"]]
                if not a or not b:
                    continue
                lo, nlo, hi, nhi = n90_levels(stv, size)
                print(f"| {stv} | {st.median(a):.3f} ({min(a):.3f}-{max(a):.3f}), {len(a)} | {st.median(b):.3f} ({min(b):.3f}-{max(b):.3f}), {len(b)} | "
                      f"{st.median(b) - st.median(a):+.3f} | {st.median(b) / st.median(a):.3f} | {lo:.3f}, {nlo} | "
                      + (f"{hi:.3f}, {nhi} | {hi / lo:.3f} |" if hi else f"none, {nhi} | |"))
            print()


def main():
    exp_r()
    exp_bg()
    exp_h()
    exp_s()
    exp_v()
    exp_v2()
    exp_v3()
    exp_slots()
    exp_w()
    exp_x()
    exp_y()
    exp_z()
    exp_n()
    exp_n2()
    exp_n3()
    exp_n4()
    exp_n5()
    exp_t2()
    exp_l2()
    exp_h2()
    exp_h3()
    exp_h4()
    exp_h5()
    exp_g1()
    exp_g2()
    exp_h("expG4", "Exp G4: lmbench's own lat_mem_rd in three interconnect states")


if __name__ == "__main__":
    main()
