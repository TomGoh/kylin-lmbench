#!/usr/bin/env python3
"""Guest-side memory latency (the data behind the paper's Figure 8).

IMPORTANT: every number printed in sections 1 to 3 was measured INSIDE an
x-kernel guest (lmbench running in the guest) on the N90.  It is a different
data set from the host 4-mode runs analysed by analyze-host-memlat.py.

What the four guest data sets are is known only from their directory names
and from the ENV_TAG in their marker files; nothing in them records the
host's boot mode, the host kernel, the VM type or the crosvm options.
Section 0 prints what the files themselves say.  In particular the set whose
directory name says pVM carries the ENV_TAG of the non-protected set.

Parses the raw per-iteration lmbench reports of the four guest data sets with
the repository's parse-lmbench.py and prints, as Markdown:

  0. what identifies each data set;
  1. random-access medians per size for the four guests, and the three ratios
     of Figure 8 (pVM/nVHE, pVM/VHE, NP/nVHE) by medians and by 10-run means
     (Figure 8 is built from means);
  2. per-iteration values at 8 MB and 64 MB;
  3. sequential access at 8 MB and 64 MB for every stride, with the
     per-iteration values of the 8 MB stride-256 point;
  4. the guest numbers next to host numbers (N90 host), including the host
     run that was taken before the background services were masked.

Standard library only.  Usage:  python3 analyze-guest-memlat.py [repo_root]
"""
import collections
import csv
import io
import os
import re
import subprocess
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(ROOT, "results")
ITERS = 10
# label (from the directory name) -> directory
GUESTS = collections.OrderedDict([
    ("VM on VHE host", "xkernel-n90-kvm-vhe-20260605-201819"),
    ("VM on nVHE host", "xkernel-n90-kvm-nvhe-20260606-133103"),
    ("NP VM on pKVM host", "xkernel-n90-pkvm-np-clean-20260606-164648"),
    ("set labelled pVM", "xkernel-n90-pkvm-pvm-20260605-163040"),
])
HOSTS = collections.OrderedDict([
    ("host kvmoff, quiesced", "n90-kvmoff-noLSM-full-cpu0.csv"),
    ("host pkvm (try2), quiesced", "n90-pkvm-noLSM-try2-cpu0.csv"),
    ("host nvhe, not quiesced", "n90-nvhe-noisy-full-cpu0.csv"),
])


def mean(v):
    return sum(v) / len(v)


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def collect(reader, what):
    d = collections.defaultdict(dict)
    for r in reader:
        if r["bench"] not in ("lat_mem_rd_load", "lat_mem_rd_rand"):
            continue
        m = re.match(r"stride(\d+)_sz([\d.]+)MB$", r["variant"])
        if not m:
            sys.exit(f"{what}: unexpected variant {r['variant']!r}")
        key = (r["bench"], int(m.group(1)), float(m.group(2)))
        it = int(r["iter"])
        if it in d[key]:
            sys.exit(f"{what}: duplicate row {key} iteration {it}")
        d[key][it] = float(r["value"])
    out = {}
    for key, per_iter in d.items():
        if sorted(per_iter) != list(range(1, ITERS + 1)):
            sys.exit(f"{what}: {key} has iterations {sorted(per_iter)}, expected 1..{ITERS}")
        out[key] = [per_iter[i] for i in range(1, ITERS + 1)]
    return out


def load_guest(dirname):
    """Returns (data, facts); facts are what the directory's own files say about the run."""
    path = os.path.join(RES, dirname)
    files = sorted(f for f in os.listdir(path) if re.search(r"-iter\d+\.txt$", f))
    run = subprocess.run([sys.executable, os.path.join(ROOT, "parse-lmbench.py")]
                         + [os.path.join(path, f) for f in files],
                         capture_output=True, text=True, check=True)
    facts = {"reports": len(files), "prefix": re.sub(r"-iter\d+\.txt$", "", files[0]),
             "unparsed": sum(1 for line in run.stderr.splitlines() if "UNPARSED" in line)}
    with open(os.path.join(path, "started.txt")) as fh:
        lines = fh.read().splitlines()
    facts["started"] = lines[0]
    m = re.search(r"ENV_TAG=(\S+)", "\n".join(lines))
    facts["env_tag"] = m.group(1) if m else "?"
    return collect(csv.DictReader(io.StringIO(run.stdout)), dirname), facts


def load_host(name):
    with open(os.path.join(RES, "n90-day3-host", name)) as fh:
        return collect(csv.DictReader(fh), name)


def main():
    g, facts = {}, {}
    for label, dirname in GUESTS.items():
        g[label], facts[label] = load_guest(dirname)
    h = {k: load_host(v) for k, v in HOSTS.items()}
    names = list(GUESTS)
    vhe, nvhe, np_, pvm = names

    print("All numbers in sections 1-3 were measured inside the guest.\n")
    print("## 0. What identifies each guest data set\n")
    print("| label used below (from the directory name) | directory | ENV_TAG in started.txt | report file prefix | "
          "first line of started.txt | reports | lines the parser did not recognise |")
    print("|---|---|---|---|---|---:|---:|")
    for n in names:
        f = facts[n]
        print(f"| {n} | {GUESTS[n]} | {f['env_tag']} | {f['prefix']} | {f['started']} | {f['reports']} | {f['unparsed']} |")
    print("\nNo file of these directories records the host boot mode, the host kernel, the VM type or the crosvm "
          "command line.  The set labelled pVM has the same ENV_TAG as the non-protected set.")

    print("\n## 1. Guest random access (lmbench -t, stride 16), ns\n")
    print("Ratios are given as median-based / mean-based; Figure 8 uses 10-run means.\n")
    print("| size | " + " | ".join(n + " (median)" for n in names)
          + " | pVM vs nVHE VM | pVM vs VHE VM | NP vs nVHE VM | pVM - nVHE VM (ns, medians) | pVM runs below all 30 other runs |")
    print("|---:|" + "---:|" * (len(names) + 4) + ":---:|")
    sizes = sorted({k[2] for k in g[pvm] if k[0] == "lat_mem_rd_rand"})
    for s in sizes:
        if s < 0.5:
            continue
        key = ("lat_mem_rd_rand", 16, s)
        md = {n: median(g[n][key]) for n in names}
        mn = {n: mean(g[n][key]) for n in names}

        def ratio(a, b):
            return f"{100 * (md[a] / md[b] - 1):+.1f}% / {100 * (mn[a] / mn[b] - 1):+.1f}%"
        floor = min(x for n in (vhe, nvhe, np_) for x in g[n][key])
        below = sum(1 for x in g[pvm][key] if x < floor)
        print(f"| {s:g} MB | " + " | ".join(f"{md[n]:.2f}" for n in names)
              + f" | {ratio(pvm, nvhe)} | {ratio(pvm, vhe)} | {ratio(np_, nvhe)} | {md[pvm] - md[nvhe]:+.1f} | {below}/10 |")

    print("\n## 2. Guest random access per iteration (ns)\n")
    for s in (8.0, 64.0):
        print(f"{s:g} MB:\n")
        for n in names:
            print(f"- {n}: " + " ".join(f"{x:.1f}" for x in g[n][("lat_mem_rd_rand", 16, s)]))
        print()

    print("## 3. Guest sequential access, ns\n")
    print("Stride 256 at 8 MB, per iteration.  Three of the sets take two values, as the quiesced hosts do; a ratio "
          "of medians or of means at this point mostly reflects how many iterations fell on the high value.\n")
    for n in names:
        v = g[n][("lat_mem_rd_load", 256, 8.0)]
        print(f"- {n}: " + " ".join(f"{x:.2f}" for x in v)
              + f"  (mean {mean(v):.3f}, median {median(v):.3f}, max/min {max(v) / min(v):.2f})")
    print("\n| stride | size | " + " | ".join(n + " (median)" for n in names)
          + " | pVM vs nVHE VM (medians / means) | max/min over iterations: " + " / ".join(names) + " |")
    print("|---:|---:|" + "---:|" * (len(names) + 1) + "---|")
    for stv in sorted({k[1] for k in g[pvm] if k[0] == "lat_mem_rd_load"}):
        for s in (8.0, 64.0):
            key = ("lat_mem_rd_load", stv, s)
            md = {n: median(g[n][key]) for n in names}
            mn = {n: mean(g[n][key]) for n in names}
            print(f"| {stv} | {s:g} MB | " + " | ".join(f"{md[n]:.3f}" for n in names)
                  + f" | {100 * (md[pvm] / md[nvhe] - 1):+.2f}% / {100 * (mn[pvm] / mn[nvhe] - 1):+.2f}% | "
                  + " / ".join(f"{max(g[n][key]) / min(g[n][key]):.2f}" for n in names) + " |")

    print("\n## 4. Guest next to host, random access medians in ns\n")
    print("Host columns were measured on the host Linux, outside any VM.  The first two host sets were taken with "
          "the background services masked; the third was taken before they were masked and is the host set whose "
          "curve the set labelled pVM follows.  Comparing a guest column with a host column of the other kind "
          "compares two states of the machine, not guest with host.\n")
    print("| size | " + " | ".join(list(HOSTS) + names) + " | set labelled pVM minus host nvhe, not quiesced |")
    print("|---:|" + "---:|" * (len(HOSTS) + len(names) + 1))
    for s in (2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0):
        key = ("lat_mem_rd_rand", 16, s)
        hm = {n: median(h[n][key]) for n in HOSTS}
        gm = {n: median(g[n][key]) for n in names}
        print(f"| {s:g} MB | " + " | ".join(f"{hm[n]:.2f}" for n in HOSTS) + " | "
              + " | ".join(f"{gm[n]:.2f}" for n in names)
              + f" | {gm[pvm] - hm['host nvhe, not quiesced']:+.2f} |")


if __name__ == "__main__":
    main()
