#!/usr/bin/env python3
"""Create auditable, boot-paired statistics for a completed D3000 campaign.

This script consumes ``metrics.csv`` from ``analyze-results.py`` and the raw
campaign tree.  Repetitions are reduced inside each boot; the five boot pairs
remain the independent experimental units.  Positive ``penalty_pct`` always
means protected/pKVM is worse, regardless of the metric's natural direction.

The percentile bootstrap interval is intentionally labelled descriptive.  At
n=5, neither it nor an exact two-sided sign test can establish a conventional
5% confirmatory result (the best possible two-sided sign-test p value is
0.0625).  The output therefore keeps observed ranges and direction counts next
to every interval.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


MetricKey = Tuple[str, str, str]
BootKey = Tuple[int, str, str, str, str]


def median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else math.nan


def mad(values: Sequence[float]) -> float:
    center = median(values)
    return median([abs(value - center) for value in values]) if values else math.nan


def percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def bootstrap_median(values: Sequence[float], rng: random.Random, iterations: int = 20000) -> Tuple[float, float]:
    if not values:
        return math.nan, math.nan
    draws = [median([rng.choice(values) for _ in values]) for _ in range(iterations)]
    return percentile(draws, 0.025), percentile(draws, 0.975)


def exact_two_sided_sign_p(values: Sequence[float], epsilon: float = 1e-12) -> float:
    nonzero = [value for value in values if abs(value) > epsilon]
    if not nonzero:
        return 1.0
    positives = sum(value > 0 for value in nonzero)
    tail = min(positives, len(nonzero) - positives)
    probability = sum(math.comb(len(nonzero), index) for index in range(tail + 1)) / (2 ** len(nonzero))
    return min(1.0, 2.0 * probability)


def average_ranks(values: Sequence[float]) -> List[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        rank = ((index + 1) + end) / 2.0
        for original_index, _ in ordered[index:end]:
            ranks[original_index] = rank
        index = end
    return ranks


def pearson(values_x: Sequence[float], values_y: Sequence[float]) -> float:
    mean_x = statistics.mean(values_x)
    mean_y = statistics.mean(values_y)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(values_x, values_y))
    denominator = math.sqrt(
        sum((x - mean_x) ** 2 for x in values_x) * sum((y - mean_y) ** 2 for y in values_y)
    )
    return numerator / denominator if denominator else 0.0


def exact_spearman_trend(values: Sequence[float]) -> Tuple[float, float]:
    """Return rho and an exact two-sided permutation p value versus pair index."""

    if len(values) < 2:
        return math.nan, math.nan
    x_ranks = list(range(1, len(values) + 1))
    y_ranks = average_ranks(values)
    observed = pearson(x_ranks, y_ranks)
    permutations = list(itertools.permutations(y_ranks))
    extreme = sum(abs(pearson(x_ranks, candidate)) >= abs(observed) - 1e-12 for candidate in permutations)
    return observed, extreme / len(permutations)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def read_env(path: Path) -> Dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def load_metric_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} has no metric rows")
    return rows


def pair_order(campaign: Path) -> Dict[int, str]:
    first = {}
    for line in (campaign / "manifest.tsv").read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) != 5 or fields[1] != "formal":
            continue
        pair = int(fields[2])
        first.setdefault(pair, fields[3])
    return first


def equivalence_margin(metric: str) -> float:
    return 5.0 if "p99" in metric else 3.0


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize_applications(metrics_path: Path, campaign: Path, out: Path) -> Tuple[List[dict], List[dict]]:
    rows = load_metric_rows(metrics_path)
    by_boot: Dict[BootKey, List[float]] = defaultdict(list)
    metadata: Dict[MetricKey, Tuple[str, bool]] = {}
    for row in rows:
        pair = int(row["pair"])
        key = (row["project"], row["scenario"], row["metric"])
        by_boot[(pair, row["mode"], *key)].append(float(row["value"]))
        metadata[key] = (row["unit"], parse_bool(row["higher_better"]))

    boot_medians = {key: median(values) for key, values in by_boot.items()}
    order = pair_order(campaign)
    summary_rows = []
    pair_rows = []
    summary_json = []
    rng = random.Random(20260717)

    for key in sorted(metadata):
        project, scenario, metric = key
        unit, higher_better = metadata[key]
        values = []
        for pair in range(1, 6):
            nvhe_key = (pair, "nvhe", *key)
            protected_key = (pair, "protected", *key)
            if nvhe_key not in boot_medians or protected_key not in boot_medians:
                continue
            nvhe = boot_medians[nvhe_key]
            protected = boot_medians[protected_key]
            raw_delta = (protected / nvhe - 1.0) * 100.0
            penalty = -raw_delta if higher_better else raw_delta
            values.append((pair, nvhe, protected, raw_delta, penalty))
            pair_rows.append(
                {
                    "project": project,
                    "scenario": scenario,
                    "metric": metric,
                    "unit": unit,
                    "higher_better": higher_better,
                    "pair": pair,
                    "first_mode": order.get(pair, "unknown"),
                    "nvhe_boot_median": nvhe,
                    "protected_boot_median": protected,
                    "raw_delta_pct": raw_delta,
                    "penalty_pct": penalty,
                }
            )
        if not values:
            continue

        penalties = [item[4] for item in values]
        boot_rmad = []
        for (pair, mode, p, s, m), repetitions in by_boot.items():
            if (p, s, m) != key:
                continue
            center = median(repetitions)
            if center:
                boot_rmad.append(mad(repetitions) / abs(center) * 100.0)
        low, high = bootstrap_median(penalties, rng)
        nvhe_first = [penalty for pair, _, _, _, penalty in values if order.get(pair) == "nvhe"]
        protected_first = [penalty for pair, _, _, _, penalty in values if order.get(pair) == "protected"]
        margin = equivalence_margin(metric)
        trend_rho, trend_p = exact_spearman_trend(penalties)
        item = {
            "project": project,
            "scenario": scenario,
            "metric": metric,
            "unit": unit,
            "higher_better": higher_better,
            "pairs": len(values),
            "nvhe_boot_median": median([value[1] for value in values]),
            "protected_boot_median": median([value[2] for value in values]),
            "median_raw_delta_pct": median([value[3] for value in values]),
            "median_penalty_pct": median(penalties),
            "mad_penalty_pct": mad(penalties),
            "min_penalty_pct": min(penalties),
            "max_penalty_pct": max(penalties),
            "worse_pairs": sum(value > 1e-12 for value in penalties),
            "better_pairs": sum(value < -1e-12 for value in penalties),
            "tied_pairs": sum(abs(value) <= 1e-12 for value in penalties),
            "exact_sign_p_two_sided": exact_two_sided_sign_p(penalties),
            "bootstrap95_low_pct": low,
            "bootstrap95_high_pct": high,
            "bootstrap_interval_is_descriptive": True,
            "equivalence_margin_pct": margin,
            "all_observed_pairs_within_margin": all(abs(value) <= margin for value in penalties),
            "bootstrap_interval_within_margin": low >= -margin and high <= margin,
            "median_within_boot_rmad_pct": median(boot_rmad),
            "nvhe_first_median_penalty_pct": median(nvhe_first),
            "protected_first_median_penalty_pct": median(protected_first),
            "order_group_gap_pct": median(nvhe_first) - median(protected_first),
            "pair_index_spearman_rho": trend_rho,
            "pair_index_permutation_p_two_sided": trend_p,
        }
        summary_rows.append(item)
        summary_json.append({**item, "pair_values": [dict(zip(("pair", "nvhe", "protected", "raw_delta_pct", "penalty_pct"), row)) for row in values]})

    summary_fields = list(summary_rows[0])
    pair_fields = list(pair_rows[0])
    write_csv(out / "application-summary.csv", summary_rows, summary_fields)
    write_csv(out / "application-pair-values.csv", pair_rows, pair_fields)
    (out / "application-summary.json").write_text(json.dumps(summary_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary_rows, pair_rows


def load_anchor_module(repo_root: Path):
    path = repo_root / "docs/mmap/scripts/plot-d3000-anchors.py"
    spec = importlib.util.spec_from_file_location("d3000_anchor_parser", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def summarize_anchors(campaign: Path, out: Path, repo_root: Path) -> Tuple[List[dict], List[dict]]:
    module = load_anchor_module(repo_root)
    data = module.load_anchors(campaign)
    order = pair_order(campaign)
    metrics = sorted({metric for _, _, _, metric in data.values})
    summary_rows = []
    pair_rows = []
    drift_rows = []
    rng = random.Random(20260718)

    for metric in metrics:
        unit = "ns" if metric.startswith("lat_mem:") else "us"
        for phase in ("start", "end"):
            values = []
            for pair in data.pairs:
                nvhe = data.values[(pair, "nvhe", phase, metric)]
                protected = data.values[(pair, "protected", phase, metric)]
                penalty = (protected / nvhe - 1.0) * 100.0
                values.append((pair, nvhe, protected, penalty))
                pair_rows.append(
                    {
                        "phase": phase,
                        "metric": metric,
                        "unit": unit,
                        "pair": pair,
                        "first_mode": order[pair],
                        "nvhe_boot_median": nvhe,
                        "protected_boot_median": protected,
                        "penalty_pct": penalty,
                    }
                )
            penalties = [value[3] for value in values]
            low, high = bootstrap_median(penalties, rng)
            trend_rho, trend_p = exact_spearman_trend(penalties)
            nvhe_first = [value[3] for value in values if order[value[0]] == "nvhe"]
            protected_first = [value[3] for value in values if order[value[0]] == "protected"]
            summary_rows.append(
                {
                    "phase": phase,
                    "metric": metric,
                    "unit": unit,
                    "pairs": len(values),
                    "nvhe_boot_median": median([value[1] for value in values]),
                    "protected_boot_median": median([value[2] for value in values]),
                    "median_penalty_pct": median(penalties),
                    "mad_penalty_pct": mad(penalties),
                    "min_penalty_pct": min(penalties),
                    "max_penalty_pct": max(penalties),
                    "worse_pairs": sum(value > 1e-12 for value in penalties),
                    "better_pairs": sum(value < -1e-12 for value in penalties),
                    "exact_sign_p_two_sided": exact_two_sided_sign_p(penalties),
                    "bootstrap95_low_pct": low,
                    "bootstrap95_high_pct": high,
                    "bootstrap_interval_is_descriptive": True,
                    "nvhe_first_median_penalty_pct": median(nvhe_first),
                    "protected_first_median_penalty_pct": median(protected_first),
                    "order_group_gap_pct": median(nvhe_first) - median(protected_first),
                    "pair_index_spearman_rho": trend_rho,
                    "pair_index_permutation_p_two_sided": trend_p,
                }
            )

        for mode in ("nvhe", "protected"):
            drifts = []
            for pair in data.pairs:
                start = data.values[(pair, mode, "start", metric)]
                end = data.values[(pair, mode, "end", metric)]
                drift = (end / start - 1.0) * 100.0
                drifts.append(drift)
            drift_rows.append(
                {
                    "metric": metric,
                    "unit": unit,
                    "mode": mode,
                    "pairs": len(drifts),
                    "median_end_vs_start_pct": median(drifts),
                    "mad_pct": mad(drifts),
                    "min_pct": min(drifts),
                    "max_pct": max(drifts),
                }
            )

    write_csv(out / "anchor-summary.csv", summary_rows, list(summary_rows[0]))
    write_csv(out / "anchor-pair-values.csv", pair_rows, list(pair_rows[0]))
    write_csv(out / "anchor-drift-summary.csv", drift_rows, list(drift_rows[0]))
    return summary_rows, pair_rows


def audit_quality(campaign: Path) -> dict:
    boot_roots = [campaign / f"pair-{pair}" / mode for pair in range(1, 6) for mode in ("nvhe", "protected")]
    scenario_counts = {}
    for root in boot_roots:
        key = f"{root.parent.name}/{root.name}"
        scenario_counts[key] = {
            "boot_valid": (root / "BOOT_BLOCK_VALID").exists(),
            "anchor_start_valid": (root / "anchors-start/rep-00/VALID").exists(),
            "anchor_end_valid": (root / "anchors-end/rep-00/VALID").exists(),
            "redis_valid": len(list(root.glob("redis-*/rep-*/VALID"))),
            "rabbitmq_valid": len(list(root.glob("rabbitmq-*/rep-*/VALID"))),
            "geekbench_formal_valid": len(list(root.glob("geekbench-cpu/rep-00/rep-*/VALID"))),
        }

    rate_rows = []
    for path in campaign.glob("pair-[1-5]/*/rabbitmq-q3-rate*/rep-*/rate-validation.env"):
        env = read_env(path)
        scenario = path.parents[1].name.removeprefix("rabbitmq-")
        target = float(env["target_msg_s"])
        observed = float(env["observed_mean_published_msg_s"])
        rate_rows.append(
            {
                "scenario": scenario,
                "samples": int(env["samples"]),
                "target": target,
                "observed": observed,
                "error_pct": abs(observed / target - 1.0) * 100.0,
            }
        )

    q5_mismatches = []
    q5_envs = list(campaign.glob("pair-[1-5]/*/rabbitmq-q5-backlog/rep-*/after-*/validation.env"))
    for path in q5_envs:
        env = read_env(path)
        for actual, expected in (("messages_ready", "expected_ready"), ("messages_unacknowledged", "expected_unacknowledged")):
            if env.get(actual) != env.get(expected):
                q5_mismatches.append(f"{path}:{actual}={env.get(actual)} expected={env.get(expected)}")

    parsing_failed = []
    for path in campaign.rglob("stderr.txt"):
        if "Parsing failed" in path.read_text(encoding="utf-8", errors="replace"):
            parsing_failed.append(str(path))

    metadata = [read_env(path) for path in campaign.glob("pair-[1-5]/*/*/rep-00/metadata/metadata.env")]
    leg_metadata = [read_env(path) for path in campaign.glob("pair-[1-5]/*/leg-metadata/metadata.env")]
    protected_dmesg = list(campaign.glob("pair-[1-5]/protected/leg-metadata/dmesg.txt"))
    nvhe_dmesg = list(campaign.glob("pair-[1-5]/nvhe/leg-metadata/dmesg.txt"))
    urls = []
    for path in campaign.glob("pair-[1-5]/*/geekbench-cpu/rep-00/rep-*/result-urls.txt"):
        urls.extend(
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if "/v6/cpu/" in line and "/claim" not in line
        )

    capacity_path = campaign / "capacity.json"
    return {
        "campaign": campaign.name,
        "campaign_complete": (campaign / "CAMPAIGN_COMPLETE").exists(),
        "boot_block_valid_count": sum((root / "BOOT_BLOCK_VALID").exists() for root in boot_roots),
        "scenario_counts": scenario_counts,
        "q3_rate_gate": {
            "validation_files": len(rate_rows),
            "minimum_samples": min((row["samples"] for row in rate_rows), default=0),
            "maximum_samples": max((row["samples"] for row in rate_rows), default=0),
            "maximum_absolute_error_pct": max((row["error_pct"] for row in rate_rows), default=math.nan),
            "targets_by_scenario": {
                scenario: sorted({row["target"] for row in rate_rows if row["scenario"] == scenario})
                for scenario in sorted({row["scenario"] for row in rate_rows})
            },
        },
        "q5_queue_gate": {
            "validation_files": len(q5_envs),
            "queue_count_valid_markers": len(list(campaign.glob("pair-[1-5]/*/rabbitmq-q5-backlog/rep-*/after-*/QUEUE_COUNTS_VALID"))),
            "mismatches": q5_mismatches,
        },
        "parsing_failed_files": parsing_failed,
        "project_metadata": {
            "files": len(metadata),
            "thp_profiles": sorted({item.get("thp_profile", "") for item in metadata}),
            "effective_thp_states": sorted({item.get("thp", "") for item in metadata}),
        },
        "leg_metadata": {
            "files": len(leg_metadata),
            "kernels": sorted({item.get("kernel", "") for item in leg_metadata}),
            "aslr": sorted({item.get("aslr", "") for item in leg_metadata}),
            "swap_values": sorted({item.get("swap", "") for item in leg_metadata}),
            "protected_dmesg_with_feature": sum("Protected KVM" in path.read_text(errors="replace") for path in protected_dmesg),
            "nvhe_dmesg_with_hyp_init": sum("Hyp mode initialized successfully" in path.read_text(errors="replace") for path in nvhe_dmesg),
            "nvhe_dmesg_with_protected_feature": sum("Protected KVM" in path.read_text(errors="replace") for path in nvhe_dmesg),
        },
        "geekbench": {
            "formal_result_urls": len(urls),
            "unique_result_urls": len(set(urls)),
            "scores_json_files": len(list(campaign.glob("pair-[1-5]/*/geekbench-cpu/rep-00/rep-*/scores.json"))),
        },
        "capacity": json.loads(capacity_path.read_text()) if capacity_path.exists() else None,
        "first_mode_by_pair": pair_order(campaign),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep audit of a completed D3000 application campaign")
    parser.add_argument("campaign", type=Path)
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    campaign = args.campaign.resolve()
    metrics = args.metrics.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]

    app_summary, app_pairs = summarize_applications(metrics, campaign, out)
    anchor_summary, anchor_pairs = summarize_anchors(campaign, out, repo_root)
    quality = audit_quality(campaign)
    (out / "quality-summary.json").write_text(json.dumps(quality, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"application_metrics={len(app_summary)} application_pair_rows={len(app_pairs)} "
        f"anchor_metrics={len(anchor_summary)} anchor_pair_rows={len(anchor_pairs)} out={out}"
    )


if __name__ == "__main__":
    main()
