#!/usr/bin/env python3
"""Compute Pixel MADV per-entry slopes and DiD correction.

Inputs are four CSVs from pixel_madv_entry_slope:
  nvhe/protected x touched/untouched.

The output is one CSV row for one boot pair. It intentionally reports the raw
touched delta, the untouched drift delta, and the DiD-corrected per-entry cost.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Fit:
    slope: float
    intercept: float
    r2: float
    n_points: int
    n_rows: int
    n_min: int
    n_max: int


def read_elapsed_by_pages(
    path: Path, probe_mode: str | None = None, touch: str | None = None
) -> dict[int, list[float]]:
    groups: dict[int, list[float]] = defaultdict(list)
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "ok") != "ok":
                continue
            if row.get("reject_reason", "ok") != "ok":
                continue
            if not row_cpu_is_stable(row):
                continue
            if probe_mode is not None and row.get("mode") != probe_mode:
                continue
            if touch is not None and row.get("touch") != touch:
                continue
            pages = int(row["pages"])
            elapsed = float(row["elapsed_ns"])
            groups[pages].append(elapsed)
    if len(groups) < 2:
        raise ValueError(f"{path}: need at least two page-count groups")
    return dict(groups)


def parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def row_cpu_is_stable(row: dict[str, str]) -> bool:
    """Keep rows that stayed on one CPU, and on cpu_target if it is present."""
    before = parse_optional_int(row.get("cpu_before"))
    after = parse_optional_int(row.get("cpu_after"))
    target = parse_optional_int(row.get("cpu_target"))

    if before is not None and after is not None and before != after:
        return False
    if target is not None:
        if before is not None and before != target:
            return False
        if after is not None and after != target:
            return False
    return True


def mean_by_pages(
    path: Path, probe_mode: str | None = None, touch: str | None = None
) -> tuple[list[float], list[float], int]:
    groups = read_elapsed_by_pages(path, probe_mode, touch)
    xs = sorted(groups)
    ys = [statistics.fmean(groups[x]) for x in xs]
    n_rows = sum(len(v) for v in groups.values())
    return [float(x) for x in xs], ys, n_rows


def fit_csv(path: Path, probe_mode: str | None = None, touch: str | None = None) -> Fit:
    xs, ys, n_rows = mean_by_pages(path, probe_mode, touch)
    n = len(xs)
    xbar = statistics.fmean(xs)
    ybar = statistics.fmean(ys)
    sxx = sum((x - xbar) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError(f"{path}: degenerate page-count groups")
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
    intercept = ybar - slope * xbar
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    return Fit(
        slope=slope,
        intercept=intercept,
        r2=r2,
        n_points=n,
        n_rows=n_rows,
        n_min=int(min(xs)),
        n_max=int(max(xs)),
    )


def fmt(v: float) -> str:
    return f"{v:.6f}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot-pair-id", required=True)
    p.add_argument("--nvhe-touched", type=Path)
    p.add_argument("--protected-touched", type=Path)
    p.add_argument("--nvhe-untouched", type=Path)
    p.add_argument("--protected-untouched", type=Path)
    p.add_argument("--nvhe-csv", type=Path)
    p.add_argument("--protected-csv", type=Path)
    p.add_argument("--probe-mode", choices=("single", "batched"), default="single")
    args = p.parse_args(argv)

    split_args = [
        args.nvhe_touched,
        args.protected_touched,
        args.nvhe_untouched,
        args.protected_untouched,
    ]
    have_split = all(split_args)
    have_combined = bool(args.nvhe_csv and args.protected_csv)
    if have_split == have_combined:
        p.error(
            "provide either the four split CSVs or --nvhe-csv/--protected-csv, "
            "but not both"
        )
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.nvhe_csv and args.protected_csv:
        nvhe_touched = fit_csv(args.nvhe_csv, args.probe_mode, "touched")
        protected_touched = fit_csv(args.protected_csv, args.probe_mode, "touched")
        nvhe_untouched = fit_csv(args.nvhe_csv, args.probe_mode, "untouched")
        protected_untouched = fit_csv(args.protected_csv, args.probe_mode, "untouched")
    else:
        nvhe_touched = fit_csv(args.nvhe_touched)
        protected_touched = fit_csv(args.protected_touched)
        nvhe_untouched = fit_csv(args.nvhe_untouched)
        protected_untouched = fit_csv(args.protected_untouched)

    raw_delta = protected_touched.slope - nvhe_touched.slope
    drift_delta = protected_untouched.slope - nvhe_untouched.slope
    per_entry = raw_delta - drift_delta

    # For one boot pair, the live drift baseline is the only honest floor we can
    # compute without resampling across pairs. A multi-pair aggregator can add CI
    # half-widths; this per-pair row still carries abs(drift_delta) explicitly.
    resolution_floor = abs(drift_delta)

    fieldnames = [
        "boot_pair_id",
        "n_min",
        "n_max",
        "n_points",
        "rows_nvhe_touched",
        "rows_protected_touched",
        "rows_nvhe_untouched",
        "rows_protected_untouched",
        "s_touched_nvhe_ns_per_op",
        "s_touched_protected_ns_per_op",
        "s_untouched_nvhe_ns_per_op",
        "s_untouched_protected_ns_per_op",
        "raw_delta_ns_per_op",
        "drift_delta_ns_per_op",
        "per_entry_cost_did_ns_per_op",
        "resolution_floor_ns_per_op",
        "r2_touched_nvhe",
        "r2_touched_protected",
        "r2_untouched_nvhe",
        "r2_untouched_protected",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(
        {
            "boot_pair_id": args.boot_pair_id,
            "n_min": max(
                nvhe_touched.n_min,
                protected_touched.n_min,
                nvhe_untouched.n_min,
                protected_untouched.n_min,
            ),
            "n_max": min(
                nvhe_touched.n_max,
                protected_touched.n_max,
                nvhe_untouched.n_max,
                protected_untouched.n_max,
            ),
            "n_points": min(
                nvhe_touched.n_points,
                protected_touched.n_points,
                nvhe_untouched.n_points,
                protected_untouched.n_points,
            ),
            "rows_nvhe_touched": nvhe_touched.n_rows,
            "rows_protected_touched": protected_touched.n_rows,
            "rows_nvhe_untouched": nvhe_untouched.n_rows,
            "rows_protected_untouched": protected_untouched.n_rows,
            "s_touched_nvhe_ns_per_op": fmt(nvhe_touched.slope),
            "s_touched_protected_ns_per_op": fmt(protected_touched.slope),
            "s_untouched_nvhe_ns_per_op": fmt(nvhe_untouched.slope),
            "s_untouched_protected_ns_per_op": fmt(protected_untouched.slope),
            "raw_delta_ns_per_op": fmt(raw_delta),
            "drift_delta_ns_per_op": fmt(drift_delta),
            "per_entry_cost_did_ns_per_op": fmt(per_entry),
            "resolution_floor_ns_per_op": fmt(resolution_floor),
            "r2_touched_nvhe": fmt(nvhe_touched.r2),
            "r2_touched_protected": fmt(protected_touched.r2),
            "r2_untouched_nvhe": fmt(nvhe_untouched.r2),
            "r2_untouched_protected": fmt(protected_untouched.r2),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
