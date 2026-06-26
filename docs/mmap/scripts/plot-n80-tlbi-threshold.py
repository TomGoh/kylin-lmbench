#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Render the N80 munmap TLBI-threshold sweep figures.

The script reads saved `op_sweep` output and plots only the `munmap` rows.  It
does not embed latency values; the experiment logs remain the source of truth.
"""

from __future__ import annotations

import argparse
import math
import re
from html import escape
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Tuple, Union


SOURCE_DIR = Path("experiments/munmap-tlbi/results/op-sweep-n80")
MODE_FILES = {
    "NVHE": SOURCE_DIR / "nvhe.txt",
    "protected": SOURCE_DIR / "protected.txt",
}
MODE_COLORS = {
    "NVHE": "#4D7C59",
    "protected": "#C23B2A",
}
SAMPLE_RE = re.compile(
    r"^(?P<op>\w+)\s+file\s+mb=(?P<mb>\d+)\s+touch=(?P<touch>[0-9.]+)MB\s+"
    r"stride=(?P<stride>\d+)K\s+:\s+mean=(?P<mean>[0-9.]+)\s+us\s+"
    r"min=(?P<min>[0-9.]+)\s+us"
)


class Sample(NamedTuple):
    touch_mb: float
    stride_kb: int
    mean_us: float
    min_us: float


class Measurements(NamedTuple):
    dense_sizes: List[float]
    dense_mean_us: Dict[str, Dict[float, float]]
    sparse_mean_us: Dict[str, float]
    delta_us: Dict[float, float]
    sparse_delta_us: float
    sub2_slope_us_per_mb: float
    sub2_intercept_us: float
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


def _format_size(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


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


def _polyline(points: List[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _linear_fit(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _read_mode(path: Path) -> List[Sample]:
    samples: List[Sample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = SAMPLE_RE.search(line)
        if not match or match.group("op") != "munmap":
            continue
        samples.append(
            Sample(
                touch_mb=float(match.group("touch")),
                stride_kb=int(match.group("stride")),
                mean_us=float(match.group("mean")),
                min_us=float(match.group("min")),
            )
        )
    if not samples:
        raise ValueError(f"no munmap samples found in {path}")
    return samples


def load_measurements(repo_root: Path) -> Measurements:
    repo_root = repo_root.resolve()
    dense_mean_us: Dict[str, Dict[float, float]] = {}
    sparse_mean_us: Dict[str, float] = {}
    sources: Dict[str, Path] = {}
    expected_dense_sizes = None

    for mode, relative_path in MODE_FILES.items():
        source = repo_root / relative_path
        if not source.exists():
            raise FileNotFoundError(source)
        sources[mode] = source
        samples = _read_mode(source)

        dense = {
            sample.touch_mb: sample.mean_us
            for sample in samples
            if sample.stride_kb == 4
        }
        sparse = [
            sample.mean_us
            for sample in samples
            if sample.stride_kb == 16 and abs(sample.touch_mb - 6.4) < 1e-9
        ]
        if not dense:
            raise ValueError(f"{source} has no dense stride=4 munmap samples")
        if len(sparse) != 1:
            raise ValueError(f"{source} should have exactly one sparse 6.4MB/16K munmap sample")

        sizes = sorted(dense)
        if expected_dense_sizes is None:
            expected_dense_sizes = sizes
        elif sizes != expected_dense_sizes:
            raise ValueError(f"{source} has dense sizes {sizes}, expected {expected_dense_sizes}")

        dense_mean_us[mode] = dense
        sparse_mean_us[mode] = sparse[0]

    if expected_dense_sizes is None:
        raise ValueError("no source files configured")

    delta_us = {
        size: dense_mean_us["protected"][size] - dense_mean_us["NVHE"][size]
        for size in expected_dense_sizes
    }
    sub2_sizes = [size for size in expected_dense_sizes if size < 2.0]
    slope, intercept = _linear_fit(sub2_sizes, [delta_us[size] for size in sub2_sizes])

    return Measurements(
        dense_sizes=expected_dense_sizes,
        dense_mean_us=dense_mean_us,
        sparse_mean_us=sparse_mean_us,
        delta_us=delta_us,
        sparse_delta_us=sparse_mean_us["protected"] - sparse_mean_us["NVHE"],
        sub2_slope_us_per_mb=slope,
        sub2_intercept_us=intercept,
        sources=sources,
    )


def _x_for(value: float, x_max: float, x0: float, width: float) -> float:
    return x0 + (value / x_max) * width if x_max else x0


def _y_for(value: float, y_max: float, y0: float, height: float) -> float:
    return y0 + height - (value / y_max) * height if y_max else y0 + height


def _draw_axes(
    svg: Svg,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    x_max: float,
    y_max: float,
    y_label: str,
    x_ticks: List[float],
    y_formatter: Callable[[float], str],
) -> None:
    bottom = y0 + height
    svg.add(
        f'<line x1="{x0:.1f}" y1="{bottom:.1f}" x2="{x0 + width:.1f}" y2="{bottom:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )
    svg.add(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{bottom:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )

    for tick in x_ticks:
        x = _x_for(tick, x_max, x0, width)
        svg.add(
            f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{bottom:.1f}" '
            f'stroke="#F0F3F7" stroke-width="1"/>'
        )
        svg.add(
            f'<line x1="{x:.1f}" y1="{bottom:.1f}" x2="{x:.1f}" y2="{bottom + 5:.1f}" '
            f'stroke="#5C6670" stroke-width="1"/>'
        )
        svg.text(x, bottom + 22, _format_size(tick), size=11, fill="#5C6670", anchor="middle")

    y_step = _nice_step(y_max, 5)
    value = 0.0
    while value <= y_max + y_step / 10:
        y = _y_for(value, y_max, y0, height)
        svg.add(
            f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0 + width:.1f}" y2="{y:.1f}" '
            f'stroke="#E6EAF0" stroke-width="1"/>'
        )
        svg.text(x0 - 10, y + 4, y_formatter(value), size=11, fill="#5C6670", anchor="end")
        value += y_step

    svg.text(x0 + width / 2, bottom + 46, "touch range (MB, linear scale)", size=12, fill="#4B5563", anchor="middle")
    svg.add(
        f'<text transform="translate({x0 - 52:.1f} {y0 + height / 2:.1f}) rotate(-90)" '
        f'font-size="12" fill="#4B5563" text-anchor="middle">{escape(y_label)}</text>'
    )


def _draw_threshold(svg: Svg, *, x0: float, y0: float, width: float, height: float, x_max: float) -> None:
    if x_max < 2:
        return
    x = _x_for(2.0, x_max, x0, width)
    svg.add(
        f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y0 + height:.1f}" '
        f'stroke="#7C3AED" stroke-width="1.4" stroke-dasharray="5 4"/>'
    )
    svg.text(x + 6, y0 + 14, "2 MB threshold", size=11, fill="#6D28D9")


def _draw_diamond(svg: Svg, x: float, y: float, color: str, *, size: float = 6.5) -> None:
    points = [
        (x, y - size),
        (x + size, y),
        (x, y + size),
        (x - size, y),
    ]
    svg.add(
        '<polygon points="'
        + " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
        + f'" fill="#FFFFFF" stroke="{color}" stroke-width="2"/>'
    )


def _draw_absolute_legend(svg: Svg, x: float, y: float) -> None:
    entries = [
        ("line", "NVHE dense 4K", MODE_COLORS["NVHE"], 170),
        ("line", "protected dense 4K", MODE_COLORS["protected"], 205),
        ("diamond", "sparse 6.4MB/16K ref", "#6B7280", 220),
    ]
    cursor = x
    for kind, label, color, advance in entries:
        if kind == "line":
            svg.add(
                f'<line x1="{cursor:.1f}" y1="{y:.1f}" x2="{cursor + 24:.1f}" y2="{y:.1f}" '
                f'stroke="{color}" stroke-width="2.4"/>'
            )
            svg.add(f'<circle cx="{cursor + 12:.1f}" cy="{y:.1f}" r="3.8" fill="{color}"/>')
        else:
            _draw_diamond(svg, cursor + 12, y, color, size=5)
        svg.text(cursor + 32, y + 4, label, size=12, fill="#374151")
        cursor += advance


def _draw_gap_legend(svg: Svg, x: float, y: float) -> None:
    svg.add(
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + 24:.1f}" y2="{y:.1f}" '
        f'stroke="#C23B2A" stroke-width="2.4"/>'
    )
    svg.add(f'<circle cx="{x + 12:.1f}" cy="{y:.1f}" r="3.9" fill="#C23B2A"/>')
    svg.text(x + 32, y + 4, "dense 4K gap", size=12, fill="#374151")
    _draw_diamond(svg, x + 185, y, "#6B7280", size=5)
    svg.text(x + 205, y + 4, "sparse 6.4MB/16K ref", size=12, fill="#374151")


def _draw_absolute_panel(
    svg: Svg,
    data: Measurements,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    x_max: float,
    panel_title: str,
    x_ticks: List[float],
) -> None:
    sizes = [size for size in data.dense_sizes if size <= x_max]
    y_values = [
        data.dense_mean_us[mode][size]
        for mode in ("NVHE", "protected")
        for size in sizes
    ]
    if x_max >= 6.4:
        y_values.extend(data.sparse_mean_us.values())
    y_max = _axis_max(max(y_values) * 1.08)

    svg.text(x0, y0 - 18, panel_title, size=15, weight=700, fill="#111827")
    _draw_axes(
        svg,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        x_max=x_max,
        y_max=y_max,
        y_label="munmap mean (us/iter)",
        x_ticks=x_ticks,
        y_formatter=lambda value: f"{value:.0f}",
    )
    _draw_threshold(svg, x0=x0, y0=y0, width=width, height=height, x_max=x_max)

    for mode in ("NVHE", "protected"):
        color = MODE_COLORS[mode]
        points = [
            (
                _x_for(size, x_max, x0, width),
                _y_for(data.dense_mean_us[mode][size], y_max, y0, height),
            )
            for size in sizes
        ]
        svg.add(
            f'<polyline points="{_polyline(points)}" fill="none" stroke="{color}" '
            f'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in points:
            svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{color}" stroke="#FFFFFF" stroke-width="1"/>')

    if x_max >= 6.4:
        for mode in ("NVHE", "protected"):
            x = _x_for(6.4, x_max, x0, width)
            y = _y_for(data.sparse_mean_us[mode], y_max, y0, height)
            _draw_diamond(svg, x, y, MODE_COLORS[mode])
        if x_max <= 8:
            svg.text(_x_for(6.4, x_max, x0, width) + 10, y0 + 24, "sparse ref", size=11, fill="#4B5563")


def _draw_gap_panel(
    svg: Svg,
    data: Measurements,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    x_max: float,
    panel_title: str,
    x_ticks: List[float],
    show_fit: bool = False,
) -> None:
    sizes = [size for size in data.dense_sizes if size <= x_max]
    y_values = [data.delta_us[size] for size in sizes]
    if x_max >= 6.4:
        y_values.append(data.sparse_delta_us)
    y_max = _axis_max(max(y_values) * 1.10)

    svg.text(x0, y0 - 18, panel_title, size=15, weight=700, fill="#111827")
    _draw_axes(
        svg,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        x_max=x_max,
        y_max=y_max,
        y_label="protected - NVHE (us/iter)",
        x_ticks=x_ticks,
        y_formatter=lambda value: f"{value:.0f}",
    )
    _draw_threshold(svg, x0=x0, y0=y0, width=width, height=height, x_max=x_max)

    points = [
        (
            _x_for(size, x_max, x0, width),
            _y_for(data.delta_us[size], y_max, y0, height),
        )
        for size in sizes
    ]
    svg.add(
        f'<polyline points="{_polyline(points)}" fill="none" stroke="#C23B2A" '
        f'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for size, (x, y) in zip(sizes, points):
        fill = "#C23B2A" if size < 2 else "#FFFFFF"
        svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.9" fill="{fill}" stroke="#C23B2A" stroke-width="1.8"/>')

    if show_fit:
        fit_xs = [0.0, 2.0]
        fit_points = [
            (
                _x_for(x, x_max, x0, width),
                _y_for(max(0.0, data.sub2_intercept_us + data.sub2_slope_us_per_mb * x), y_max, y0, height),
            )
            for x in fit_xs
        ]
        svg.add(
            f'<polyline points="{_polyline(fit_points)}" fill="none" stroke="#374151" '
            f'stroke-width="1.6" stroke-dasharray="5 4"/>'
        )
        label_x = _x_for(2.2, x_max, x0, width)
        label_y = _y_for(
            max(0.0, data.sub2_intercept_us + data.sub2_slope_us_per_mb * 2.0),
            y_max,
            y0,
            height,
        ) + 18
        svg.text(
            label_x,
            label_y,
            f"fit (<2MB): {data.sub2_slope_us_per_mb:.1f} us/MB",
            size=11,
            fill="#374151",
        )

    if x_max >= 6.4:
        x = _x_for(6.4, x_max, x0, width)
        y = _y_for(data.sparse_delta_us, y_max, y0, height)
        _draw_diamond(svg, x, y, "#6B7280")
        if x_max <= 8:
            svg.text(x + 10, y - 8, "sparse ref", size=11, fill="#4B5563")


def render_absolute(data: Measurements) -> str:
    svg = Svg(
        1180,
        560,
        "N80 munmap TLBI threshold sweep absolute latency",
        "Dense 4K munmap threshold sweep, with sparse 6.4MB/16K reference markers.",
    )
    svg.text(590, 34, "N80 munmap TLBI Threshold Sweep: Absolute Time", size=21, weight=700, anchor="middle")
    svg.text(590, 57, "dense 4K sweep is connected; sparse 6.4MB/16K reference is shown as diamonds", size=13, fill="#4B5563", anchor="middle")
    _draw_absolute_legend(svg, 305, 82)
    _draw_absolute_panel(
        svg,
        data,
        x0=84,
        y0=120,
        width=470,
        height=315,
        x_max=64,
        panel_title="Full range: 0-64 MB",
        x_ticks=[0, 16, 32, 48, 64],
    )
    _draw_absolute_panel(
        svg,
        data,
        x0=665,
        y0=120,
        width=430,
        height=315,
        x_max=8,
        panel_title="Detail: 0-8 MB",
        x_ticks=[0, 2, 4, 6, 8],
    )
    svg.text(590, 532, "Source: experiments/munmap-tlbi/results/op-sweep-n80/{nvhe,protected}.txt", size=12, fill="#6B7280", anchor="middle")
    return svg.render()


def render_gap(data: Measurements) -> str:
    svg = Svg(
        1180,
        560,
        "N80 munmap TLBI threshold sweep protected minus NVHE gap",
        "Protected minus NVHE delta for dense 4K munmap threshold sweep, with sparse reference marker.",
    )
    svg.text(590, 34, "N80 munmap TLBI Threshold Sweep: protected - NVHE Gap", size=21, weight=700, anchor="middle")
    svg.text(590, 57, "the sub-2MB gap grows linearly, then collapses when each PMD batch reaches the 2MB full-flush path", size=13, fill="#4B5563", anchor="middle")
    _draw_gap_legend(svg, 390, 82)
    _draw_gap_panel(
        svg,
        data,
        x0=84,
        y0=120,
        width=470,
        height=315,
        x_max=64,
        panel_title="Full range: 0-64 MB",
        x_ticks=[0, 16, 32, 48, 64],
        show_fit=False,
    )
    _draw_gap_panel(
        svg,
        data,
        x0=665,
        y0=120,
        width=430,
        height=315,
        x_max=8,
        panel_title="Detail: 0-8 MB",
        x_ticks=[0, 2, 4, 6, 8],
        show_fit=True,
    )
    svg.text(590, 532, "Source: experiments/munmap-tlbi/results/op-sweep-n80/{nvhe,protected}.txt", size=12, fill="#6B7280", anchor="middle")
    return svg.render()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="repository root")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/mmap/figures"), help="output directory")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_measurements(repo_root)
    (output_dir / "n80-tlbi-threshold-absolute.svg").write_text(render_absolute(data), encoding="utf-8")
    (output_dir / "n80-tlbi-threshold-gap.svg").write_text(render_gap(data), encoding="utf-8")


if __name__ == "__main__":
    main()
