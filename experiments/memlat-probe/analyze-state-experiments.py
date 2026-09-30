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
          "adjacent, in either direction.\n")
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
    print("\nRank correlation of the latency with the physical layout (both rebuild settings pooled):\n")
    print("| size | n | rho(ns, adjacency) | rho(ns, distinct 2 MiB regions) | adjacency range | ns range |")
    print("|---:|---:|---:|---:|---|---|")
    for sz in sorted({k[0] for k in by}):
        rs = by[(sz, 0)] + by[(sz, 1)]
        ns = [r["ns_min"] for r in rs]
        adj = [r["contig_frac"] + r["rcontig_frac"] for r in rs]
        mb = [r["mb2_regions"] for r in rs]
        print(f"| {sz:g} MB | {len(rs)} | {spearman(ns, adj):+.2f} | {spearman(ns, mb):+.2f} | {min(adj):.2f}-{max(adj):.2f} | "
              f"{min(ns):.2f}-{max(ns):.2f} |")
    # consecutive processes reuse the frames the previous one freed, in reverse order
    sw = 0
    pairs = 0
    seq = [r for r in rows]
    for a, b in zip(seq, seq[1:]):
        if a["size_mb"] == b["size_mb"]:
            pairs += 1
            if abs(a["contig_frac"] - b["rcontig_frac"]) < 0.02 and abs(a["rcontig_frac"] - b["contig_frac"]) < 0.02:
                sw += 1
    print(f"\nFrame reuse: in {sw} of {pairs} pairs of consecutive processes at the same size, the ascending adjacency of "
          "one equals the descending adjacency of the next within 0.02, i.e. the second process received the frames the "
          "first one had just freed, in reverse order.\n")


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
          "/proc/iomem; a slot that is not entirely ordinary RAM cannot be one 1 GiB stage-2 block.\n")
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
    print("| size | pages picked | class | slots | sorted: ns (min-max) | shuffled: ns (min-max) | shuffled vs sorted | "
          "page walks per access: sorted / shuffled | L2 refills: sorted / shuffled | adjacency when sorted |")
    print("|---:|---|---|---:|---|---|---:|---|---|---:|")
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
                      f"{m(so, 'ev17'):.3f} / {m(sh, 'ev17'):.3f} | {m(so, 'contig_frac'):.2f} |")
    # the same slot for both classes, where shared exists
    print("\nSame slot, both classes (slot 0x20c0000000 where available):\n")
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
        print("\n### lmbench's own lat_mem_rd, stride 256: Exp H (about 18:00) against Exp X3 (20:00), same platform state\n")
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


def main():
    exp_r()
    exp_bg()
    exp_h()
    exp_s()
    exp_v()
    exp_v2()
    exp_w()
    exp_x()
    exp_y()
    exp_g1()
    exp_g2()
    exp_h("expG4", "Exp G4: lmbench's own lat_mem_rd in three interconnect states")


if __name__ == "__main__":
    main()
