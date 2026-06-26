#!/usr/bin/env python3
"""Summarize Pixel MADV DiD rows across boot pairs.

Input rows are produced by pixel-analyze-madv-entry-slope.py. The summary keeps
the point estimate separate from the resolution floor, so a near-zero result can
be reported as an upper bound instead of over-read as "zero cost".
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, action="append", required=True)
    p.add_argument("--label", default="all")
    p.add_argument("--bootstrap-reps", type=int, default=10000)
    p.add_argument("--seed", type=int, default=1)
    return p.parse_args(argv)


def read_values(paths: list[Path]) -> tuple[list[float], list[float]]:
    per_entry: list[float] = []
    drift: list[float] = []
    for path in paths:
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    per_entry.append(float(row["per_entry_cost_did_ns_per_op"]))
                    drift.append(float(row["drift_delta_ns_per_op"]))
                except (KeyError, TypeError, ValueError):
                    # Allows concatenated CSVs with repeated headers.
                    continue
    if not per_entry:
        raise ValueError("no usable boot-pair rows")
    return per_entry, drift


def mad(values: list[float]) -> float:
    med = statistics.median(values)
    return statistics.median([abs(v - med) for v in values])


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        raise ValueError("empty percentile input")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = pct * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def bootstrap_median_ci(values: list[float], reps: int, seed: int) -> tuple[float, float]:
    med = statistics.median(values)
    if reps <= 0 or len(values) < 2:
        return med, med
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(reps):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(statistics.median(sample))
    samples.sort()
    return percentile(samples, 0.025), percentile(samples, 0.975)


def fmt(v: float) -> str:
    return f"{v:.6f}"


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    per_entry, drift = read_values(args.input)

    per_median = statistics.median(per_entry)
    per_mean = statistics.fmean(per_entry)
    drift_median = statistics.median(drift)
    drift_mean = statistics.fmean(drift)
    per_low, per_high = bootstrap_median_ci(per_entry, args.bootstrap_reps, args.seed)
    drift_low, drift_high = bootstrap_median_ci(drift, args.bootstrap_reps, args.seed + 17)
    per_half = max(abs(per_median - per_low), abs(per_high - per_median))
    drift_half = max(abs(drift_median - drift_low), abs(drift_high - drift_median))
    abs_median_drift = abs(drift_median)
    resolution_floor = max(per_half, drift_half, abs_median_drift)

    fieldnames = [
        "label",
        "n_boot_pairs",
        "per_entry_median_ns_per_op",
        "per_entry_mean_ns_per_op",
        "per_entry_mad_ns_per_op",
        "per_entry_ci95_low_ns_per_op",
        "per_entry_ci95_high_ns_per_op",
        "per_entry_ci95_half_width_ns_per_op",
        "drift_delta_median_ns_per_op",
        "drift_delta_mean_ns_per_op",
        "drift_delta_mad_ns_per_op",
        "drift_delta_ci95_low_ns_per_op",
        "drift_delta_ci95_high_ns_per_op",
        "drift_delta_ci95_half_width_ns_per_op",
        "abs_median_drift_ns_per_op",
        "resolution_floor_ns_per_op",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(
        {
            "label": args.label,
            "n_boot_pairs": len(per_entry),
            "per_entry_median_ns_per_op": fmt(per_median),
            "per_entry_mean_ns_per_op": fmt(per_mean),
            "per_entry_mad_ns_per_op": fmt(mad(per_entry)),
            "per_entry_ci95_low_ns_per_op": fmt(per_low),
            "per_entry_ci95_high_ns_per_op": fmt(per_high),
            "per_entry_ci95_half_width_ns_per_op": fmt(per_half),
            "drift_delta_median_ns_per_op": fmt(drift_median),
            "drift_delta_mean_ns_per_op": fmt(drift_mean),
            "drift_delta_mad_ns_per_op": fmt(mad(drift)),
            "drift_delta_ci95_low_ns_per_op": fmt(drift_low),
            "drift_delta_ci95_high_ns_per_op": fmt(drift_high),
            "drift_delta_ci95_half_width_ns_per_op": fmt(drift_half),
            "abs_median_drift_ns_per_op": fmt(abs_median_drift),
            "resolution_floor_ns_per_op": fmt(resolution_floor),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
