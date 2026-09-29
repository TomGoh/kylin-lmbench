#!/usr/bin/env python3
"""Check whether paired VM runs share the same hardware baseline.

The VM comparisons in docs/vm-ratio-comparison.* pair a regular VM with a
protected/confidential VM on the same machine. Host-side settings (core
clock, DRAM speed, vCPU pinning) were not recorded for every platform, so
this script looks for baseline drift in the guest's own lmbench output:

  * Group A (core-bound): lat_ops ALU/FPU latencies, L1 load latency, L1
    read bandwidth and stream2 sum. `stream2 sum` is `s += a[i]`, a serial
    FP-add dependency chain (see src/stream.c), so its bandwidth is
    8 bytes / double-add latency, not a DRAM measurement. None of these
    touch stage-2 page tables or memory encryption, so a same-clock pair
    should give a ratio of 1.000.
  * Group B (DRAM-bound): 64 MB load/random latency, 64 MB read bandwidth,
    STREAM copy/triad. These mix memory config with protection overhead.

"min ratio" compares the fastest iteration of each side, which filters out
intermittent perturbations that a clock difference would not produce.

Usage: python3 scripts/check-vm-baseline.py
"""
from __future__ import annotations

import csv
import io
import statistics as st
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DATASETS = {
    "kp_reg": "virtcca-regular-results",
    "kp_cca": "virtcca-cvm-results",
    "hg_reg": "hygon_regular_results",
    "hg_csv": "hygon_csv_results",
    "n90_vhe": "xkernel-n90-kvm-vhe-20260605-201819",
    "n90_nvhe": "xkernel-n90-kvm-nvhe-20260606-133103",
    "n90_np": "xkernel-n90-pkvm-np-clean-20260606-164648",
    "n90_pvm": "xkernel-n90-pkvm-pvm-20260605-163040",
}
PAIRS = [
    ("kp_cca", "kp_reg"),
    ("hg_csv", "hg_reg"),
    ("n90_np", "n90_nvhe"),
    ("n90_pvm", "n90_nvhe"),
]
# (bench, variant, higher_is_better)
GROUP_A = [
    ("lat_ops", "integer_add", False),
    ("lat_ops", "integer_mul", False),
    ("lat_ops", "integer_div", False),
    ("lat_ops", "int64_div", False),
    ("lat_ops", "double_add", False),
    ("lat_ops", "double_mul", False),
    ("lat_ops", "double_div", False),
    ("lat_ops", "float_div", False),
    ("lat_mem_rd_load", "stride16_sz0.00049MB", False),
    ("bw_mem_rd", "sz0.004096", True),
    ("stream2", "sum_bw", True),
]
GROUP_B = [
    ("lat_mem_rd_load", "stride128_sz64.00000MB", False),
    ("lat_mem_rd_rand", "stride16_sz64.00000MB", False),
    ("bw_mem_rd", "sz67.11", True),
    ("stream", "copy_bw", True),
    ("stream", "triad_bw", True),
]


def load(dirname: str) -> dict[tuple[str, str], list[float]]:
    files = sorted((REPO / "results" / dirname).glob("*iter*.txt"))
    if not files:
        raise FileNotFoundError(f"no *iter*.txt under results/{dirname}")
    proc = subprocess.run(
        [sys.executable, str(REPO / "parse-lmbench.py"), *map(str, files)],
        capture_output=True, text=True, check=True,
    )
    vals: dict[tuple[str, str], list[float]] = {}
    for row in csv.DictReader(io.StringIO(proc.stdout)):
        try:
            vals.setdefault((row["bench"], row["variant"]), []).append(float(row["value"]))
        except ValueError:
            continue
    return vals


def cv_pct(v: list[float]) -> float:
    return st.stdev(v) / st.mean(v) * 100 if len(v) > 1 and st.mean(v) else 0.0


def best(v: list[float], higher_is_better: bool) -> float:
    return max(v) if higher_is_better else min(v)


def main() -> None:
    data = {k: load(d) for k, d in DATASETS.items()}

    for title, group in (("A: core-bound (clock proxies)", GROUP_A),
                         ("B: DRAM-bound", GROUP_B)):
        print(f"\n## {title}\n")
        print("| metric | " + " | ".join(f"{n}/{d} mean (best) [cv n/d %]" for n, d in PAIRS) + " |")
        print("|---|" + "---:|" * len(PAIRS))
        for bench, variant, hib in group:
            cells = []
            for num, den in PAIRS:
                a, b = data[num].get((bench, variant)), data[den].get((bench, variant))
                if not a or not b:
                    cells.append("n/a")
                    continue
                cells.append(
                    f"{st.mean(a) / st.mean(b):.3f} ({best(a, hib) / best(b, hib):.3f})"
                    f" [{cv_pct(a):.1f}/{cv_pct(b):.1f}]"
                )
            print(f"| {bench}:{variant} | " + " | ".join(cells) + " |")

        print("\n| metric | " + " | ".join(DATASETS) + " |")
        print("|---|" + "---:|" * len(DATASETS))
        for bench, variant, _ in group:
            cells = []
            for k in DATASETS:
                v = data[k].get((bench, variant))
                cells.append(f"{st.mean(v):.4g}" if v else "n/a")
            print(f"| {bench}:{variant} | " + " | ".join(cells) + " |")

    print("\n## stream2 sum vs 8 B / double-add latency (MB/s)\n")
    print("| dataset | measured | 8 B / double_add | measured / predicted |")
    print("|---|---:|---:|---:|")
    for k in DATASETS:
        s = data[k].get(("stream2", "sum_bw"))
        add = data[k].get(("lat_ops", "double_add"))
        if not s or not add:
            continue
        pred = 8 / st.mean(add) * 1000  # ns -> MB/s
        print(f"| {k} | {st.mean(s):.0f} | {pred:.0f} | {st.mean(s) / pred:.3f} |")


if __name__ == "__main__":
    main()
