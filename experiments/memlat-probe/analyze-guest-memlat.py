#!/usr/bin/env python3
"""Guest-side memory latency (the data behind the paper's Figure 8).

IMPORTANT: every number printed here was measured INSIDE an x-kernel guest
(lmbench running in the guest) on the N90.  It is a different data set from
the host 4-mode runs analysed by analyze-host-memlat.py.

Parses the raw per-iteration lmbench reports of the four guest data sets with
the repository's parse-lmbench.py and prints, as Markdown:

  1. random-access medians per size for the four guests and the ratios used
     in Figure 8 (pVM/nVHE, pVM/VHE, NP/nVHE);
  2. per-iteration values at 8 MB and 64 MB;
  3. sequential medians at 8 MB and 64 MB for every stride;
  4. the guest numbers next to the host numbers (N90 host, 4 modes).

Standard library only.  Usage:  python3 analyze-guest-memlat.py [repo_root]
"""
import collections
import csv
import io
import os
import re
import statistics as st
import subprocess
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(ROOT, "results")
GUESTS = collections.OrderedDict([
    ("regular VM on VHE host", "xkernel-n90-kvm-vhe-20260605-201819"),
    ("regular VM on nVHE host", "xkernel-n90-kvm-nvhe-20260606-133103"),
    ("NP VM on pKVM host", "xkernel-n90-pkvm-np-clean-20260606-164648"),
    ("pVM on pKVM host", "xkernel-n90-pkvm-pvm-20260605-163040"),
])
HOSTS = collections.OrderedDict([
    ("host kvmoff", "n90-kvmoff-noLSM-full-cpu0.csv"),
    ("host pkvm (try2)", "n90-pkvm-noLSM-try2-cpu0.csv"),
])


def collect(reader):
    d = collections.defaultdict(dict)
    for r in reader:
        if r["bench"] not in ("lat_mem_rd_load", "lat_mem_rd_rand"):
            continue
        m = re.match(r"stride(\d+)_sz([\d.]+)MB", r["variant"])
        if m:
            d[(r["bench"], int(m.group(1)), float(m.group(2)))][int(r["iter"])] = float(r["value"])
    return d


def load_guest(dirname):
    files = sorted(f for f in os.listdir(os.path.join(RES, dirname)) if re.search(r"-iter\d+\.txt$", f))
    out = subprocess.run([sys.executable, os.path.join(ROOT, "parse-lmbench.py")]
                         + [os.path.join(RES, dirname, f) for f in files],
                         capture_output=True, text=True, check=True).stdout
    return collect(csv.DictReader(io.StringIO(out)))


def load_host(name):
    with open(os.path.join(RES, "n90-day3-host", name)) as fh:
        return collect(csv.DictReader(fh))


def med(d, key):
    return st.median(d[key].values())


def main():
    g = {k: load_guest(v) for k, v in GUESTS.items()}
    h = {k: load_host(v) for k, v in HOSTS.items()}
    names = list(GUESTS)
    vhe, nvhe, np_, pvm = names

    print("All numbers in sections 1-3 were measured inside the guest.\n")
    print("## 1. Guest random access (lmbench -t, stride 16), medians in ns\n")
    print("| size | " + " | ".join(names) + " | pVM vs nVHE VM | pVM vs VHE VM | NP vs nVHE VM | pVM - nVHE VM (ns) |")
    print("|---:|" + "---:|" * (len(names) + 4))
    sizes = sorted({k[2] for k in g[pvm] if k[0] == "lat_mem_rd_rand"})
    for s in sizes:
        if s < 0.5:
            continue
        key = ("lat_mem_rd_rand", 16, s)
        m = {n: med(g[n], key) for n in names}
        print(f"| {s:g} MB | " + " | ".join(f"{m[n]:.2f}" for n in names)
              + f" | {100 * (m[pvm] / m[nvhe] - 1):+.1f}% | {100 * (m[pvm] / m[vhe] - 1):+.1f}% | "
                f"{100 * (m[np_] / m[nvhe] - 1):+.1f}% | {m[pvm] - m[nvhe]:+.1f} |")

    print("\n## 2. Guest random access per iteration (ns)\n")
    for s in (8.0, 64.0):
        print(f"{s:g} MB:\n")
        for n in names:
            v = g[n][("lat_mem_rd_rand", 16, s)]
            print(f"- {n}: " + " ".join(f"{v[i]:.1f}" for i in sorted(v)))
        print()

    print("## 3. Guest sequential access, medians in ns\n")
    print("| stride | size | " + " | ".join(names) + " | pVM vs nVHE VM |")
    print("|---:|---:|" + "---:|" * (len(names) + 1))
    for stv in sorted({k[1] for k in g[pvm] if k[0] == "lat_mem_rd_load"}):
        for s in (8.0, 64.0):
            key = ("lat_mem_rd_load", stv, s)
            m = {n: med(g[n], key) for n in names}
            print(f"| {stv} | {s:g} MB | " + " | ".join(f"{m[n]:.3f}" for n in names)
                  + f" | {100 * (m[pvm] / m[nvhe] - 1):+.2f}% |")

    print("\n## 4. Guest next to host, random access medians in ns\n")
    print("Host columns were measured on the host Linux with no VM running.\n")
    print("| size | " + " | ".join(list(HOSTS) + names) + " |")
    print("|---:|" + "---:|" * (len(HOSTS) + len(names)))
    for s in (2.0, 3.0, 4.0, 6.0, 8.0, 16.0, 32.0, 64.0):
        key = ("lat_mem_rd_rand", 16, s)
        print(f"| {s:g} MB | " + " | ".join(f"{med(h[n], key):.2f}" for n in HOSTS) + " | "
              + " | ".join(f"{med(g[n], key):.2f}" for n in names) + " |")


if __name__ == "__main__":
    main()
