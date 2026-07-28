#!/usr/bin/env python3
import csv
import json
import statistics
import sys
from pathlib import Path


def redis_ops(path: Path) -> float:
    obj = json.loads(path.read_text())
    for all_key in ("ALL STATS", "All Stats", "all stats"):
        if all_key not in obj:
            continue
        totals = obj[all_key].get("Totals", obj[all_key].get("totals", {}))
        for key in ("Ops/sec", "Ops/Sec", "ops/sec"):
            if key in totals:
                return float(totals[key])
    raise ValueError(f"cannot find total Ops/sec in {path}")


def rabbit_ops(path: Path) -> float:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"no CSV rows in {path}")
    fields = list(rows[0])
    sent = next(
        (
            x
            for x in fields
            if ("sent" in x.lower() or "published" in x.lower())
            and ("msg" in x.lower() or "rate" in x.lower())
        ),
        None,
    )
    received = next((x for x in fields if "received" in x.lower() and ("msg" in x.lower() or "rate" in x.lower())), None)
    time_field = next((x for x in fields if "time" in x.lower()), None)
    if not sent or not received:
        raise ValueError(f"cannot identify sent/received fields in {path}: {fields}")
    numeric_times = []
    if time_field:
        for row in rows:
            try:
                numeric_times.append(float(row[time_field]))
            except (ValueError, TypeError):
                pass
    discard_before = 60 if numeric_times and max(numeric_times) >= 120 else 0
    vals = []
    for row in rows:
        try:
            if time_field and float(row[time_field]) < discard_before:
                continue
            vals.append(min(float(row[sent]), float(row[received])))
        except (ValueError, TypeError):
            continue
    if not vals:
        raise ValueError(f"no numeric steady rows in {path}")
    return statistics.median(vals)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: compute-capacity.py RESULTS_CAMPAIGN STATE_DIR OUT_JSON", file=sys.stderr)
        return 2
    root, state, out = map(Path, sys.argv[1:])
    summary = {"redis": {}, "rabbitmq": {}}
    for mode in ("nvhe", "protected"):
        rfiles = sorted((root / "pair-calibration" / mode / "redis-calibration").glob("rep-*/memtier.json"))
        qfiles = sorted((root / "pair-calibration" / mode / "rabbitmq-calibration").glob("rep-*/perftest.csv"))
        if len(rfiles) != 5 or len(qfiles) != 5:
            raise RuntimeError(f"expected five calibration files for {mode}; redis={len(rfiles)} rabbit={len(qfiles)}")
        rvals = [redis_ops(x) for x in rfiles]
        qvals = [rabbit_ops(x) for x in qfiles]
        summary["redis"][mode] = {"runs": rvals, "median": statistics.median(rvals)}
        summary["rabbitmq"][mode] = {"runs": qvals, "median": statistics.median(qvals)}
    summary["redis"]["common"] = min(summary["redis"][m]["median"] for m in ("nvhe", "protected"))
    summary["rabbitmq"]["common"] = min(summary["rabbitmq"][m]["median"] for m in ("nvhe", "protected"))
    state.mkdir(parents=True, exist_ok=True)
    (state / "redis-rate-common").write_text(f"{int(summary['redis']['common'])}\n")
    (state / "redis-rate-70").write_text(f"{int(summary['redis']['common'] * 0.70)}\n")
    (state / "rabbit-rate-common").write_text(f"{int(summary['rabbitmq']['common'])}\n")
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
