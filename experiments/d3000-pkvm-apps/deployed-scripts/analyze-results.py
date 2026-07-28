#!/usr/bin/env python3
"""Analyze D3000 application campaign results using boot-paired statistics."""

import argparse
import csv
import json
import math
import random
import re
import statistics
from collections import defaultdict
from pathlib import Path


def median(values):
    return statistics.median(values) if values else math.nan


def percentile(values, p):
    values = sorted(values)
    if not values:
        return math.nan
    x = (len(values) - 1) * p
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return values[lo]
    return values[lo] * (hi - x) + values[hi] * (x - lo)


def elapsed_seconds(text):
    match = re.search(r"Elapsed \(wall clock\) time .*?:\s*([0-9:.]+)", text)
    if not match:
        return math.nan
    parts = [float(x) for x in match.group(1).split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def add(rows, pair, mode, project, scenario, rep, metric, value, unit, higher):
    if value is None or not math.isfinite(float(value)):
        return
    rows.append(
        {
            "pair": str(pair),
            "mode": mode,
            "project": project,
            "scenario": scenario,
            "rep": int(rep),
            "metric": metric,
            "value": float(value),
            "unit": unit,
            "higher_better": bool(higher),
        }
    )


def parse_redis(rows, pair, mode, scenario, rep, path):
    obj = json.loads(path.read_text())
    totals = obj["ALL STATS"]["Totals"]
    pct = totals.get("Percentile Latencies", {})
    add(rows, pair, mode, "redis", scenario, rep, "throughput", totals["Ops/sec"], "ops/s", True)
    add(rows, pair, mode, "redis", scenario, rep, "latency_avg", totals.get("Average Latency", totals.get("Latency")), "ms", False)
    for source, name in (("p50.00", "latency_p50"), ("p95.00", "latency_p95"), ("p99.00", "latency_p99")):
        add(rows, pair, mode, "redis", scenario, rep, name, pct.get(source), "ms", False)


def numeric(row, field):
    try:
        return float(row[field])
    except (KeyError, TypeError, ValueError):
        return math.nan


def parse_rabbit_csv(rows_out, pair, mode, scenario, rep, path):
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    times = [numeric(x, "time (s)") for x in rows]
    cutoff = 60 if max((x for x in times if math.isfinite(x)), default=0) >= 120 else 0
    rows = [x for x in rows if numeric(x, "time (s)") >= cutoff]
    fields = {
        "published": ("published (msg/s)", "msg/s", True),
        "received": ("received (msg/s)", "msg/s", True),
        "consumer_p95": ("95th p. consumer latency (µs)", "us", False),
        "consumer_p99": ("99th p. consumer latency (µs)", "us", False),
        "confirm_p95": ("95th p. confirm latency (µs)", "us", False),
        "confirm_p99": ("99th p. confirm latency (µs)", "us", False),
    }
    for metric, (field, unit, higher) in fields.items():
        vals = [numeric(x, field) for x in rows]
        vals = [x for x in vals if math.isfinite(x)]
        add(rows_out, pair, mode, "rabbitmq", scenario, rep, metric, median(vals), unit, higher)


def parse_geekbench(rows, pair, mode, rep, rep_dir):
    scores_file = rep_dir / "scores.json"
    if scores_file.exists():
        obj = json.loads(scores_file.read_text())
        for metric, value in obj.get("scores", {}).items():
            add(rows, pair, mode, "geekbench", "cpu", rep, metric, value, "score", True)
        return
    text = (rep_dir / "stdout.txt").read_text(errors="replace")
    for metric, pattern in (
        ("single_core_score", r"Single-Core Score\s*[: ]\s*([0-9]+)"),
        ("multi_core_score", r"Multi-Core Score\s*[: ]\s*([0-9]+)"),
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            add(rows, pair, mode, "geekbench", "cpu", rep, metric, float(match.group(1)), "score", True)


def perftest_phase_valid(phase_dir):
    csv_path = phase_dir / "perftest.csv"
    stderr_path = phase_dir / "stderr.txt"
    if not csv_path.is_file() or csv_path.stat().st_size == 0:
        return False
    if stderr_path.is_file() and "Parsing failed" in stderr_path.read_text(errors="replace"):
        return False
    return True


def collect(campaign):
    rows = []
    for pair_dir in sorted(campaign.glob("pair-[1-5]")):
        pair = pair_dir.name.removeprefix("pair-")
        for mode in ("nvhe", "protected"):
            root = pair_dir / mode
            if not root.is_dir():
                continue
            for scenario_dir in root.glob("redis-*"):
                scenario = scenario_dir.name.removeprefix("redis-")
                for rep_dir in sorted(scenario_dir.glob("rep-*")):
                    if not (rep_dir / "VALID").exists() or not (rep_dir / "memtier.json").exists():
                        continue
                    parse_redis(rows, pair, mode, scenario, int(rep_dir.name[-2:]), rep_dir / "memtier.json")
            for scenario_dir in root.glob("rabbitmq-*"):
                scenario = scenario_dir.name.removeprefix("rabbitmq-")
                for rep_dir in sorted(scenario_dir.glob("rep-*")):
                    if not (rep_dir / "VALID").exists():
                        continue
                    rep = int(rep_dir.name[-2:])
                    if scenario == "q5-backlog":
                        phase_dirs = {phase: rep_dir / phase for phase in ("fill", "drain")}
                        if all(perftest_phase_valid(phase_dir) for phase_dir in phase_dirs.values()):
                            for phase, phase_dir in phase_dirs.items():
                                time_file = phase_dir / "time.txt"
                                if time_file.exists():
                                    add(rows, pair, mode, "rabbitmq", scenario, rep, f"{phase}_time", elapsed_seconds(time_file.read_text()), "s", False)
                    elif (rep_dir / "perftest.csv").exists():
                        parse_rabbit_csv(rows, pair, mode, scenario, rep, rep_dir / "perftest.csv")
            geek = root / "geekbench-cpu"
            candidates = list(geek.glob("rep-*/rep-*")) + list(geek.glob("rep-*")) if geek.is_dir() else []
            seen = set()
            for rep_dir in sorted(candidates):
                if rep_dir in seen:
                    continue
                seen.add(rep_dir)
                if (rep_dir / "VALID").exists() and (rep_dir / "stdout.txt").exists():
                    parse_geekbench(rows, pair, mode, int(rep_dir.name[-2:]), rep_dir)
    return rows


def summarize(rows):
    by_boot = defaultdict(list)
    metadata = {}
    for row in rows:
        key = (row["pair"], row["mode"], row["project"], row["scenario"], row["metric"])
        by_boot[key].append(row["value"])
        metadata[(row["project"], row["scenario"], row["metric"])] = (row["unit"], row["higher_better"])
    boot_medians = {key: median(vals) for key, vals in by_boot.items()}
    deltas = defaultdict(list)
    pair_values = defaultdict(dict)
    for (pair, mode, project, scenario, metric), value in boot_medians.items():
        pair_values[(pair, project, scenario, metric)][mode] = value
    for (pair, project, scenario, metric), modes in pair_values.items():
        if set(modes) != {"nvhe", "protected"} or modes["nvhe"] == 0:
            continue
        delta = modes["protected"] / modes["nvhe"] - 1
        deltas[(project, scenario, metric)].append((int(pair), delta, modes["nvhe"], modes["protected"]))
    summary = []
    rng = random.Random(20260713)
    for key, values in sorted(deltas.items()):
        project, scenario, metric = key
        ordered = sorted(values)
        ds = [x[1] for x in ordered]
        med = median(ds)
        mad = median([abs(x - med) for x in ds])
        boots = []
        if ds:
            for _ in range(10000):
                boots.append(median([rng.choice(ds) for _ in ds]))
        unit, higher = metadata[key]
        threshold = 0.05 if "p99" in metric else 0.03
        summary.append(
            {
                "project": project,
                "scenario": scenario,
                "metric": metric,
                "unit": unit,
                "higher_better": higher,
                "pairs": len(ds),
                "median_delta": med,
                "mad": mad,
                "ci95_low": percentile(boots, 0.025),
                "ci95_high": percentile(boots, 0.975),
                "equivalence_threshold": threshold,
                "equivalent": len(ds) == 5 and percentile(boots, 0.025) >= -threshold and percentile(boots, 0.975) <= threshold,
                "same_direction_4of5": len(ds) == 5 and max(sum(x > 0 for x in ds), sum(x < 0 for x in ds)) >= 4,
                "pair_values": ordered,
            }
        )
    return summary


def write_outputs(out, rows, summary, campaign_name):
    out.mkdir(parents=True, exist_ok=True)
    with (out / "metrics.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["pair", "mode", "project", "scenario", "rep", "metric", "value", "unit", "higher_better"])
        writer.writeheader()
        writer.writerows(rows)
    flat_fields = ["project", "scenario", "metric", "unit", "higher_better", "pairs", "median_delta", "mad", "ci95_low", "ci95_high", "equivalence_threshold", "equivalent", "same_direction_4of5"]
    with (out / "paired-summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=flat_fields)
        writer.writeheader()
        for item in summary:
            writer.writerow({x: item[x] for x in flat_fields})
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    lines = [
        f"# D3000 nVHE / pKVM 真实负载结果：{campaign_name}",
        "",
        "下表的差值统一为 `protected / nVHE - 1`。吞吐/分数越高越好；延迟/时间越低越好。",
        "统计单位是 boot pair：先在每个 boot 内取 5 次中位数，再做同 pair 差值。",
        "",
        "| 项目 | 场景 | 指标 | pairs | 中位差值 | MAD | paired bootstrap 95% CI | 等价 | 4/5 同方向 |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for x in summary:
        ci = f"[{x['ci95_low'] * 100:+.2f}%, {x['ci95_high'] * 100:+.2f}%]"
        lines.append(
            f"| {x['project']} | {x['scenario']} | {x['metric']} | {x['pairs']} | "
            f"{x['median_delta'] * 100:+.2f}% | {x['mad'] * 100:.2f}% | {ci} | "
            f"{'是' if x['equivalent'] else '否/未完成'} | {'是' if x['same_direction_4of5'] else '否'} |"
        )
    lines += ["", "完整逐次指标见 `metrics.csv`，逐 pair 原值与 bootstrap 输入见 `summary.json`。", ""]
    (out / "REPORT.zh-CN.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = collect(args.campaign)
    summary = summarize(rows)
    out = args.out or args.campaign / "analysis"
    write_outputs(out, rows, summary, args.campaign.name)
    print(f"rows={len(rows)} summaries={len(summary)} out={out}")


if __name__ == "__main__":
    main()
