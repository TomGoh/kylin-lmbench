#!/usr/bin/env python3
"""Host 4-mode memory-latency analysis for the N90 lmbench data.

Reads results/n90-day3-host/*.csv (kvmoff / nvhe / vhe / pkvm-try2, 10
iterations each, one boot per mode) and results/standalone-mem-bench/*.log
(a second set of sessions), and prints, as Markdown:

  1. the three memory-latency numbers of the paper's Figure 7 (LLC Bnd,
     Main Mem, Rand Mem) with the mean (the paper's estimator) and the median,
     each with an exact permutation test on that estimator;
  2. the per-iteration values of the LLC-boundary point, the two levels it
     takes, and tests of pkvm against kvmoff;
  3. the random-access curve: pkvm minus the baselines per working-set size;
  4. the same comparison with one boot session as the unit;
  5. the sequential curve at 64 MB per stride;
  6. the quiesced nVHE run next to the non-quiesced nVHE run that the
     repository keeps as a counter-example;
  7. how often single runs of the quiesced data sets are faster than their
     median, for three thresholds;
  8. whether the slow level of the sequential test carries over from one
     working-set size to the next one measured.

How to read the tests.  The 10 iterations of a mode are repeated measurements
inside ONE boot.  A test on iterations therefore says whether two boots
differ, not whether the boot mode is the cause: the vhe and kvmoff boots,
which have the same translation regime, differ "significantly" in several
sequential rows.  Evidence for a mode effect is the size of a difference
compared with the spread among the boots without host stage-2, and whether
it reappears in the second set of sessions (section 4).

Standard library only.  Usage:  python3 analyze-host-memlat.py [repo_root]
"""
import collections
import csv
import itertools
import math
import os
import random
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(ROOT, "results", "n90-day3-host")
STANDALONE = os.path.join(ROOT, "results", "standalone-mem-bench")
FILES = {
    "kvmoff": "n90-kvmoff-noLSM-full-cpu0.csv",
    "nvhe": "n90-nvhe-noLSM-full-cpu0.csv",
    "vhe": "n90-vhe-noLSM-full-cpu0.csv",
    "pkvm": "n90-pkvm-noLSM-try2-cpu0.csv",
}
NOISY = "n90-nvhe-noisy-full-cpu0.csv"
CFGS = ["kvmoff", "nvhe", "vhe", "pkvm"]
BASE = ["kvmoff", "nvhe", "vhe"]          # the three modes without a host stage-2
ITERS = 10
SPLITS = (11.3, 12.0)                       # two ways to cut the 8 MB values into a low and a high level


def mean(v):
    return sum(v) / len(v)


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def stdev(v):
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def load_csv(name):
    """{(bench, stride, size_mb): [value of iteration 1..10]}; refuses missing or duplicate rows."""
    d = collections.defaultdict(dict)
    with open(os.path.join(RES, name)) as fh:
        for r in csv.DictReader(fh):
            if r["bench"] not in ("lat_mem_rd_load", "lat_mem_rd_rand"):
                continue
            m = re.match(r"stride(\d+)_sz([\d.]+)MB$", r["variant"])
            if not m:
                sys.exit(f"{name}: unexpected variant {r['variant']!r}")
            key = (r["bench"], int(m.group(1)), float(m.group(2)))
            it = int(r["iter"])
            if it in d[key]:
                sys.exit(f"{name}: duplicate row {key} iteration {it}")
            d[key][it] = float(r["value"])
    out = {}
    for key, per_iter in d.items():
        if sorted(per_iter) != list(range(1, ITERS + 1)):
            sys.exit(f"{name}: {key} has iterations {sorted(per_iter)}, expected 1..{ITERS}")
        out[key] = [per_iter[i] for i in range(1, ITERS + 1)]
    return out


def load_standalone():
    """{cfg: {("seq" | "rand", size_mb): [value per run]}} from results/standalone-mem-bench/*.log."""
    out = {}
    for cfg in CFGS:
        d = collections.defaultdict(list)
        path = os.path.join(STANDALONE, f"standalone-{cfg}.log")
        if not os.path.exists(path):
            return {}
        with open(path) as fh:
            for line in fh:
                m = re.match(r"\s*lat_mem_rd (seq|rand) stride\d+:(.*)", line)
                if not m:
                    continue
                for tok in m.group(2).split():
                    size, val = tok.split("=")
                    d[(m.group(1), float(size))].append(float(val))
        out[cfg] = d
    return out


def welch(a, b):
    va, vb = stdev(a) ** 2, stdev(b) ** 2
    se = math.sqrt(va / len(a) + vb / len(b))
    t = (mean(b) - mean(a)) / se
    df = (va / len(a) + vb / len(b)) ** 2 / (
        (va / len(a)) ** 2 / (len(a) - 1) + (vb / len(b)) ** 2 / (len(b) - 1))
    return t, df


def exact_permutation_p(a, b, stat=mean):
    """Two-sided exact permutation test on the difference of `stat`, all C(n_a + n_b, n_a) splits."""
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


def midranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def mann_whitney_p(a, b):
    """Exact two-sided Mann-Whitney test: the permutation test on the mean of the ranks."""
    r = midranks(a + b)
    return exact_permutation_p(r[:len(a)], r[len(a):])


def fisher_p(k1, n1, k2, n2):
    """Two-sided Fisher exact test for k1 of n1 against k2 of n2."""
    k, n = k1 + k2, n1 + n2

    def prob(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    p_obs = prob(k1)
    return sum(prob(x) for x in range(max(0, k - n2), min(k, n1) + 1) if prob(x) <= p_obs + 1e-12)


def bootstrap_mean_diff(a, b, n=20000, seed=1):
    rng = random.Random(seed)
    diffs = sorted(mean([rng.choice(b) for _ in b]) - mean([rng.choice(a) for _ in a]) for _ in range(n))
    return diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def bootstrap_increment(groups, n=20000, seed=1):
    """95% percentile interval of median(pkvm) - median(the three baseline medians); all four groups resampled."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        md = {c: median([rng.choice(v) for _ in v]) for c, v in groups.items()}
        diffs.append(md["pkvm"] - median([md[c] for c in BASE]))
    diffs.sort()
    return diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def fmt_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def section_figure7(data):
    print("## 1. Figure 7 memory-latency numbers (pkvm try2 against each baseline)\n")
    print("p = exact two-sided permutation test on the estimator of the row, over all 184756 ways to split "
          "the 20 iterations of two boots.\n")
    print("| metric | estimator | kvmoff | nvhe | vhe | pkvm | vs kvmoff (p) | vs vhe (p) | vs nvhe (p) | vhe vs kvmoff (p) |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, key in [("LLC Bnd (seq stride 256, 8 MB)", ("lat_mem_rd_load", 256, 8.0)),
                      ("Main Mem (seq stride 256, 64 MB)", ("lat_mem_rd_load", 256, 64.0)),
                      ("Rand Mem (rand stride 16, 64 MB)", ("lat_mem_rd_rand", 16, 64.0))]:
        for est_name, est in (("mean", mean), ("median", median)):
            v = {c: est(data[c][key]) for c in CFGS}
            cells = []
            for x, y in (("kvmoff", "pkvm"), ("vhe", "pkvm"), ("nvhe", "pkvm"), ("kvmoff", "vhe")):
                p = exact_permutation_p(data[x][key], data[y][key], est)
                cells.append(f"{100 * (v[y] / v[x] - 1):+.2f}% ({fmt_p(p)})")
            print(f"| {name} | {est_name} | {v['kvmoff']:.3f} | {v['nvhe']:.3f} | {v['vhe']:.3f} | {v['pkvm']:.3f} | "
                  + " | ".join(cells) + " |")
    key = ("lat_mem_rd_rand", 16, 64.0)
    print(f"\nRand Mem, pkvm against kvmoff / vhe / nvhe, exact Mann-Whitney p: "
          + " / ".join(fmt_p(mann_whitney_p(data[b][key], data["pkvm"][key])) for b in ("kvmoff", "vhe", "nvhe")) + ".")
    print("The last column compares two boots that have the same translation regime (the kernel runs at EL2 "
          "with VHE in both); it shows how large a difference between boots can be without any stage-2.")


def section_llc(data):
    print("\n## 2. LLC-boundary point (sequential, stride 256, 8 MB): per-iteration values (ns)\n")
    key = ("lat_mem_rd_load", 256, 8.0)
    print(f"| config | iter 1..10 | runs >= {SPLITS[0]} ns | runs >= {SPLITS[1]} ns | mean | SD | median |")
    print("|---|---|:---:|:---:|---:|---:|---:|")
    for c in CFGS:
        v = data[c][key]
        print(f"| {c} | {' '.join(f'{x:.2f}' for x in v)} | {sum(x >= SPLITS[0] for x in v)}/{len(v)} | "
              f"{sum(x >= SPLITS[1] for x in v)}/{len(v)} | {mean(v):.3f} | {stdev(v):.2f} | {median(v):.3f} |")
    allv = sorted((x, c) for c in CFGS for x in data[c][key])
    between = [f"{c} {x:.2f}" for x, c in allv if 10.75 < x < 12.2]
    low = [x for x, _ in allv if x <= 10.75]
    high = [x for x, _ in allv if x >= 12.2]
    print(f"\nThe 40 values form two groups, {low[0]:.2f}-{low[-1]:.2f} ns ({len(low)} values) and "
          f"{high[0]:.2f}-{high[-1]:.2f} ns ({len(high)} values); in between: {', '.join(between)}. "
          "The count of 'slow' runs therefore depends on where the line is drawn.")
    print("\nMean of the runs at or above 12.2 ns / at or below 10.75 ns, per config: "
          + "; ".join(f"{c} {mean([x for x in data[c][key] if x >= 12.2]):.2f} / {mean([x for x in data[c][key] if x <= 10.75]):.2f}"
                      for c in CFGS) + ".")
    a, b = data["kvmoff"][key], data["pkvm"][key]
    t, df = welch(a, b)
    lo, hi = bootstrap_mean_diff(a, b)
    print(f"\npkvm - kvmoff: mean difference {mean(b) - mean(a):+.3f} ns ({100 * (mean(b) / mean(a) - 1):+.2f}%); "
          f"Welch t = {t:.2f} (df = {df:.1f}); exact permutation p = {exact_permutation_p(a, b):.4f} (means), "
          f"{exact_permutation_p(a, b, median):.4f} (medians); exact Mann-Whitney p = {mann_whitney_p(a, b):.3f}; "
          f"bootstrap 95% interval of the mean difference [{lo:+.2f}, {hi:+.2f}] ns "
          f"({100 * lo / mean(a):+.1f}% to {100 * hi / mean(a):+.1f}%).")
    for cut in SPLITS:
        ka, kb = sum(x >= cut for x in a), sum(x >= cut for x in b)
        print(f"Fisher exact test on the counts at the {cut} ns cut ({kb}/10 against {ka}/10): p = {fisher_p(kb, 10, ka, 10):.2f}.")

    print("\nSame working set at the other strides, per iteration (ns):\n")
    print("| stride | config | iter 1..10 | mean | pkvm vs kvmoff (means) |")
    print("|---:|---|---|---:|---:|")
    for s in (64, 128, 512, 1024):
        for c in CFGS:
            v = data[c][("lat_mem_rd_load", s, 8.0)]
            rel = ""
            if c == "pkvm":
                rel = f"{100 * (mean(v) / mean(data['kvmoff'][('lat_mem_rd_load', s, 8.0)]) - 1):+.1f}%"
            print(f"| {s} | {c} | {' '.join(f'{x:.2f}' for x in v)} | {mean(v):.3f} | {rel} |")

    print("\nNeighbouring sizes at stride 256 (mean and coefficient of variation per config):\n")
    print("| size | " + " | ".join(CFGS) + " | pkvm vs kvmoff | pkvm vs vhe | vhe vs kvmoff |")
    print("|---:|" + "---:|" * (len(CFGS) + 3))
    for sz in (4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0):
        k = ("lat_mem_rd_load", 256, sz)
        m = {c: mean(data[c][k]) for c in CFGS}
        row = [f"{m[c]:.2f} ns, CV {100 * stdev(data[c][k]) / m[c]:.1f}%" for c in CFGS]
        print(f"| {sz:g} MB | " + " | ".join(row) + f" | {100 * (m['pkvm'] / m['kvmoff'] - 1):+.1f}% | "
              f"{100 * (m['pkvm'] / m['vhe'] - 1):+.1f}% | {100 * (m['vhe'] / m['kvmoff'] - 1):+.1f}% |")


def section_random(data):
    print("\n## 3. Random access (lmbench -t, stride 16): medians and the protected-mode increment\n")
    print("increment = median(pkvm) - median of the three baseline medians.  The interval is a 95% percentile "
          "bootstrap of that quantity with all four groups resampled (20000 draws); it treats iterations as "
          "independent, see the note at the top of the script.\n")
    print("| size | pages | kvmoff | nvhe | vhe | pkvm | increment (ns) | 95% interval (ns) | relative to kvmoff | "
          "spread of the 3 baseline medians (ns) | pkvm runs above all 30 baseline runs |")
    print("|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|:---:|")
    sizes = sorted({k[2] for k in data["kvmoff"] if k[0] == "lat_mem_rd_rand"})
    for s in sizes:
        if s < 0.25:
            continue
        key = ("lat_mem_rd_rand", 16, s)
        groups = {c: data[c][key] for c in CFGS}
        md = {c: median(groups[c]) for c in CFGS}
        base = median([md[c] for c in BASE])
        spread = max(md[c] for c in BASE) - min(md[c] for c in BASE)
        lo, hi = bootstrap_increment(groups, seed=int(s * 1024))
        top = max(x for c in BASE for x in groups[c])
        above = sum(1 for x in groups["pkvm"] if x > top)
        print(f"| {s:g} MB | {int(s * 256)} | {md['kvmoff']:.2f} | {md['nvhe']:.2f} | {md['vhe']:.2f} | {md['pkvm']:.2f} | "
              f"{md['pkvm'] - base:+.2f} | [{lo:+.2f}, {hi:+.2f}] | {100 * (md['pkvm'] / md['kvmoff'] - 1):+.2f}% | "
              f"{spread:.2f} | {above}/10 |")

    print("\nPer-iteration values at 64 MB (every mode has two or three faster iterations):\n")
    for c in CFGS:
        print(f"- {c}: " + " ".join(f"{x:.1f}" for x in data[c][("lat_mem_rd_rand", 16, 64.0)]))

    print("\npkvm (10 runs) against the 30 pooled runs of the three baselines, Monte-Carlo permutation test on "
          "the difference of medians (200000 shuffles).  This says that the pkvm boot differs from the other "
          "three boots; it does not by itself attribute the difference to the boot mode.\n")
    print("| size | median pooled baselines | median pkvm | difference (ns) | two-sided p |")
    print("|---:|---:|---:|---:|---:|")
    rng = random.Random(7)
    for s in (4.0, 8.0, 16.0, 32.0, 64.0):
        key = ("lat_mem_rd_rand", 16, s)
        pooled = [x for c in BASE for x in data[c][key]]
        pk = data["pkvm"][key]
        obs = median(pk) - median(pooled)
        allv = pooled + pk
        hits = 0
        shuffles = 200000
        for _ in range(shuffles):
            rng.shuffle(allv)
            if abs(median(allv[:len(pk)]) - median(allv[len(pk):])) >= abs(obs) - 1e-12:
                hits += 1
        print(f"| {s:g} MB | {median(pooled):.2f} | {median(pk):.2f} | {obs:+.2f} | {(hits + 1) / (shuffles + 1):.6f} |")


def section_sessions(data, sa):
    print("\n## 4. One boot session as the unit: the suite runs and the stand-alone runs\n")
    if not sa:
        print("(results/standalone-mem-bench not found)")
        return
    print("results/standalone-mem-bench holds a second set of sessions (10 runs each of a short memory-only "
          "test).  The logs carry no date, kernel or boot identification; that they were taken on the N90 in "
          "the four modes on other boots is stated only in docs/n90-kvm-host/standalone-memory-bench-validation.md.\n")
    print("Random access, median of the 10 runs of each session (ns):\n")
    print("| size | suite kvmoff | suite nvhe | suite vhe | alone kvmoff | alone nvhe | alone vhe | range of the 6 | "
          "suite pkvm | alone pkvm | smallest pkvm minus largest baseline |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in (4.0, 8.0, 16.0, 32.0, 64.0):
        suite = {c: median(data[c][("lat_mem_rd_rand", 16, s)]) for c in CFGS}
        alone = {c: median(sa[c][("rand", s)]) for c in CFGS}
        six = [suite[c] for c in BASE] + [alone[c] for c in BASE]
        print(f"| {s:g} MB | " + " | ".join(f"{suite[c]:.2f}" for c in BASE) + " | "
              + " | ".join(f"{alone[c]:.2f}" for c in BASE)
              + f" | {max(six) - min(six):.2f} | {suite['pkvm']:.2f} | {alone['pkvm']:.2f} | "
              f"{min(suite['pkvm'], alone['pkvm']) - max(six):+.2f} |")
    print("\nWith sessions as the unit there are 2 protected sessions against 6 others; both protected medians "
          "lie above all six.  The probability of that ordering if the mode made no difference is 1/28 = 0.036.\n")
    print("Stand-alone sessions, the three Figure 7 points (10-run means; exact permutation p on means):\n")
    print("| point | kvmoff | nvhe | vhe | pkvm | pkvm vs kvmoff (p) | pkvm vs nvhe | pkvm vs vhe |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, key in (("seq stride 256, 8 MB", ("seq", 8.0)), ("seq stride 256, 64 MB", ("seq", 64.0)),
                      ("rand, 64 MB", ("rand", 64.0))):
        m = {c: mean(sa[c][key]) for c in CFGS}
        p = exact_permutation_p(sa["kvmoff"][key], sa["pkvm"][key])
        print(f"| {name} | {m['kvmoff']:.3f} | {m['nvhe']:.3f} | {m['vhe']:.3f} | {m['pkvm']:.3f} | "
              f"{100 * (m['pkvm'] / m['kvmoff'] - 1):+.2f}% ({fmt_p(p)}) | {100 * (m['pkvm'] / m['nvhe'] - 1):+.2f}% | "
              f"{100 * (m['pkvm'] / m['vhe'] - 1):+.2f}% |")
    print("\nStand-alone sessions, seq stride 256 at 8 MB, per run (ns):\n")
    for c in CFGS:
        v = sa[c][("seq", 8.0)]
        print(f"- {c}: " + " ".join(f"{x:.2f}" for x in v)
              + f"  (>= {SPLITS[0]}: {sum(x >= SPLITS[0] for x in v)}, >= {SPLITS[1]}: {sum(x >= SPLITS[1] for x in v)})")


def section_sequential(data):
    print("\n## 5. Sequential access at 64 MB by stride (one page crossing every 4096/stride accesses), medians (ns)\n")
    print("The last column is what 7 ns per page crossing would add, 7 ns being the random-access increment.  "
          "No cost per page crossing can be derived from these rows: pkvm lies above kvmoff and nvhe at some "
          "strides, but the vhe boot, which has no host stage-2 either, lies above pkvm.\n")
    print("| stride | crossings per access | kvmoff | nvhe | vhe | pkvm | pkvm - kvmoff | pkvm - nvhe | pkvm - vhe | "
          "vhe - kvmoff | 7 ns x crossings |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in (16, 32, 64, 128, 256, 512, 1024):
        key = ("lat_mem_rd_load", s, 64.0)
        md = {c: median(data[c][key]) for c in CFGS}
        print(f"| {s} | {s / 4096:.4f} | {md['kvmoff']:.3f} | {md['nvhe']:.3f} | {md['vhe']:.3f} | {md['pkvm']:.3f} | "
              f"{md['pkvm'] - md['kvmoff']:+.3f} | {md['pkvm'] - md['nvhe']:+.3f} | {md['pkvm'] - md['vhe']:+.3f} | "
              f"{md['vhe'] - md['kvmoff']:+.3f} | {7 * s / 4096:.3f} |")


def section_state(data, noisy):
    print("\n## 6. Quiesced nVHE host against the non-quiesced nVHE host (neither has a host stage-2)\n")
    print("results/n90-day3-host/n90-nvhe-noisy-full-* was taken on the same machine, kernel and KVM mode before "
          "the background services were masked (according to the June documents; the result files record only "
          "the kernel and its command line).  Medians of 10 iterations.\n")
    print("| size | random: quiesced | random: non-quiesced | change | seq stride 256: quiesced | seq stride 256: non-quiesced | change |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for s in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0):
        ra = median(data["nvhe"][("lat_mem_rd_rand", 16, s)])
        rb = median(noisy[("lat_mem_rd_rand", 16, s)])
        qa = median(data["nvhe"][("lat_mem_rd_load", 256, s)])
        qb = median(noisy[("lat_mem_rd_load", 256, s)])
        print(f"| {s:g} MB | {ra:.2f} | {rb:.2f} | {100 * (rb / ra - 1):+.1f}% ({rb - ra:+.1f} ns) | {qa:.2f} | {qb:.2f} | {100 * (qb / qa - 1):+.1f}% |")
    print("\nSequential stride 256 at 8 MB, per iteration (ns):\n")
    print("- quiesced nvhe: " + " ".join(f"{x:.2f}" for x in data["nvhe"][("lat_mem_rd_load", 256, 8.0)]))
    print("- non-quiesced nvhe: " + " ".join(f"{x:.2f}" for x in noisy[("lat_mem_rd_load", 256, 8.0)]))
    n_hi = sum(x >= SPLITS[0] for s in (128, 256, 512, 1024) for x in noisy[("lat_mem_rd_load", s, 8.0)])
    print(f"\nNon-quiesced run, strides 128 to 1024 at 8 MB: {n_hi} of 40 values at or above {SPLITS[0]} ns.")

    print("\n## 7. Single runs of the quiesced data sets that are faster than the median of their config (random access)\n")
    print("Counts of runs more than 4%, 8% and 15% below the median, as kvmoff/nvhe/vhe/pkvm.  The non-quiesced "
          "run is 18% to 35% below the quiesced one, so only the last column counts runs that reach that level "
          "completely; lmbench reports the fastest of 11 timed intervals, and a run that is a few percent low "
          "can be one in which some of the laps of that interval were fast.\n")
    print("| size | > 4% below | > 8% below | > 15% below |")
    print("|---:|---|---|---|")
    tot = {t: [0, 0, 0, 0] for t in (0.04, 0.08, 0.15)}
    for s in (3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0):
        key = ("lat_mem_rd_rand", 16, s)
        cells = []
        for t in (0.04, 0.08, 0.15):
            counts = [sum(1 for x in data[c][key] if x < (1 - t) * median(data[c][key])) for c in CFGS]
            for i, n in enumerate(counts):
                tot[t][i] += n
            cells.append(f"{sum(counts)} ({'/'.join(str(n) for n in counts)})")
        print(f"| {s:g} MB | " + " | ".join(cells) + " |")
    print("| all sizes | " + " | ".join(f"{sum(tot[t])} ({'/'.join(str(n) for n in tot[t])})" for t in (0.04, 0.08, 0.15)) + " |")


def section_persistence(data):
    print("\n## 8. Does the high level of the sequential test carry over to the next size measured?\n")
    print("lmbench measures the sizes of one stride in ascending order, each in a fresh child process about one "
          "second after the previous one.  high = more than 12% above the median of the lower half of the 40 "
          "values of that stride and size.  Expected = the count if the two sizes were unrelated within each "
          "(config, stride); p from 20000 random re-pairings of the iterations within each (config, stride).\n")
    print("| first measurement | second measurement | high at the first | high at the second | high at both | expected | one-sided p |")
    print("|---|---|---:|---:|---:|---:|---:|")
    rng = random.Random(11)
    strides = (64, 128, 256, 512, 1024)

    def high(stride, size):
        allv = sorted(x for c in CFGS for x in data[c][("lat_mem_rd_load", stride, size)])
        cut = 1.12 * median(allv[:len(allv) // 2])
        return {c: [x > cut for x in data[c][("lat_mem_rd_load", stride, size)]] for c in CFGS}

    def row(first, second, strata):
        both = sum(sum(x and y for x, y in zip(ha, hb)) for ha, hb in strata)
        exp = sum(sum(ha) * sum(hb) / len(ha) for ha, hb in strata)
        hits = 0
        draws = 20000
        for _ in range(draws):
            tot = 0
            for ha, hb in strata:
                if not any(ha) or not any(hb):
                    continue
                perm = hb[:]
                rng.shuffle(perm)
                tot += sum(x and y for x, y in zip(ha, perm))
            if tot >= both:
                hits += 1
        print(f"| {first} | {second} | {sum(sum(ha) for ha, _ in strata)} | {sum(sum(hb) for _, hb in strata)} | "
              f"{both} | {exp:.1f} | {(hits + 1) / (draws + 1):.4f} |")

    for a, b in ((6.0, 8.0), (8.0, 12.0), (12.0, 16.0), (16.0, 24.0)):
        strata = []
        for s in strides:
            ha, hb = high(s, a), high(s, b)
            strata += [(ha[c], hb[c]) for c in CFGS]
        row(f"{a:g} MB, strides 64-1024", f"{b:g} MB, same stride and iteration", strata)
    strata = []
    for s1, s2 in ((128, 256), (256, 512), (512, 1024)):
        ha, hb = high(s1, 8.0), high(s2, 8.0)
        strata += [(ha[c], hb[c]) for c in CFGS]
    row("8 MB, strides 128, 256, 512", "8 MB at the next stride (about a minute later), same iteration", strata)
    strata = []
    for s in (128, 256, 512, 1024):
        h = high(s, 8.0)
        strata += [(h[c][:-1], h[c][1:]) for c in CFGS]
    row("8 MB, strides 128-1024", "8 MB, same stride, next iteration (about ten minutes later)", strata)


def section_after_high(data):
    print("\n## 9. What the next sizes read right after a high 8 MB point\n")
    print("Same sweeps as section 8 (strides 64-1024, four quiesced boots, ten iterations each: 200 sweeps).  Every value "
          "is divided by the median of the lower half of the 40 values of its stride and size.  The sweeps are split by "
          "whether their 8 MB point was high (more than 1.12).  If a high 8 MB point came from the frames of that child's "
          "buffer and the next child took the same frames back (as every 12 MB child did on the N80, Exp H7), two thirds "
          "of the 12 MB buffer and half of the 16 MB buffer would be those frames.\n")
    strides = (64, 128, 256, 512, 1024)

    def rel(stride, size):
        allv = sorted(x for c in CFGS for x in data[c][("lat_mem_rd_load", stride, size)])
        low = median(allv[:len(allv) // 2])
        return {c: [x / low for x in data[c][("lat_mem_rd_load", stride, size)]] for c in CFGS}

    def quart(v):
        v = sorted(v)
        return f"{v[len(v) // 4]:.3f} / {median(v):.3f} / {v[(3 * len(v)) // 4]:.3f}"

    print("| size | 8 MB point of the sweep | sweeps | quartiles of value / low level | within 0.97-1.04 | 1.04-1.12 | above 1.12 | above 1.20 |")
    print("|---:|---|---:|---|---:|---:|---:|---:|")
    hist = {}
    for size in (12.0, 16.0, 24.0, 32.0):
        groups = {"high": [], "low": []}
        for s in strides:
            r8, rn = rel(s, 8.0), rel(s, size)
            for c in CFGS:
                for a, b in zip(r8[c], rn[c]):
                    groups["high" if a > 1.12 else "low"].append(b)
        for name in ("high", "low"):
            v = groups[name]
            print(f"| {size:g} MB | {name} | {len(v)} | {quart(v)} | {sum(1 for x in v if 0.97 <= x <= 1.04)} | "
                  f"{sum(1 for x in v if 1.04 < x <= 1.12)} | {sum(1 for x in v if x > 1.12)} | {sum(1 for x in v if x > 1.20)} |")
        hist[size] = groups["high"]
    print("\n12 MB value / low level in the sweeps whose 8 MB point was high, by stride (count: median, number above 1.12):\n")
    for s in strides:
        r8, rn = rel(s, 8.0), rel(s, 12.0)
        v = [b for c in CFGS for a, b in zip(r8[c], rn[c]) if a > 1.12]
        print(f"- stride {s}: {len(v)}: {median(v):.3f}, {sum(1 for x in v if x > 1.12)}")
    print("\nHistogram of the 12 MB value / low level after a high 8 MB point (bins of 0.04):\n")
    print("```")
    lo = 0.94
    while lo < 1.30:
        n = sum(1 for x in hist[12.0] if lo <= x < lo + 0.04)
        print(f"{lo:.2f}-{lo + 0.04:.2f} {'#' * n} {n}")
        lo += 0.04
    print("```")


def main():
    data = {cfg: load_csv(name) for cfg, name in FILES.items()}
    noisy = load_csv(NOISY)
    section_figure7(data)
    section_llc(data)
    section_random(data)
    section_sessions(data, load_standalone())
    section_sequential(data)
    section_state(data, noisy)
    section_persistence(data)
    section_after_high(data)


if __name__ == "__main__":
    main()
