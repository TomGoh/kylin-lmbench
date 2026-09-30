#!/usr/bin/env python3
"""Host 4-mode memory-latency analysis for the N90 lmbench data.

Reads results/n90-day3-host/*.csv (kvmoff / nvhe / vhe / pkvm-try2, N=10 each)
and prints, as Markdown:

  1. the three memory-latency numbers of the paper's Figure 7
     (LLC Bnd, Main Mem, Rand Mem) with both mean and median estimators;
  2. the per-iteration values of the LLC-boundary point, the two latency
     modes, and significance tests of pkvm vs kvmoff;
  3. the random-access curve: pkvm minus baseline (ns) per working-set size,
     with a bootstrap confidence interval;
  4. the sequential curve at 64 MB per stride (page crossings per access).

Standard library only.  Usage:  python3 analyze-host-memlat.py [repo_root]
"""
import collections
import csv
import itertools
import math
import os
import random
import re
import statistics as st
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(ROOT, "results", "n90-day3-host")
FILES = {
    "kvmoff": "n90-kvmoff-noLSM-full-cpu0.csv",
    "nvhe": "n90-nvhe-noLSM-full-cpu0.csv",
    "vhe": "n90-vhe-noLSM-full-cpu0.csv",
    "pkvm": "n90-pkvm-noLSM-try2-cpu0.csv",
}
CFGS = ["kvmoff", "nvhe", "vhe", "pkvm"]
BASE = ["kvmoff", "nvhe", "vhe"]          # the three modes without a host stage-2
MODE_SPLIT_NS = 11.3                        # boundary between the two 8 MB modes


def load():
    data = {}
    for cfg, name in FILES.items():
        d = collections.defaultdict(dict)
        with open(os.path.join(RES, name)) as fh:
            for r in csv.DictReader(fh):
                if r["bench"] not in ("lat_mem_rd_load", "lat_mem_rd_rand"):
                    continue
                m = re.match(r"stride(\d+)_sz([\d.]+)MB", r["variant"])
                d[(r["bench"], int(m.group(1)), float(m.group(2)))][int(r["iter"])] = float(r["value"])
        data[cfg] = d
    return data


def vals(data, cfg, key):
    return [data[cfg][key][i] for i in sorted(data[cfg][key])]


def welch(a, b):
    ma, mb = st.mean(a), st.mean(b)
    va, vb = st.variance(a), st.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    t = (mb - ma) / se
    df = (va / len(a) + vb / len(b)) ** 2 / (
        (va / len(a)) ** 2 / (len(a) - 1) + (vb / len(b)) ** 2 / (len(b) - 1))
    return t, df


def exact_permutation_p(a, b, stat=st.mean):
    """Two-sided exact permutation test on the difference of `stat`."""
    pool = a + b
    n = len(a)
    obs = abs(stat(b) - stat(a))
    total = hits = 0
    idx = range(len(pool))
    for comb in itertools.combinations(idx, n):
        s = set(comb)
        x = [pool[i] for i in comb]
        y = [pool[i] for i in idx if i not in s]
        total += 1
        if abs(stat(y) - stat(x)) >= obs - 1e-12:
            hits += 1
    return hits / total


def bootstrap_ci(a, b, stat=st.median, n=20000, seed=1):
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        x = [rng.choice(a) for _ in a]
        y = [rng.choice(b) for _ in b]
        diffs.append(stat(y) - stat(x))
    diffs.sort()
    return diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def main():
    data = load()

    print("## 1. Figure 7 memory-latency numbers (pkvm try2 vs each baseline)\n")
    print("| metric | estimator | kvmoff | nvhe | vhe | pkvm | vs kvmoff | vs vhe | vs nvhe |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, key in [("LLC Bnd (seq stride 256, 8 MB)", ("lat_mem_rd_load", 256, 8.0)),
                      ("Main Mem (seq stride 256, 64 MB)", ("lat_mem_rd_load", 256, 64.0)),
                      ("Rand Mem (rand stride 16, 64 MB)", ("lat_mem_rd_rand", 16, 64.0))]:
        for est_name, est in (("mean", st.mean), ("median", st.median)):
            v = {c: est(vals(data, c, key)) for c in CFGS}
            print(f"| {name} | {est_name} | {v['kvmoff']:.3f} | {v['nvhe']:.3f} | {v['vhe']:.3f} | {v['pkvm']:.3f} | "
                  + " | ".join(f"{100 * (v['pkvm'] / v[b] - 1):+.2f}%" for b in ("kvmoff", "vhe", "nvhe")) + " |")

    print("\n## 2. LLC-boundary point: per-iteration values (ns)\n")
    key = ("lat_mem_rd_load", 256, 8.0)
    print("| config | iter 1..10 | slow-mode runs | slow-mode mean | fast-mode mean | mean | SD |")
    print("|---|---|:---:|---:|---:|---:|---:|")
    for c in CFGS:
        v = vals(data, c, key)
        slow = [x for x in v if x >= MODE_SPLIT_NS]
        fast = [x for x in v if x < MODE_SPLIT_NS]
        print(f"| {c} | {' '.join(f'{x:.2f}' for x in v)} | {len(slow)}/{len(v)} | {st.mean(slow):.2f} | "
              f"{st.mean(fast):.2f} | {st.mean(v):.3f} | {st.stdev(v):.2f} |")
    a, b = vals(data, "kvmoff", key), vals(data, "pkvm", key)
    t, df = welch(a, b)
    lo, hi = bootstrap_ci(a, b, st.mean)
    print(f"\npkvm - kvmoff: mean difference {st.mean(b) - st.mean(a):+.3f} ns; Welch t = {t:.2f} (df = {df:.1f}); "
          f"exact permutation p (means) = {exact_permutation_p(a, b):.3f}; "
          f"exact permutation p (medians) = {exact_permutation_p(a, b, st.median):.3f}; "
          f"bootstrap 95% CI of the mean difference [{lo:+.2f}, {hi:+.2f}] ns.")
    print("\nDifferences among the three modes that have no host stage-2 at the same point (means):")
    for x, y in (("kvmoff", "nvhe"), ("kvmoff", "vhe"), ("nvhe", "vhe")):
        mx, my = st.mean(vals(data, x, key)), st.mean(vals(data, y, key))
        print(f"- {y} vs {x}: {100 * (my / mx - 1):+.2f}%")

    print("\nSame point for other strides (values per iteration; modes are decided per allocation, "
          "so strides within one iteration do not agree):\n")
    print("| stride | config | iter 1..10 |")
    print("|---:|---|---|")
    for s in (128, 512, 1024):
        for c in CFGS:
            print(f"| {s} | {c} | {' '.join(f'{x:.2f}' for x in vals(data, c, ('lat_mem_rd_load', s, 8.0)))} |")

    print("\nNeighbouring sizes at stride 256 (coefficient of variation per config):\n")
    print("| size | " + " | ".join(CFGS) + " |")
    print("|---:|" + "---:|" * len(CFGS))
    for sz in (4.0, 6.0, 8.0, 12.0, 16.0, 64.0):
        row = []
        for c in CFGS:
            v = vals(data, c, ("lat_mem_rd_load", 256, sz))
            row.append(f"{st.mean(v):.2f} ns, CV {100 * st.stdev(v) / st.mean(v):.1f}%")
        print(f"| {sz:g} MB | " + " | ".join(row) + " |")

    print("\n## 3. Random access (lmbench -t, stride 16): medians and the protected-mode increment\n")
    print("| size | pages | kvmoff | nvhe | vhe | pkvm | pkvm - baseline (ns) | 95% CI vs kvmoff (ns) | relative | spread of the 3 baselines (ns) |")
    print("|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|")
    sizes = sorted({k[2] for k in data["kvmoff"] if k[0] == "lat_mem_rd_rand"})
    for s in sizes:
        if s < 0.5:
            continue
        key = ("lat_mem_rd_rand", 16, s)
        md = {c: st.median(vals(data, c, key)) for c in CFGS}
        base = st.median([md[c] for c in BASE])
        spread = max(md[c] for c in BASE) - min(md[c] for c in BASE)
        lo, hi = bootstrap_ci(vals(data, "kvmoff", key), vals(data, "pkvm", key), st.median, n=5000)
        print(f"| {s:g} MB | {int(s * 256)} | {md['kvmoff']:.2f} | {md['nvhe']:.2f} | {md['vhe']:.2f} | {md['pkvm']:.2f} | "
              f"{md['pkvm'] - base:+.2f} | [{lo:+.2f}, {hi:+.2f}] | {100 * (md['pkvm'] / base - 1):+.2f}% | {spread:.2f} |")

    print("\nPer-iteration values at 64 MB (note the occasional fast iterations in every mode):\n")
    for c in CFGS:
        print(f"- {c}: " + " ".join(f"{x:.1f}" for x in vals(data, c, ("lat_mem_rd_rand", 16, 64.0))))

    print("\npkvm (10 runs) against the 30 pooled runs of the three baselines, Monte-Carlo permutation "
          "test on the difference of medians (200000 shuffles):\n")
    print("| size | median pooled baselines | median pkvm | difference (ns) | two-sided p | pkvm runs above every baseline run |")
    print("|---:|---:|---:|---:|---:|:---:|")
    rng = random.Random(7)
    for s in (4.0, 8.0, 16.0, 32.0, 64.0):
        key = ("lat_mem_rd_rand", 16, s)
        pooled = [x for c in BASE for x in vals(data, c, key)]
        pk = vals(data, "pkvm", key)
        obs = st.median(pk) - st.median(pooled)
        allv = pooled + pk
        hits = 0
        shuffles = 200000
        for _ in range(shuffles):
            rng.shuffle(allv)
            if abs(st.median(allv[:len(pk)]) - st.median(allv[len(pk):])) >= abs(obs) - 1e-12:
                hits += 1
        above = sum(1 for x in pk if x > max(pooled))
        print(f"| {s:g} MB | {st.median(pooled):.2f} | {st.median(pk):.2f} | {obs:+.2f} | "
              f"{max(hits, 1) / shuffles:.6f}{' (upper bound)' if hits == 0 else ''} | {above}/{len(pk)} |")

    print("\n## 4. Sequential access at 64 MB by stride (one page crossing every 4096/stride accesses)\n")
    print("| stride | crossings per access | kvmoff | nvhe | vhe | pkvm | pkvm - median(kvmoff, nvhe) (ns) | implied ns per crossing |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in (16, 32, 64, 128, 256, 512, 1024):
        key = ("lat_mem_rd_load", s, 64.0)
        md = {c: st.median(vals(data, c, key)) for c in CFGS}
        ref = (md["kvmoff"] + md["nvhe"]) / 2
        d = md["pkvm"] - ref
        print(f"| {s} | {s / 4096:.4f} | {md['kvmoff']:.3f} | {md['nvhe']:.3f} | {md['vhe']:.3f} | {md['pkvm']:.3f} | "
              f"{d:+.3f} | {d / (s / 4096):+.1f} |")


if __name__ == "__main__":
    main()
