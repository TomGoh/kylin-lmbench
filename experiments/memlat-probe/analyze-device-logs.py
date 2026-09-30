#!/usr/bin/env python3
"""Tabulate the N80 device measurements (results/memlat-n80-20260930/*.log).

  Exp A  random chase, size sweep      -> page walks per access vs working set,
                                          and the N90 protected-mode increment
                                          divided by that walk rate
  Exp B  sequential stride 256         -> what predicts run-to-run latency
  Exp C  random chase on 2 MiB pages
  Exp D  sequential 64 MB, by stride   -> page walks per page crossing
  Exp L  same frames, different order  -> sorted / reversed / shuffled
  Exp T  first-touch order
  Exp F  frame set chosen by policy    -> does physical location matter for random access

Standard library only.  Usage:  python3 analyze-device-logs.py [repo_root]
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


def rows(name, marker):
    out = []
    with open(os.path.join(DEV, name)) as fh:
        for line in fh:
            if marker in line:
                out.append(kv(line))
    return out


def mean(rs, key):
    v = [r[key] for r in rs if isinstance(r.get(key), float)]
    return st.mean(v) if v else float("nan")


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
    mx, my = st.mean(x), st.mean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def n90_random_increment():
    """pkvm median minus the median of the three baseline medians, per size (ns)."""
    files = {"kvmoff": "n90-kvmoff-noLSM-full-cpu0.csv", "nvhe": "n90-nvhe-noLSM-full-cpu0.csv",
             "vhe": "n90-vhe-noLSM-full-cpu0.csv", "pkvm": "n90-pkvm-noLSM-try2-cpu0.csv"}
    med = {}
    for cfg, name in files.items():
        d = collections.defaultdict(list)
        with open(os.path.join(HOST, name)) as fh:
            for r in csv.DictReader(fh):
                if r["bench"] == "lat_mem_rd_rand":
                    m = re.match(r"stride(\d+)_sz([\d.]+)MB", r["variant"])
                    d[float(m.group(2))].append(float(r["value"]))
        med[cfg] = {s: st.median(v) for s, v in d.items()}
    return {s: med["pkvm"][s] - st.median([med[c][s] for c in ("kvmoff", "nvhe", "vhe")]) for s in med["pkvm"]}


def main():
    inc = n90_random_increment()

    a = rows("expA.log", "mode=")
    by = collections.defaultdict(list)
    for r in a:
        by[r["size_mb"]].append(r)
    print("## Exp A: random chase (lmbench -t, stride 16), 4 KiB pages, N80 in protected mode\n")
    print("| size | pages | ns per access | L2 TLB refills per access (page walks) | L1 TLB refills | L2 cache refills | L3 cache refills | "
          "N90 increment pkvm - baseline (ns) | increment / walk rate (ns) |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in sorted(by):
        rs = by[s]
        w = mean(rs, "ev2d")
        i = inc.get(s, float("nan"))
        per = f"{i / w:.2f}" if w > 0.02 else "n/a (no walks)"
        print(f"| {s:g} MB | {int(rs[0]['pages'])} | {st.mean(r['ns_med'] for r in rs):.2f} | {w:.4f} | {mean(rs, 'ev5'):.4f} | "
              f"{mean(rs, 'ev17'):.3f} | {mean(rs, 'ev2a'):.3f} | {i:+.2f} | {per} |")

    print("\n## Exp D: sequential chase over 64 MB, 4 KiB pages\n")
    d = rows("expD.log", "mode=")
    by = collections.defaultdict(list)
    for r in d:
        by[r["stride"]].append(r)
    print("| stride | ns per access | page crossings per access | L2 TLB refills per access | walks per page crossing |")
    print("|---:|---:|---:|---:|---:|")
    for s in sorted(by):
        rs = by[s]
        w = mean(rs, "ev2d")
        print(f"| {int(s)} | {st.mean(r['ns_med'] for r in rs):.2f} | {s / 4096:.5f} | {w:.5f} | {w / (s / 4096):.3f} |")

    print("\n## Exp C: random chase with MADV_HUGEPAGE (huge pages only partly obtained)\n")
    print("| size | seed | ns per access | L2 TLB refills per access | L1 TLB refills per access | distinct 2 MiB physical regions |")
    print("|---:|---:|---:|---:|---:|---:|")
    for r in rows("expC.log", "mode="):
        print(f"| {r['size_mb']:g} MB | {int(r['seed'])} | {r['ns_med']:.2f} | {r['ev2d']:.5f} | {r['ev5']:.4f} | {int(r['mb2_regions'])} |")

    print("\n## Exp B: sequential stride 256, fresh process per point, 30 laps\n")
    b = rows("expB.log", "mode=")
    by = collections.defaultdict(list)
    for r in b:
        by[r["size_mb"]].append(r)
    print("| size | n | mean ns | min | max | CV | rho(ns, physical contiguity) | rho(ns, colour overflow fraction) | rho(ns, L3 refills) | "
          "partial r(ns, contiguity given colour) | partial r(ns, colour given contiguity) | L3 refills per access (min-max) |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    def resid(y, x):
        mx, my = st.mean(x), st.mean(y)
        sxx = sum((p - mx) ** 2 for p in x)
        b = sum((p - mx) * (q - my) for p, q in zip(x, y)) / sxx if sxx else 0.0
        return [q - (my + b * (p - mx)) for p, q in zip(x, y)]

    for s in sorted(by):
        rs = by[s]
        ns = [r["ns_med"] for r in rs]
        col = lambda k: [r[k] for r in rs]
        c, t, l3 = col("contig_frac"), col("thrash_pages_frac"), col("ev2a")
        print(f"| {s:g} MB | {len(rs)} | {st.mean(ns):.2f} | {min(ns):.2f} | {max(ns):.2f} | {100 * st.pstdev(ns) / st.mean(ns):.1f}% | "
              f"{spearman(ns, c):+.2f} | {spearman(ns, t):+.2f} | {spearman(ns, l3):+.2f} | "
              f"{pearson(resid(ns, t), resid(c, t)):+.2f} | {pearson(resid(ns, c), resid(t, c)):+.2f} | {min(l3):.3f}-{max(l3):.3f} |")
    rs = sorted(by[8.0], key=lambda r: r["contig_frac"])
    x = [r["contig_frac"] for r in rs]
    y = [r["ns_med"] for r in rs]
    mx, my = st.mean(x), st.mean(y)
    slope = sum((p - mx) * (q - my) for p, q in zip(x, y)) / sum((p - mx) ** 2 for p in x)
    print(f"\n8 MB: least-squares fit ns = {my - slope * mx:.2f} {slope:+.2f} x contiguity, Pearson r = {pearson(x, y):+.3f}.\n")
    print("| contiguity | ns per access | L3 refills per access | colour overflow fraction |")
    print("|---:|---:|---:|---:|")
    for r in rs:
        print(f"| {r['contig_frac']:.3f} | {r['ns_med']:.2f} | {r['ev2a']:.3f} | {r['thrash_pages_frac']:.3f} |")

    print("\n## Exp L: the same physical frames in three virtual orders (sequential chase)\n")
    lrows = []
    with open(os.path.join(DEV, "expL.log")) as fh:
        for line in fh:
            if line.startswith("layout="):
                lrows.append(kv(line))
    by = collections.defaultdict(list)
    for r in lrows:
        by[(r["size_mb"], r["stride"], r["layout"])].append(r)
    print("| size | stride | sorted (ns) | reversed (ns) | shuffled (ns) | shuffled vs sorted | contiguity when sorted | "
          "L3 refills sorted / shuffled | page walks sorted / shuffled | runs |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for sz in sorted({k[0] for k in by}):
        for stv in sorted({k[1] for k in by if k[0] == sz}):
            g = lambda lay, key="ns_med": mean(by.get((sz, stv, lay), []), key)
            print(f"| {sz:g} MB | {int(stv)} | {g('sorted'):.2f} | {g('reversed'):.2f} | {g('shuffled'):.2f} | "
                  f"{100 * (g('shuffled') / g('sorted') - 1):+.1f}% | {g('sorted', 'contig_frac'):.3f} | "
                  f"{g('sorted', 'ev2a'):.3f} / {g('shuffled', 'ev2a'):.3f} | {g('sorted', 'ev2d'):.4f} / {g('shuffled', 'ev2d'):.4f} | "
                  f"{len(by.get((sz, stv, 'sorted'), []))} |")

    print("\n## Exp T: first-touch order (fresh allocation per run), sequential stride 256\n")
    t = rows("expT.log", "mode=")
    by = collections.defaultdict(list)
    for r in t:
        by[(r["size_mb"], r["touch"])].append(r)
    print("| size | first-touch order | ns per run | contiguity | reverse contiguity |")
    print("|---:|---|---|---:|---:|")
    for k in sorted(by):
        rs = by[k]
        print(f"| {k[0]:g} MB | {k[1]} | {' '.join(format(r['ns_med'], '.2f') for r in rs)} | {mean(rs, 'contig_frac'):.3f} | {mean(rs, 'rcontig_frac'):.3f} |")

    print("\n## Exp F: random chase over 64 MB, frame set chosen by policy\n")
    f = rows("expF.log", "policy=")
    by = collections.defaultdict(list)
    for r in f:
        by[r["policy"]].append(r)
    print("| policy | ns per run | contiguity | distinct 1 GiB regions | distinct 2 MiB regions | page walks per access | L2 cache refills per access |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for pol, rs in by.items():
        ok = [r for r in rs if "ns_med" in r]
        if not ok:
            print(f"| {pol} | not available (too few frames in that region) | | | | | |")
            continue
        print(f"| {pol} | {' '.join(format(r['ns_med'], '.1f') for r in ok)} | {mean(ok, 'contig_frac'):.3f} | {mean(ok, 'gb_regions'):.0f} | "
              f"{mean(ok, 'mb2_regions'):.0f} | {mean(ok, 'ev2d'):.3f} | {mean(ok, 'ev17'):.3f} |")


if __name__ == "__main__":
    main()
