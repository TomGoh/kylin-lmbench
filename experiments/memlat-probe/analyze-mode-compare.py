#!/usr/bin/env python3
"""Compare run5-mode-compare.sh output directories taken in different KVM boot modes.

  python3 analyze-mode-compare.py modecmp-none-... modecmp-nvhe-... modecmp-protected-...

The first directory is the reference.  The question each table answers:

  state     were the runs taken in the same platform state (THP, CPU and
            interconnect frequency)?  If not, the comparison is not between
            boot modes.
  random    do the modes make the same number of page walks and the same
            number of cache refills per access, and if so how many extra
            cycles does each walk cost?  (On the N80 the placement of the
            frames alone moved the 64 MB random latency by 3 to 4 percent
            together with the L2 refill count, so equal refill counts are part
            of the test.)
  seq       the same per page crossing, for the sequential chase over 64 MB
  llc       how the sequential points around the L3 size vary from one fresh
            process to the next, and whether that follows physical contiguity
            or the interconnect frequency
  tlb       what one page walk costs in each mode, from a chase whose data stay
            in the L1/L2 caches (frames2 tlb<L>), and whether GiB slots differ

Standard library only.  Output is Markdown.
"""
import collections
import math
import os
import re
import statistics as st
import sys


def kv(line):
    d = {}
    for k, v in re.findall(r"(\w+)=([^\s]+)", line):
        v = re.sub(r"\(mux[\d.]+\)", "", v)
        try:
            d[k] = float(v)
        except ValueError:
            d[k] = v
    return d


def rows(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            if "mode=" in line and "ns_min=" in line:
                out.append(kv(line))
    return out


def num(rs, key):
    return [r[key] for r in rs if isinstance(r.get(key), float)]


def med(rs, key):
    v = num(rs, key)
    return st.median(v) if v else float("nan")


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


def state(path):
    """Pick the fields that decide whether two runs are comparable."""
    s = {}
    if not os.path.exists(path):
        return s
    section = ""
    dev = ""
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("## "):
                section = line[3:]
                continue
            if line.startswith("### "):
                dev = line[4:].split(" ")[0]
                continue
            if section == "" and ": " in line:
                k, v = line.split(": ", 1)
                s[k] = v
            elif section == "kernel config" and line.startswith("CONFIG_X1_RMS"):
                s["x1_rms"] = line.split("=", 1)[1]
            elif section == "transparent huge pages" and line.endswith(tuple("]abcdefghijklmnopqrstuvwxyz")):
                name, v = line.split(": ", 1)
                m = re.search(r"\[(\w+)\]", v)
                if m and name.endswith("transparent_hugepage/enabled"):
                    s["thp"] = m.group(1)
                elif m and "hugepages-" in name and m.group(1) not in ("never", "inherit"):
                    s.setdefault("thp_sizes", []).append(name.split("/")[-2] + "=" + m.group(1))
            elif section == "cpufreq" and line.startswith("cpu0:"):
                s["cpu0"] = line.split(": ", 1)[1]
            elif section == "devfreq" and dev == "nocfreq":
                if line.startswith("governor: "):
                    s["noc_governor"] = line.split(": ", 1)[1]
                elif line.startswith("cur_freq: "):
                    s["noc_freq"] = line.split(": ", 1)[1]
    return s


def freq_summary(rs):
    c = collections.Counter()
    for r in rs:
        for k in ("noc_before", "noc_after"):
            c[r.get(k, "na")] += 1
    return ", ".join(f"{int(k) if isinstance(k, float) else k}: {n}" for k, n in sorted(c.items(), key=lambda kv: str(kv[0])))


def main():
    dirs = [d.rstrip("/") for d in sys.argv[1:]]
    if not dirs:
        sys.exit(__doc__)
    names = [os.path.basename(d) for d in dirs]
    data = {}
    for d, n in zip(dirs, names):
        data[n] = {
            "before": state(os.path.join(d, "state-before.txt")),
            "after": state(os.path.join(d, "state-after.txt")),
            "rand": rows(os.path.join(d, "rand.log")),
            "seq": rows(os.path.join(d, "seq.log")),
            "llc": rows(os.path.join(d, "llc.log")),
            "tlb": rows(os.path.join(d, "tlb.log")),
        }
    ref = names[0]

    print("## Platform state of each run\n")
    print("| run | kvm-arm.mode | kernel | CONFIG_X1_RMS | THP | cpu0 | interconnect governor | interconnect frequency before / after | "
          "frequencies seen around the probe runs (value: count) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in names:
        b, a = data[n]["before"], data[n]["after"]
        kernel = b.get("uname", "?").split(" ")[2] if b.get("uname") else "?"
        thp = b.get("thp", "?") + ("; " + " ".join(b["thp_sizes"]) if b.get("thp_sizes") else "")
        allr = data[n]["rand"] + data[n]["seq"] + data[n]["llc"]
        print(f"| {n} | {b.get('kvm_arm_mode', '?')} | {kernel} | {b.get('x1_rms', 'not in config')} | {thp} | {b.get('cpu0', '?')} | "
              f"{b.get('noc_governor', 'no nocfreq device')} | {b.get('noc_freq', '?')} / {a.get('noc_freq', '?')} | {freq_summary(allr)} |")
    print("\nIf the runs differ in any column other than kvm-arm.mode, the tables below do not compare boot modes alone.\n")

    print(f"## Random chase (lmbench -t, stride 16): reference = {ref}\n")
    print("Per access, median over seeds: time in ns (the minimum of 11 repetitions of each run, as lmbench reports), cycles, "
          "page walks (l2d_tlb_refill), L2 and L3 cache refills.  'extra cycles per walk' = (cycles - reference cycles) / walks.  "
          "It measures the cost of a walk only if 'walks ratio' is 1 and 'extra L2 refills' is about 0.\n")
    head = "| size |"
    sep = "|---:|"
    for n in names:
        head += f" {n}: ns | cycles | walks | L2 refills | L3 refills |"
        sep += "---:|---:|---:|---:|---:|"
        if n != ref:
            head += " extra ns | extra cycles | walks ratio | extra L2 refills | extra cycles per walk |"
            sep += "---:|---:|---:|---:|---:|"
    print(head)
    print(sep)
    by = {n: collections.defaultdict(list) for n in names}
    for n in names:
        for r in data[n]["rand"]:
            by[n][r["size_mb"]].append(r)
    for s in sorted(by[ref]):
        line = f"| {s:g} MB |"
        r0 = by[ref][s]
        for n in names:
            rs = by[n].get(s, [])
            ns, cyc, w, l2, l3 = med(rs, "ns_min"), med(rs, "ev11"), med(rs, "ev2d"), med(rs, "ev17"), med(rs, "ev2a")
            line += f" {ns:.2f} | {cyc:.2f} | {w:.4f} | {l2:.3f} | {l3:.3f} |"
            if n != ref:
                dns, dc = ns - med(r0, "ns_min"), cyc - med(r0, "ev11")
                w0 = med(r0, "ev2d")
                ratio = f"{w / w0:.3f}" if w0 > 0.02 else "n/a"
                per = f"{dc / w:.1f}" if w > 0.02 else "n/a"
                line += f" {dns:+.2f} | {dc:+.2f} | {ratio} | {l2 - med(r0, 'ev17'):+.3f} | {per} |"
        print(line)

    print(f"\n## Sequential chase over 64 MB by stride: reference = {ref}\n")
    head = "| stride | page crossings per access |"
    sep = "|---:|---:|"
    for n in names:
        head += f" {n}: ns | cycles | walks |"
        sep += "---:|---:|---:|"
        if n != ref:
            head += " extra ns | extra cycles per walk |"
            sep += "---:|---:|"
    print(head)
    print(sep)
    by = {n: collections.defaultdict(list) for n in names}
    for n in names:
        for r in data[n]["seq"]:
            by[n][r["stride"]].append(r)
    for s in sorted(by[ref]):
        line = f"| {int(s)} | {s / 4096:.5f} |"
        r0 = by[ref][s]
        for n in names:
            rs = by[n].get(s, [])
            ns, cyc, w = med(rs, "ns_min"), med(rs, "ev11"), med(rs, "ev2d")
            line += f" {ns:.3f} | {cyc:.3f} | {w:.5f} |"
            if n != ref:
                per = f"{(cyc - med(r0, 'ev11')) / w:.1f}" if w > 0.001 else "n/a"
                line += f" {ns - med(r0, 'ns_min'):+.3f} | {per} |"
        print(line)

    print("\n## Sequential stride 256 around the L3 size, fresh process per point\n")
    print("'slow' = above the midpoint between the smallest and the largest value of that row.  "
          "rho = Spearman rank correlation with the latency.\n")
    print("| run | size | n | min | median | max | max / min | slow | rho(physical contiguity) | rho(L3 refills) | "
          "rho(interconnect frequency before the run) | interconnect frequencies before the run (value: count) |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for n in names:
        bys = collections.defaultdict(list)
        for r in data[n]["llc"]:
            bys[r["size_mb"]].append(r)
        for s in sorted(bys):
            rs = bys[s]
            ns = [r["ns_min"] for r in rs]
            mid = (min(ns) + max(ns)) / 2
            c = num(rs, "contig_frac")
            l3 = num(rs, "ev2a")
            f = num(rs, "noc_before")
            fc = collections.Counter(int(x) for x in f)
            rho = lambda v: f"{spearman(ns, v):+.2f}" if len(v) == len(ns) and len(set(v)) > 1 else "n/a"
            print(f"| {n} | {s:g} MB | {len(ns)} | {min(ns):.2f} | {st.median(ns):.2f} | {max(ns):.2f} | {max(ns) / min(ns):.3f} | "
                  f"{sum(x > mid for x in ns)}/{len(ns)} | {rho(c)} | {rho(l3)} | {rho(f)} | "
                  f"{', '.join(f'{k}: {v}' for k, v in sorted(fc.items())) or 'n/a'} |")

    section_tlb(names, data, ref)


def section_tlb(names, data, ref):
    if not any(data[n]["tlb"] for n in names):
        return
    print(f"\n## Translation-only chase (another page on every hop, few cache lines per page): reference = {ref}\n")
    print("Cycles per hop, median over GiB slots, passes and seeds.  The first configuration needs no page walk and is the "
          "reference within each mode; 'walk cost' = cycles minus that reference.  The difference of the walk cost between "
          "two modes is what the stage-2 translation adds to a TLB miss, free of memory-system state.\n")
    cfgs = sorted({(r["size_mb"], r["stride"]) for n in names for r in data[n]["tlb"]}, key=lambda c: (c[0] * c[1], c[0]))
    head = "| pages x lines per page |"
    sep = "|---|"
    for n in names:
        head += f" {n}: cycles | walks | L2 refills | walk cost |"
        sep += "---:|---:|---:|---:|"
        if n != ref:
            head += " walk cost minus reference |"
            sep += "---:|"
    print(head)
    print(sep)
    nowalk = {}
    for n in names:
        rs = [r for r in data[n]["tlb"] if (r["size_mb"], r["stride"]) == (4.0, 4.0)]
        nowalk[n] = med(rs, "ev11")
    for size, lines in cfgs:
        line = f"| {int(size * 256)} x {lines:g} |"
        cost = {}
        for n in names:
            rs = [r for r in data[n]["tlb"] if (r["size_mb"], r["stride"]) == (size, lines)]
            cost[n] = med(rs, "ev11") - nowalk[n]
            line += f" {med(rs, 'ev11'):.2f} | {med(rs, 'ev2d'):.3f} | {med(rs, 'ev17'):.3f} | {cost[n]:+.2f} |"
            if n != ref:
                line += f" {cost[n] - cost[ref]:+.2f} |"
        print(line)
    print("\nPer GiB slot, 4096 pages x 1 line (cycles per hop, median over passes and seeds).  Under a host stage-2 "
          "map, slots mapped by one 1 GiB block were about 4 cycles slower than slots mapped by 2 MiB blocks on the N80; "
          "without a host stage-2 no slot should differ.\n")
    slots = sorted({r["slot"] for n in names for r in data[n]["tlb"] if (r["size_mb"], r["stride"]) == (16.0, 1.0)}, key=str)
    print("| slot | " + " | ".join(names) + " |")
    print("|---|" + "---:|" * len(names))
    for s in slots:
        cells = []
        for n in names:
            rs = [r for r in data[n]["tlb"] if (r["size_mb"], r["stride"]) == (16.0, 1.0) and r["slot"] == s]
            cells.append(f"{med(rs, 'ev11'):.2f}" if rs else "")
        print(f"| {s} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
