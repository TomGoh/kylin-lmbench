#!/usr/bin/env python3
"""Render D3000 boot-paired application figures from analyze-results.py metrics.csv.

The statistical unit is a boot pair.  Repetitions are reduced to one median per
boot before a protected-vs-nVHE penalty is calculated.  The script deliberately
does not draw the five in-boot repetitions as five independent pKVM samples.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, NamedTuple, Sequence, Tuple, Union


TEXT = "#1F2933"
MUTED = "#64707D"
GRID = "#E8EDF3"
AXIS = "#5C6670"
NVHE = "#4D7C59"
PROTECTED = "#C23B2A"
POSITIVE = "#C23B2A"
NEGATIVE = "#4D7C59"
DOT = "#243B53"
MISSING = "#F1F4F7"

MetricKey = Tuple[str, str, str]
BootKey = Tuple[int, str, str, str, str]


class MetricDef(NamedTuple):
    key: MetricKey
    label: str
    group: str


class MetricsData(NamedTuple):
    boot_medians: Dict[BootKey, float]
    penalties_pct: Dict[MetricKey, Dict[int, float]]
    metadata: Dict[MetricKey, Tuple[str, bool]]
    pairs: List[int]


REDIS_METRICS = [
    MetricDef(("redis", "r1-steady", "latency_avg"), "R1 avg latency", "Redis"),
    MetricDef(("redis", "r2-pipeline", "throughput"), "R2 throughput", "Redis"),
    MetricDef(("redis", "r2-pipeline", "latency_p99"), "R2 p99 latency", "Redis"),
    MetricDef(("redis", "r3-ttl-eviction", "latency_avg"), "R3 avg latency", "Redis"),
    MetricDef(("redis", "r4-bgsave", "latency_avg"), "R4 avg latency", "Redis"),
]

RABBIT_METRICS = [
    MetricDef(("rabbitmq", "q1-one-fast", "published"), "Q1 throughput", "RabbitMQ"),
    MetricDef(("rabbitmq", "q2-reliable", "published"), "Q2 throughput", "RabbitMQ"),
    MetricDef(("rabbitmq", "q3-rate50", "consumer_p99"), "Q3 50% consumer p99", "RabbitMQ"),
    MetricDef(("rabbitmq", "q3-rate70", "consumer_p99"), "Q3 70% consumer p99", "RabbitMQ"),
    MetricDef(("rabbitmq", "q3-rate85", "consumer_p99"), "Q3 85% consumer p99", "RabbitMQ"),
    MetricDef(("rabbitmq", "q3-rate85", "confirm_p99"), "Q3 85% confirm p99", "RabbitMQ"),
    MetricDef(("rabbitmq", "q4-join-late", "consumer_p99"), "Q4 consumer p99", "RabbitMQ"),
    MetricDef(("rabbitmq", "q5-backlog", "fill_time"), "Q5 fill time", "RabbitMQ"),
    MetricDef(("rabbitmq", "q5-backlog", "drain_time"), "Q5 drain time", "RabbitMQ"),
]

GEEKBENCH_METRICS = [
    MetricDef(("geekbench", "cpu", "wall_time"), "Geekbench suite wall time", "Geekbench"),
    MetricDef(("geekbench", "cpu", "single_core_score"), "Geekbench single-core", "Geekbench"),
    MetricDef(("geekbench", "cpu", "multi_core_score"), "Geekbench multi-core", "Geekbench"),
]

MATRIX_METRICS = REDIS_METRICS + RABBIT_METRICS + GEEKBENCH_METRICS
Q3_LOADS = [50, 70, 85]


class Svg:
    def __init__(self, width: int, height: int, title: str, desc: str) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.desc = desc
        self.parts: List[str] = []

    def add(self, markup: str) -> None:
        self.parts.append(markup)

    def text(
        self,
        x: float,
        y: float,
        value: str,
        *,
        size: int = 13,
        fill: str = TEXT,
        anchor: str = "start",
        weight: Union[int, str] = 400,
    ) -> None:
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>'
        )

    def render(self) -> str:
        body = "\n  ".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}" '
            f'role="img" aria-labelledby="title desc">\n'
            f'  <title id="title">{escape(self.title)}</title>\n'
            f'  <desc id="desc">{escape(self.desc)}</desc>\n'
            f'  <rect width="100%" height="100%" fill="#FFFFFF"/>\n'
            f'  {body}\n'
            f'</svg>\n'
        )


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def load_metrics(path: Path) -> MetricsData:
    """Load analyzer rows and reduce repetitions to boot-paired penalties."""

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no metric rows")
    return aggregate_rows(rows)


def aggregate_rows(rows: Iterable[Mapping[str, str]]) -> MetricsData:
    by_boot: Dict[BootKey, List[float]] = defaultdict(list)
    metadata: Dict[MetricKey, Tuple[str, bool]] = {}

    for row in rows:
        pair = int(row["pair"])
        mode = row["mode"]
        if mode not in {"nvhe", "protected"}:
            raise ValueError(f"unexpected mode {mode!r}")
        key = (row["project"], row["scenario"], row["metric"])
        meta = (row["unit"], _parse_bool(row["higher_better"]))
        previous = metadata.get(key)
        if previous is not None and previous != meta:
            raise ValueError(f"inconsistent metadata for {key}: {previous} vs {meta}")
        metadata[key] = meta
        by_boot[(pair, mode, *key)].append(float(row["value"]))

    boot_medians = {key: statistics.median(values) for key, values in by_boot.items()}
    pair_values: Dict[Tuple[int, MetricKey], Dict[str, float]] = defaultdict(dict)
    for (pair, mode, project, scenario, metric), value in boot_medians.items():
        pair_values[(pair, (project, scenario, metric))][mode] = value

    penalties: Dict[MetricKey, Dict[int, float]] = defaultdict(dict)
    complete_pairs = set()
    for (pair, key), modes in pair_values.items():
        if set(modes) != {"nvhe", "protected"} or modes["nvhe"] == 0:
            continue
        raw_delta = (modes["protected"] / modes["nvhe"] - 1.0) * 100.0
        higher_better = metadata[key][1]
        penalties[key][pair] = -raw_delta if higher_better else raw_delta
        complete_pairs.add(pair)

    return MetricsData(
        boot_medians=boot_medians,
        penalties_pct=dict(penalties),
        metadata=metadata,
        pairs=sorted(complete_pairs),
    )


def _nice_step(max_value: float, target_ticks: int = 5) -> float:
    if max_value <= 0:
        return 1.0
    raw = max_value / target_ticks
    exponent = math.floor(math.log10(raw))
    fraction = raw / (10**exponent)
    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    return nice_fraction * (10**exponent)


def _axis_max(max_value: float, target_ticks: int = 5) -> float:
    step = _nice_step(max_value, target_ticks)
    return max(step, math.ceil(max_value / step) * step)


def _x_for_signed(value: float, extent: float, left: float, width: float) -> float:
    return left + ((value + extent) / (2 * extent)) * width


def _available(data: MetricsData, definitions: Sequence[MetricDef]) -> List[MetricDef]:
    return [definition for definition in definitions if data.penalties_pct.get(definition.key)]


def _draw_penalty_axis(
    svg: Svg,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    extent: float,
) -> None:
    for value in (-extent, -extent / 2, 0.0, extent / 2, extent):
        x = _x_for_signed(value, extent, left, width)
        color = AXIS if value == 0 else GRID
        stroke = 1.5 if value == 0 else 1.0
        svg.add(
            f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{top + height:.1f}" '
            f'stroke="{color}" stroke-width="{stroke}"/>'
        )
        svg.text(x, top + height + 22, f"{value:+.0f}%", size=11, fill=MUTED, anchor="middle")


def _draw_penalty_panel(
    svg: Svg,
    data: MetricsData,
    definitions: Sequence[MetricDef],
    *,
    x: float,
    y: float,
    width: float,
    title: str,
) -> float:
    rows = _available(data, definitions)
    if not rows:
        return y
    row_gap = 48.0
    label_width = 182.0
    plot_left = x + label_width
    plot_width = width - label_width - 22
    plot_top = y + 50
    plot_height = max(1.0, len(rows) * row_gap - 10)
    all_values = [value for row in rows for value in data.penalties_pct[row.key].values()]
    extent = _axis_max(max(abs(value) for value in all_values) * 1.08, 4)

    svg.text(x, y, title, size=17, weight=700)
    svg.text(x, y + 21, "bar = median paired penalty; dots = boot pairs", size=11, fill=MUTED)
    _draw_penalty_axis(svg, left=plot_left, top=plot_top - 16, width=plot_width, height=plot_height + 18, extent=extent)
    zero_x = _x_for_signed(0.0, extent, plot_left, plot_width)

    for index, definition in enumerate(rows):
        center_y = plot_top + index * row_gap + 9
        pair_values = data.penalties_pct[definition.key]
        median = statistics.median(pair_values.values())
        value_x = _x_for_signed(median, extent, plot_left, plot_width)
        bar_x = min(zero_x, value_x)
        bar_width = max(1.2, abs(value_x - zero_x))
        color = POSITIVE if median >= 0 else NEGATIVE
        svg.text(x, center_y + 4, definition.label, size=11, fill=TEXT)
        svg.add(
            f'<rect x="{bar_x:.1f}" y="{center_y - 8:.1f}" width="{bar_width:.1f}" '
            f'height="16" rx="3" fill="{color}" opacity="0.55"/>'
        )

        ordered = sorted(pair_values.items())
        for dot_index, (pair, value) in enumerate(ordered):
            dot_x = _x_for_signed(value, extent, plot_left, plot_width)
            jitter = ((dot_index % 3) - 1) * 3.0 if len(ordered) > 1 else 0.0
            svg.add(
                f'<circle cx="{dot_x:.1f}" cy="{center_y + jitter:.1f}" r="3.2" '
                f'fill="{DOT}" stroke="#FFFFFF" stroke-width="0.8">'
                f'<title>Pair {pair}: {value:+.2f}%</title></circle>'
            )

        label_anchor = "start" if median >= 0 else "end"
        label_x = value_x + 7 if median >= 0 else value_x - 7
        svg.text(label_x, center_y + 4, f"{median:+.2f}%", size=10, fill=color, anchor=label_anchor, weight=700)

    return plot_top + plot_height + 46


def write_application_overview(
    data: MetricsData,
    out_path: Path,
    *,
    source_label: str,
) -> None:
    redis_rows = _available(data, REDIS_METRICS)
    rabbit_rows = _available(data, RABBIT_METRICS + GEEKBENCH_METRICS)
    if not redis_rows and not rabbit_rows:
        raise ValueError("no selected D3000 application metrics are available")

    width = 1240
    max_rows = max(len(redis_rows), len(rabbit_rows), 1)
    height = int(190 + max_rows * 48 + 95)
    svg = Svg(
        width,
        height,
        "D3000 pKVM application penalty overview",
        "Boot-paired pKVM penalty. Positive values mean pKVM is worse. Bars are medians across boot pairs and dots are individual boot pairs.",
    )
    shown_rows = redis_rows + rabbit_rows
    pair_counts = [len(data.penalties_pct[row.key]) for row in shown_rows]
    min_pairs, max_pairs = min(pair_counts), max(pair_counts)
    if min_pairs == max_pairs:
        status = f"n={max_pairs} paired boot{'s' if max_pairs != 1 else ''} per shown metric"
    else:
        status = f"n={min_pairs}-{max_pairs} paired boots depending on metric; see matrix for missing cells"
    if max_pairs < 5:
        status += "; preliminary until all 5 pairs complete"
    svg.text(width / 2, 34, "D3000 pKVM application penalty overview", size=22, weight=700, anchor="middle")
    svg.text(width / 2, 58, "positive = pKVM worse; repetitions are reduced inside each boot before pairing", size=13, fill=MUTED, anchor="middle")
    svg.text(width / 2, 80, status, size=12, fill=MUTED, anchor="middle")

    _draw_penalty_panel(svg, data, REDIS_METRICS, x=42, y=112, width=560, title="Redis")
    _draw_penalty_panel(svg, data, RABBIT_METRICS + GEEKBENCH_METRICS, x=638, y=112, width=560, title="RabbitMQ / Geekbench")

    legend_y = height - 47
    for index, (label, color) in enumerate((("pKVM penalty", POSITIVE), ("pKVM improvement", NEGATIVE))):
        x = 395 + index * 210
        svg.add(f'<rect x="{x:.1f}" y="{legend_y - 11:.1f}" width="18" height="12" rx="2" fill="{color}" opacity="0.7"/>')
        svg.text(x + 26, legend_y, label, size=11, fill=MUTED)
    svg.text(width / 2, height - 17, f"Source: {source_label}", size=11, fill=MUTED, anchor="middle")
    out_path.write_text(svg.render(), encoding="utf-8")


def _q3_key(load: int, metric: str) -> MetricKey:
    return ("rabbitmq", f"q3-rate{load}", metric)


def _common_q3_pairs(data: MetricsData, metric: str) -> List[int]:
    common = None
    for load in Q3_LOADS:
        key = _q3_key(load, metric)
        present = {
            pair
            for pair in data.pairs
            if (pair, "nvhe", *key) in data.boot_medians
            and (pair, "protected", *key) in data.boot_medians
        }
        common = present if common is None else common.intersection(present)
    return sorted(common or set())


def _metric_to_display(value: float, unit: str) -> Tuple[float, str]:
    if unit == "us":
        return value / 1000.0, "ms"
    return value, unit


def _polyline(points: Sequence[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _draw_load_panel(
    svg: Svg,
    data: MetricsData,
    metric: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    title: str,
) -> None:
    pairs = _common_q3_pairs(data, metric)
    if not pairs:
        raise ValueError(f"no complete Q3 boot pairs for {metric}")

    sample_key = _q3_key(Q3_LOADS[0], metric)
    unit = data.metadata[sample_key][0]
    display_unit = _metric_to_display(1.0, unit)[1]
    values = []
    for pair in pairs:
        for mode in ("nvhe", "protected"):
            for load in Q3_LOADS:
                raw = data.boot_medians[(pair, mode, *_q3_key(load, metric))]
                values.append(_metric_to_display(raw, unit)[0])
    y_max = _axis_max(max(values) * 1.10, 5)
    bottom = top + height
    x_positions = {load: left + index * width / (len(Q3_LOADS) - 1) for index, load in enumerate(Q3_LOADS)}

    svg.text(left, top - 38, title, size=17, weight=700)
    svg.text(left, top - 16, f"absolute {display_unit}; faint lines are individual pairs", size=11, fill=MUTED)
    for index in range(6):
        value = y_max * index / 5
        y = bottom - value / y_max * height
        svg.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + width:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        svg.text(left - 10, y + 4, f"{value:.1f}", size=11, fill=MUTED, anchor="end")
    svg.add(f'<line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{bottom:.1f}" stroke="{AXIS}"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{bottom:.1f}" x2="{left + width:.1f}" y2="{bottom:.1f}" stroke="{AXIS}"/>')

    for load in Q3_LOADS:
        x = x_positions[load]
        svg.text(x, bottom + 24, f"{load}%", size=12, fill=TEXT, anchor="middle")

    for mode, color in (("nvhe", NVHE), ("protected", PROTECTED)):
        for pair in pairs:
            pair_points = []
            for load in Q3_LOADS:
                raw = data.boot_medians[(pair, mode, *_q3_key(load, metric))]
                value = _metric_to_display(raw, unit)[0]
                pair_points.append((x_positions[load], bottom - value / y_max * height))
            svg.add(
                f'<polyline points="{_polyline(pair_points)}" fill="none" stroke="{color}" '
                f'stroke-width="1.2" opacity="0.22"/>'
            )
            for x, y in pair_points:
                svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="{color}" opacity="0.28"/>')

        aggregate_points = []
        for load in Q3_LOADS:
            aggregate = statistics.median(
                _metric_to_display(data.boot_medians[(pair, mode, *_q3_key(load, metric))], unit)[0]
                for pair in pairs
            )
            aggregate_points.append((x_positions[load], bottom - aggregate / y_max * height))
        svg.add(
            f'<polyline points="{_polyline(aggregate_points)}" fill="none" stroke="{color}" '
            f'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in aggregate_points:
            svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#FFFFFF" stroke="{color}" stroke-width="2"/>')

    penalty_values = data.penalties_pct[_q3_key(85, metric)]
    penalty = statistics.median(penalty_values[pair] for pair in pairs)
    annotation_x = x_positions[85] - 8
    svg.add(
        f'<rect x="{annotation_x - 112:.1f}" y="{top + 12:.1f}" width="112" height="29" rx="4" '
        f'fill="#FFFFFF" stroke="#D9DEE7"/>'
    )
    svg.text(annotation_x - 56, top + 32, f"85%: {penalty:+.1f}%", size=12, fill=POSITIVE if penalty >= 0 else NEGATIVE, anchor="middle", weight=700)
    svg.text(left + width / 2, bottom + 51, "offered load (% of common capacity)", size=12, fill=MUTED, anchor="middle")


def write_rabbitmq_load_curve(
    data: MetricsData,
    out_path: Path,
    *,
    source_label: str,
) -> None:
    width, height = 1240, 610
    svg = Svg(
        width,
        height,
        "D3000 RabbitMQ fixed-load tail latency",
        "RabbitMQ Q3 consumer and publisher-confirm p99 latency at 50, 70, and 85 percent of common capacity for nVHE and pKVM.",
    )
    pair_count = len(_common_q3_pairs(data, "consumer_p99"))
    svg.text(width / 2, 35, "D3000 RabbitMQ: tail latency versus fixed offered load", size=22, weight=700, anchor="middle")
    svg.text(width / 2, 59, f"boot medians; aggregate line is the median across {pair_count} complete pair{'s' if pair_count != 1 else ''}", size=13, fill=MUTED, anchor="middle")

    _draw_load_panel(svg, data, "consumer_p99", left=86, top=130, width=470, height=330, title="Consumer p99")
    _draw_load_panel(svg, data, "confirm_p99", left=684, top=130, width=470, height=330, title="Publisher confirm p99")

    legend_y = 93
    for index, (label, color) in enumerate((("nVHE", NVHE), ("pKVM", PROTECTED))):
        x = 482 + index * 118
        svg.add(f'<line x1="{x:.1f}" y1="{legend_y:.1f}" x2="{x + 28:.1f}" y2="{legend_y:.1f}" stroke="{color}" stroke-width="3"/>')
        svg.add(f'<circle cx="{x + 14:.1f}" cy="{legend_y:.1f}" r="4" fill="#FFFFFF" stroke="{color}" stroke-width="2"/>')
        svg.text(x + 37, legend_y + 4, label, size=12)
    svg.text(width / 2, height - 19, f"Source: {source_label}; Q3 rate gates must be valid", size=11, fill=MUTED, anchor="middle")
    out_path.write_text(svg.render(), encoding="utf-8")


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _blend(start: str, end: str, fraction: float) -> str:
    fraction = max(0.0, min(1.0, fraction))
    a = _hex_to_rgb(start)
    b = _hex_to_rgb(end)
    rgb = tuple(round(x + (y - x) * fraction) for x, y in zip(a, b))
    return "#" + "".join(f"{value:02X}" for value in rgb)


def _penalty_color(value: float, extent: float) -> str:
    fraction = min(1.0, abs(value) / extent) if extent else 0.0
    if value >= 0:
        return _blend("#FFF7F5", POSITIVE, fraction)
    return _blend("#F5FAF6", NEGATIVE, fraction)


def write_pair_matrix(
    data: MetricsData,
    out_path: Path,
    *,
    source_label: str,
    expected_pairs: int = 5,
) -> None:
    rows = _available(data, MATRIX_METRICS)
    if not rows:
        raise ValueError("no selected metrics for pair matrix")
    width = 1180
    row_height = 42
    header_y = 130
    height = int(header_y + len(rows) * row_height + 118)
    label_left = 42
    grid_left = 332
    cell_width = 120
    columns: List[Union[int, str]] = list(range(1, expected_pairs + 1)) + ["median"]
    all_values = [value for definition in rows for value in data.penalties_pct[definition.key].values()]
    extent = _axis_max(max(abs(value) for value in all_values) * 1.02, 4)

    svg = Svg(
        width,
        height,
        "D3000 pKVM boot-pair penalty matrix",
        "Pair-by-pair pKVM penalty matrix. Positive red cells mean pKVM is worse; negative green cells mean pKVM is better.",
    )
    svg.text(width / 2, 34, "D3000 pKVM boot-pair penalty matrix", size=22, weight=700, anchor="middle")
    svg.text(width / 2, 58, "positive/red = pKVM worse; each cell uses one boot median per mode", size=13, fill=MUTED, anchor="middle")
    svg.text(width / 2, 80, "blank cells are incomplete pairs, not zeroes", size=11, fill=MUTED, anchor="middle")

    for index, column in enumerate(columns):
        center = grid_left + index * cell_width + cell_width / 2
        label = f"Pair {column}" if isinstance(column, int) else "Median"
        svg.text(center, header_y - 16, label, size=12, fill=TEXT, anchor="middle", weight=700 if column == "median" else 400)

    for row_index, definition in enumerate(rows):
        y = header_y + row_index * row_height
        svg.text(label_left, y + 26, definition.label, size=11, fill=TEXT)
        values = data.penalties_pct[definition.key]
        median = statistics.median(values.values())
        for column_index, column in enumerate(columns):
            x = grid_left + column_index * cell_width
            value = values.get(column) if isinstance(column, int) else median
            if value is None:
                fill = MISSING
                label = "—"
                text_fill = MUTED
            else:
                fill = _penalty_color(value, extent)
                label = f"{value:+.1f}%"
                text_fill = "#FFFFFF" if abs(value) / extent > 0.62 else TEXT
            stroke = "#9AA5B1" if column == "median" else "#FFFFFF"
            stroke_width = 1.5 if column == "median" else 1.0
            svg.add(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_width:.1f}" height="{row_height:.1f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
            )
            svg.text(x + cell_width / 2, y + 26, label, size=11, fill=text_fill, anchor="middle", weight=700 if column == "median" else 400)

    legend_y = header_y + len(rows) * row_height + 40
    legend_values = [-extent, -extent / 2, 0.0, extent / 2, extent]
    legend_cell = 76
    legend_left = width / 2 - len(legend_values) * legend_cell / 2
    for index, value in enumerate(legend_values):
        x = legend_left + index * legend_cell
        svg.add(f'<rect x="{x:.1f}" y="{legend_y:.1f}" width="{legend_cell:.1f}" height="18" fill="{_penalty_color(value, extent)}"/>')
        svg.text(x + legend_cell / 2, legend_y + 36, f"{value:+.0f}%", size=10, fill=MUTED, anchor="middle")
    svg.text(width / 2, height - 17, f"Source: {source_label}", size=11, fill=MUTED, anchor="middle")
    out_path.write_text(svg.render(), encoding="utf-8")


def _safe_prefix(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_" else "-" for character in value)
    return cleaned.strip("-") or "d3000"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render D3000 application SVGs from analyzer metrics.csv")
    parser.add_argument("metrics", type=Path, help="metrics.csv produced by analyze-results.py")
    parser.add_argument("--figure-dir", type=Path, default=Path("docs/mmap/figures"))
    parser.add_argument("--prefix", help="output filename prefix; default is the metrics parent directory name")
    parser.add_argument("--expected-pairs", type=int, default=5)
    args = parser.parse_args()

    source_label = args.metrics.as_posix()
    metrics = args.metrics.resolve()
    data = load_metrics(metrics)
    figure_dir = args.figure_dir.resolve()
    figure_dir.mkdir(parents=True, exist_ok=True)
    prefix = _safe_prefix(args.prefix or metrics.parent.name)
    outputs = [
        figure_dir / f"{prefix}-application-overview.svg",
        figure_dir / f"{prefix}-rabbitmq-load-curve.svg",
        figure_dir / f"{prefix}-pair-penalty-matrix.svg",
    ]
    write_application_overview(data, outputs[0], source_label=source_label)
    write_rabbitmq_load_curve(data, outputs[1], source_label=source_label)
    write_pair_matrix(data, outputs[2], source_label=source_label, expected_pairs=args.expected_pairs)
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
