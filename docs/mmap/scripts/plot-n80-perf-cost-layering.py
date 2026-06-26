#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Render the N80 host-side perf cost layering result as SVG."""

from __future__ import annotations

import argparse
import math
import re
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Tuple, Union


MODE_FILES = {
    "NVHE": Path("results/n80-munmap-gate-c0/nvhe/c0-nvhe/perf-munmap_after_write_touch-64mb-nvhe.txt"),
    "protected": Path("results/n80-munmap-gate-c0/protected/c0-protected/perf-munmap_after_write_touch-64mb-protected.txt"),
}

EVENT_LABELS = {
    "cycles": "cycles",
    "instructions": "instructions",
    "stall_backend": "stall_backend",
    "page-faults": "page-faults",
    "l1d_tlb_refill": "l1d_tlb_refill",
    "l2d_tlb_refill": "l2d_tlb_refill",
    "r34": "dtlb_walk (r34)",
}

BIG_EVENTS = ["cycles", "instructions", "stall_backend"]
SMALL_EVENTS = ["page-faults", "l1d_tlb_refill", "l2d_tlb_refill", "r34"]

MODE_COLORS = {
    "NVHE": "#4D7C59",
    "protected": "#C23B2A",
}


class PerfMeasurements(NamedTuple):
    counts: Dict[str, Dict[str, int]]
    elapsed_s: Dict[str, float]
    ipc: Dict[str, float]
    sources: Dict[str, Path]


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
        fill: str = "#1F2933",
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
    return math.ceil(max_value / step) * step


def _format_count(value: int) -> str:
    return f"{value:,}"


def _format_delta(value: int) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(value):,}"


def _format_ratio(value: float) -> str:
    return f"{value:.2f}x"


def _read_perf(path: Path) -> Tuple[Dict[str, int], float]:
    counts: Dict[str, int] = {}
    elapsed_s = None
    count_re = re.compile(r"^\s*([0-9][0-9,]*)\s+([A-Za-z0-9_:-]+)\b")
    elapsed_re = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s+seconds time elapsed\b")

    for line in path.read_text(encoding="utf-8").splitlines():
        elapsed_match = elapsed_re.match(line)
        if elapsed_match:
            elapsed_s = float(elapsed_match.group(1))
            continue

        count_match = count_re.match(line)
        if not count_match:
            continue
        value = int(count_match.group(1).replace(",", ""))
        event = count_match.group(2)
        if event in EVENT_LABELS:
            counts[event] = value

    missing = [event for event in BIG_EVENTS + SMALL_EVENTS if event not in counts]
    if missing:
        raise ValueError(f"{path} missing perf events: {', '.join(missing)}")
    if elapsed_s is None:
        raise ValueError(f"{path} missing elapsed time")
    return counts, elapsed_s


def load_measurements(repo_root: Path) -> PerfMeasurements:
    counts: Dict[str, Dict[str, int]] = {}
    elapsed_s: Dict[str, float] = {}
    ipc: Dict[str, float] = {}
    sources: Dict[str, Path] = {}

    for mode, relative_path in MODE_FILES.items():
        source = repo_root / relative_path
        if not source.exists():
            raise FileNotFoundError(source)
        mode_counts, mode_elapsed = _read_perf(source)
        counts[mode] = mode_counts
        elapsed_s[mode] = mode_elapsed
        ipc[mode] = mode_counts["instructions"] / mode_counts["cycles"]
        sources[mode] = source

    return PerfMeasurements(counts=counts, elapsed_s=elapsed_s, ipc=ipc, sources=sources)


def _draw_summary_cards(svg: Svg, data: PerfMeasurements, x0: float, y0: float) -> None:
    cards = [
        (
            "elapsed",
            f"{data.elapsed_s['NVHE']:.6f}s -> {data.elapsed_s['protected']:.6f}s",
            f"{_format_ratio(data.elapsed_s['protected'] / data.elapsed_s['NVHE'])}, "
            f"+{(data.elapsed_s['protected'] - data.elapsed_s['NVHE']) / 50 * 1_000_000:.0f} us/iter",
        ),
        (
            "IPC",
            f"{data.ipc['NVHE']:.2f} -> {data.ipc['protected']:.2f}",
            "same instructions, lower progress per cycle",
        ),
        (
            "extra cycles",
            f"{(data.counts['protected']['cycles'] - data.counts['NVHE']['cycles']) / 1_000_000:.1f}M",
            "matches backend-stall growth",
        ),
    ]
    card_w = 315
    card_h = 82
    gap = 22
    for index, (title, value, note) in enumerate(cards):
        x = x0 + index * (card_w + gap)
        svg.add(
            f'<rect x="{x:.1f}" y="{y0:.1f}" width="{card_w}" height="{card_h}" '
            f'rx="7" fill="#F8FAFC" stroke="#D8DEE8" stroke-width="1"/>'
        )
        svg.text(x + 18, y0 + 26, title, size=12, fill="#64707D", weight=700)
        svg.text(x + 18, y0 + 55, value, size=21, fill="#1F2933", weight=700)
        svg.text(x + 18, y0 + 74, note, size=11, fill="#64707D")


def _draw_axis(
    svg: Svg,
    *,
    x0: float,
    y0: float,
    width: float,
    max_value: float,
    unit_label: str,
) -> float:
    axis_max = _axis_max(max_value, 5)
    step = _nice_step(axis_max, 5)
    value = 0.0
    while value <= axis_max + step / 10:
        x = x0 + (value / axis_max) * width if axis_max else x0
        svg.add(
            f'<line x1="{x:.1f}" y1="{y0 - 210:.1f}" x2="{x:.1f}" y2="{y0:.1f}" '
            f'stroke="#EDF1F5" stroke-width="1"/>'
        )
        svg.add(
            f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y0 + 5:.1f}" '
            f'stroke="#5C6670" stroke-width="1"/>'
        )
        svg.text(x, y0 + 22, f"{value:.0f}", size=11, fill="#5C6670", anchor="middle")
        value += step
    svg.add(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0 + width:.1f}" y2="{y0:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )
    svg.text(x0 + width / 2, y0 + 46, unit_label, size=12, fill="#4B5563", anchor="middle")
    return axis_max


def _draw_bar_panel(
    svg: Svg,
    data: PerfMeasurements,
    *,
    events: Iterable[str],
    x0: float,
    y0: float,
    title: str,
    subtitle: str,
    divisor: float,
    unit_label: str,
) -> None:
    events = list(events)
    label_w = 180
    plot_x = x0 + label_w
    plot_y = y0 + 48
    plot_w = 780
    row_gap = 58
    bar_h = 13
    axis_y = plot_y + row_gap * len(events) + 10
    max_scaled = max(data.counts[mode][event] / divisor for mode in MODE_FILES for event in events)
    axis_max = _draw_axis(svg, x0=plot_x, y0=axis_y, width=plot_w, max_value=max_scaled, unit_label=unit_label)

    svg.text(x0, y0, title, size=18, weight=700)
    svg.text(x0, y0 + 23, subtitle, size=12, fill="#64707D")

    legend_x = plot_x + 510
    legend_y = y0 + 10
    for mode in ["NVHE", "protected"]:
        svg.add(
            f'<rect x="{legend_x:.1f}" y="{legend_y - 10:.1f}" width="14" height="10" '
            f'rx="2" fill="{MODE_COLORS[mode]}"/>'
        )
        svg.text(legend_x + 20, legend_y, mode, size=11, fill="#374151")
        legend_x += 100

    for index, event in enumerate(events):
        row_y = plot_y + index * row_gap
        svg.text(x0, row_y + 18, EVENT_LABELS[event], size=12, fill="#374151")
        delta = data.counts["protected"][event] - data.counts["NVHE"][event]
        base = data.counts["NVHE"][event]
        pct = (delta / base * 100.0) if base else 0.0

        for offset, mode in [(0, "NVHE"), (bar_h + 4, "protected")]:
            scaled = data.counts[mode][event] / divisor
            width = (scaled / axis_max) * plot_w if axis_max else 0.0
            svg.add(
                f'<rect x="{plot_x:.1f}" y="{row_y + offset:.1f}" width="{width:.1f}" '
                f'height="{bar_h}" rx="2" fill="{MODE_COLORS[mode]}"/>'
            )
            svg.text(
                plot_x + width + 6,
                row_y + offset + 10,
                _format_count(data.counts[mode][event]),
                size=10,
                fill="#4B5563",
            )

        delta_text = f"delta {_format_delta(delta)} ({pct:+.1f}%)"
        fill = "#C23B2A" if event in {"cycles", "stall_backend"} and delta > 0 else "#64707D"
        svg.text(plot_x + plot_w + 18, row_y + 20, delta_text, size=11, fill=fill)


def render_svg(data: PerfMeasurements) -> str:
    svg = Svg(
        1180,
        940,
        "N80 perf cost layering for munmap_after_write_touch",
        "Grouped perf counters for NVHE and protected mode, parsed from raw perf stat output.",
    )
    svg.text(56, 48, "N80 perf cost layering", size=26, weight=700)
    svg.text(
        56,
        73,
        "munmap_after_write_touch, 64 MB x 50 iterations, cpu0",
        size=13,
        fill="#64707D",
    )

    _draw_summary_cards(svg, data, 56, 98)
    _draw_bar_panel(
        svg,
        data,
        events=BIG_EVENTS,
        x0=56,
        y0=235,
        title="large counters",
        subtitle="cycles and backend stalls grow; instructions stay flat",
        divisor=1_000_000,
        unit_label="million events",
    )
    _draw_bar_panel(
        svg,
        data,
        events=SMALL_EVENTS,
        x0=56,
        y0=545,
        title="translation-related counters",
        subtitle="page faults and DTLB walk counts do not grow with protected mode",
        divisor=1_000,
        unit_label="thousand events",
    )
    svg.text(
        56,
        922,
        "Source: results/n80-munmap-gate-c0/{nvhe,protected}/c0-*/perf-munmap_after_write_touch-64mb-*.txt",
        size=11,
        fill="#64707D",
    )
    return svg.render()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/mmap/figures/n80-perf-cost-layering.svg"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    out = args.out if args.out.is_absolute() else repo_root / args.out
    data = load_measurements(repo_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_svg(data), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
