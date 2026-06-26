#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Render the N90/Kylin V10 lat_mmap four-mode comparison as SVG.

The plotted values are recomputed from raw `lat_mmap_precise` logs.  Mode names
and log locations are part of the experiment definition; latency values are not
embedded here.
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
from html import escape
from pathlib import Path
from typing import Dict, List, NamedTuple, Union


MODE_LOGS = {
    "KVM-off": Path("results/n90-v10-kvmoff-mmap/precise-mmap/n90-v10-kvmoff-mmap.log"),
    "VHE": Path("results/n90-v10-vhe-mmap/precise-mmap/n90-v10-vhe-mmap.log"),
    "NVHE": Path("results/n90-v10-nvhe-mmap/precise-mmap/n90-v10-nvhe-mmap.log"),
    "pKVM": Path("results/n90-v10-pkvm-mmap/precise-mmap/n90-v10-pkvm-mmap.log"),
}

MODE_COLORS = {
    "KVM-off": "#4F6D7A",
    "VHE": "#8A6F3D",
    "NVHE": "#4D7C59",
    "pKVM": "#C23B2A",
}

SAMPLE_RE = re.compile(
    r"\bsize_mb=(?P<size>[0-9.]+)\b.*?\bper_iter_us=(?P<latency>[0-9.]+)\b"
)


class Measurements(NamedTuple):
    sizes: List[float]
    median_us: Dict[str, Dict[float, float]]
    mad_pct: Dict[str, Dict[float, float]]
    pkvm_vs_nvhe_pct: Dict[float, float]
    sources: Dict[str, Path]


def _median_absolute_deviation_pct(values: List[float]) -> float:
    median = statistics.median(values)
    if median == 0:
        return 0.0
    deviations = [abs(value - median) for value in values]
    return statistics.median(deviations) * 100.0 / median


def _load_mode_samples(path: Path) -> Dict[float, List[float]]:
    samples: Dict[float, List[float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = SAMPLE_RE.search(line)
        if not match:
            continue
        size = float(match.group("size"))
        latency = float(match.group("latency"))
        samples.setdefault(size, []).append(latency)

    if not samples:
        raise ValueError(f"no lat_mmap_precise samples found in {path}")
    return samples


def load_measurements(repo_root: Path) -> Measurements:
    repo_root = repo_root.resolve()
    median_us: Dict[str, Dict[float, float]] = {}
    mad_pct: Dict[str, Dict[float, float]] = {}
    sources: Dict[str, Path] = {}
    expected_sizes = None

    for mode, relative_path in MODE_LOGS.items():
        source = repo_root / relative_path
        if not source.exists():
            raise FileNotFoundError(source)

        samples = _load_mode_samples(source)
        sizes = sorted(samples)
        if expected_sizes is None:
            expected_sizes = sizes
        elif sizes != expected_sizes:
            raise ValueError(f"{source} has sizes {sizes}, expected {expected_sizes}")

        median_us[mode] = {
            size: statistics.median(values) for size, values in samples.items()
        }
        mad_pct[mode] = {
            size: _median_absolute_deviation_pct(values)
            for size, values in samples.items()
        }
        sources[mode] = source

    if expected_sizes is None:
        raise ValueError("no mode logs configured")

    pkvm_vs_nvhe_pct = {
        size: (median_us["pKVM"][size] / median_us["NVHE"][size] - 1.0) * 100.0
        for size in expected_sizes
    }

    return Measurements(
        sizes=expected_sizes,
        median_us=median_us,
        mad_pct=mad_pct,
        pkvm_vs_nvhe_pct=pkvm_vs_nvhe_pct,
        sources=sources,
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


def _tick_values(max_value: float, target_ticks: int = 5) -> List[float]:
    step = _nice_step(max_value, target_ticks)
    top = _axis_max(max_value, target_ticks)
    ticks = []
    value = 0.0
    while value <= top + step / 10:
        ticks.append(value)
        value += step
    return ticks


def _format_size(size: float) -> str:
    if size.is_integer():
        return str(int(size))
    return str(size)


def _polyline(points: List[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


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
        extra: str = "",
    ) -> None:
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}" {extra}>{escape(value)}</text>'
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


def _rotated_axis_label(svg: Svg, x: float, y: float, value: str) -> None:
    svg.add(
        f'<text transform="translate({x:.1f} {y:.1f}) rotate(-90)" '
        f'font-size="12" fill="#4B5563" text-anchor="middle">{escape(value)}</text>'
    )


def _draw_panel_frame(
    svg: Svg,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    y_ticks: List[float],
    y_max: float,
    y_label_formatter,
) -> None:
    plot_bottom = y0 + height
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{width:.1f}" height="{height:.1f}" fill="#FFFFFF"/>')
    for tick in y_ticks:
        y = plot_bottom - (tick / y_max) * height if y_max else plot_bottom
        svg.add(
            f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0 + width:.1f}" y2="{y:.1f}" '
            f'stroke="#E6EAF0" stroke-width="1"/>'
        )
        svg.text(x0 - 10, y + 4, y_label_formatter(tick), size=12, fill="#5C6670", anchor="end")
    svg.add(
        f'<line x1="{x0:.1f}" y1="{plot_bottom:.1f}" x2="{x0 + width:.1f}" y2="{plot_bottom:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )
    svg.add(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{plot_bottom:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )


def _linear_x_positions(sizes: List[float], x0: float, width: float) -> Dict[float, float]:
    if any(size < 0 for size in sizes):
        raise ValueError("size values must be non-negative for the linear x-axis")
    max_size = max(sizes)
    if max_size == 0:
        return {size: x0 + width / 2 for size in sizes}
    return {size: x0 + (size / max_size) * width for size in sizes}


def _category_x_positions(sizes: List[float], x0: float, width: float) -> Dict[float, float]:
    if len(sizes) == 1:
        return {sizes[0]: x0 + width / 2}
    step = width / (len(sizes) - 1)
    return {size: x0 + index * step for index, size in enumerate(sizes)}


def _min_gap(values: List[float]) -> float:
    ordered = sorted(values)
    if len(ordered) < 2:
        return 1.0
    return min(b - a for a, b in zip(ordered, ordered[1:]))


def _draw_x_labels(svg: Svg, sizes: List[float], x_by_size: Dict[float, float], bottom: float) -> None:
    for size in sizes:
        svg.text(x_by_size[size], bottom + 24, _format_size(size), size=12, fill="#4B5563", anchor="middle")


def _draw_linear_x_ticks(svg: Svg, max_size: float, x0: float, width: float, bottom: float, top: float) -> None:
    for fraction in range(5):
        tick = max_size * fraction / 4
        x = x0 + (tick / max_size) * width if max_size else x0
        svg.add(
            f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{bottom:.1f}" '
            f'stroke="#F0F3F7" stroke-width="1"/>'
        )
        svg.add(
            f'<line x1="{x:.1f}" y1="{bottom:.1f}" x2="{x:.1f}" y2="{bottom + 5:.1f}" '
            f'stroke="#5C6670" stroke-width="1"/>'
        )
        svg.text(x, bottom + 24, _format_size(tick), size=12, fill="#4B5563", anchor="middle")


def _draw_legend(svg: Svg, x: float, y: float) -> None:
    offset = 0.0
    for mode in MODE_LOGS:
        color = MODE_COLORS[mode]
        svg.add(
            f'<line x1="{x + offset:.1f}" y1="{y:.1f}" x2="{x + offset + 24:.1f}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-width="{3 if mode == "pKVM" else 2}"/>'
        )
        svg.add(
            f'<circle cx="{x + offset + 12:.1f}" cy="{y:.1f}" r="3.8" fill="#FFFFFF" '
            f'stroke="{color}" stroke-width="1.8"/>'
        )
        svg.text(x + offset + 31, y + 4, mode, size=12, fill="#374151")
        offset += 96 if mode != "KVM-off" else 114


def _draw_absolute_panel(
    svg: Svg,
    data: Measurements,
    x0: float,
    y0: float,
    width: float,
    height: float,
    *,
    sizes: List[float],
    panel_title: str,
    subtitle: str,
    show_legend: bool = False,
) -> None:
    max_latency = max(data.median_us[mode][size] for mode in MODE_LOGS for size in sizes)
    y_max = _axis_max(max_latency, 5)
    ticks = _tick_values(max_latency, 5)
    bottom = y0 + height
    x_by_size = _linear_x_positions(sizes, x0 + 6, width - 6)

    svg.text(x0, y0 - 36, panel_title, size=16, weight=700)
    svg.text(x0, y0 - 14, subtitle, size=12, fill="#64707D")
    _draw_panel_frame(
        svg,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        y_ticks=ticks,
        y_max=y_max,
        y_label_formatter=lambda value: f"{value:.0f}",
    )

    _draw_linear_x_ticks(svg, max(sizes), x0, width, bottom, y0)

    for mode in MODE_LOGS:
        color = MODE_COLORS[mode]
        points = [
            (x_by_size[size], bottom - (data.median_us[mode][size] / y_max) * height)
            for size in sizes
        ]
        svg.add(
            f'<polyline points="{_polyline(points)}" fill="none" stroke="{color}" '
            f'stroke-width="{3 if mode == "pKVM" else 2.2}" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in points:
            svg.add(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4.2 if mode == "pKVM" else 3.5}" '
                f'fill="#FFFFFF" stroke="{color}" stroke-width="1.8"/>'
            )

    _rotated_axis_label(svg, x0 - 54, y0 + height / 2, "us / iter")
    svg.text(x0 + width / 2, bottom + 50, "mapping size (MB, linear scale)", size=12, fill="#4B5563", anchor="middle")
    if show_legend:
        _draw_legend(svg, x0 + 16, y0 + 18)


def _draw_overhead_panel(svg: Svg, data: Measurements, x0: float, y0: float, width: float, height: float) -> None:
    max_overhead = max(data.pkvm_vs_nvhe_pct.values())
    y_max = _axis_max(max_overhead, 5)
    ticks = _tick_values(max_overhead, 5)
    bottom = y0 + height
    x_by_size = _category_x_positions(data.sizes, x0 + 24, width - 48)
    bar_width = min(34.0, _min_gap(list(x_by_size.values())) * 0.42)

    svg.text(x0, y0 - 36, "pKVM overhead vs NVHE", size=18, weight=700)
    svg.text(x0, y0 - 14, "same runs, median(pKVM) / median(NVHE) - 1", size=12, fill="#64707D")
    _draw_panel_frame(
        svg,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        y_ticks=ticks,
        y_max=y_max,
        y_label_formatter=lambda value: f"{value:.0f}%",
    )

    for size in data.sizes:
        x = x_by_size[size]
        value = data.pkvm_vs_nvhe_pct[size]
        bar_height = (value / y_max) * height
        y = bottom - bar_height
        svg.add(
            f'<rect x="{x - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{bar_height:.1f}" rx="3" fill="#D45745"/>'
        )
        svg.add(
            f'<line x1="{x:.1f}" y1="{bottom:.1f}" x2="{x:.1f}" y2="{bottom + 5:.1f}" '
            f'stroke="#5C6670" stroke-width="1"/>'
        )
        svg.text(x, y - 8, f"{value:.1f}%", size=12, fill="#9E2F24", anchor="middle", weight=700)

    _draw_x_labels(svg, data.sizes, x_by_size, bottom)
    _rotated_axis_label(svg, x0 - 56, y0 + height / 2, "overhead (%)")
    svg.text(x0 + width / 2, bottom + 50, "mapping size (MB)", size=12, fill="#4B5563", anchor="middle")


def _add_source_note(svg: Svg, y: float) -> None:
    svg.text(
        svg.width / 2,
        y,
        "Source: results/n90-v10-*-mmap/precise-mmap/*.log; median of 10 runs",
        size=11,
        fill="#7A8591",
        anchor="middle",
    )


def write_absolute_svg(data: Measurements, out_path: Path) -> None:
    width = 1180
    height = 520
    svg = Svg(
        width,
        height,
        "lat_mmap absolute latency",
        "Median lat_mmap_precise latency recomputed from raw logs, with full-range and <=8 MB linear views.",
    )
    svg.add(
        '<style>text{font-family:Inter,Arial,"Noto Sans",sans-serif;} '
        '.source{font-size:11px;fill:#7A8591;}</style>'
    )
    svg.text(76, 36, "N90 lat_mmap absolute latency", size=20, weight=700)
    svg.text(76, 58, "Kylin V10 / 6.6.30+ #4, median of 10 runs", size=12, fill="#64707D")

    _draw_absolute_panel(
        svg,
        data,
        x0=76,
        y0=118,
        width=500,
        height=290,
        sizes=data.sizes,
        panel_title="full range",
        subtitle="0-64 MB, absolute latency",
        show_legend=True,
    )
    _draw_absolute_panel(
        svg,
        data,
        x0=692,
        y0=118,
        width=390,
        height=290,
        sizes=[size for size in data.sizes if size <= 8],
        panel_title="detail: 0-8 MB",
        subtitle="same data, small-size range only",
    )
    _add_source_note(svg, height - 26)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg.render(), encoding="utf-8")


def write_overhead_svg(data: Measurements, out_path: Path) -> None:
    width = 900
    height = 500
    svg = Svg(
        width,
        height,
        "pKVM overhead vs NVHE",
        "pKVM relative overhead against NVHE, recomputed from median lat_mmap_precise latency.",
    )
    svg.add(
        '<style>text{font-family:Inter,Arial,"Noto Sans",sans-serif;} '
        '.source{font-size:11px;fill:#7A8591;}</style>'
    )

    _draw_overhead_panel(svg, data, x0=86, y0=88, width=720, height=300)
    _add_source_note(svg, height - 26)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg.render(), encoding="utf-8")


def _print_summary(data: Measurements) -> None:
    header = ["size_mb", *MODE_LOGS.keys(), "pKVM_vs_NVHE_pct"]
    print(",".join(header))
    for size in data.sizes:
        values = [
            _format_size(size),
            *(f"{data.median_us[mode][size]:.6f}" for mode in MODE_LOGS),
            f"{data.pkvm_vs_nvhe_pct[size]:.2f}",
        ]
        print(",".join(values))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--absolute-output",
        type=Path,
        default=Path("docs/mmap/figures/n90-v10-lat-mmap-absolute.svg"),
    )
    parser.add_argument(
        "--overhead-output",
        type=Path,
        default=Path("docs/mmap/figures/n90-v10-lat-mmap-overhead.svg"),
    )
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    data = load_measurements(args.repo_root)
    absolute_output = args.absolute_output
    overhead_output = args.overhead_output
    if not absolute_output.is_absolute():
        absolute_output = args.repo_root / absolute_output
    if not overhead_output.is_absolute():
        overhead_output = args.repo_root / overhead_output
    write_absolute_svg(data, absolute_output)
    write_overhead_svg(data, overhead_output)
    if args.print_summary:
        _print_summary(data)
    print(absolute_output)
    print(overhead_output)


if __name__ == "__main__":
    main()
