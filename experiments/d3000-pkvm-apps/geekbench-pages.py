#!/usr/bin/env python3
"""Build a Geekbench URL manifest and import user-saved result pages."""

import argparse
import csv
import hashlib
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


CANONICAL_URL = re.compile(r"https://browser\.geekbench\.com/v6/cpu/([0-9]+)/?$")
WORKLOADS = (
    ("file_compression", "File Compression"),
    ("navigation", "Navigation"),
    ("html5_browser", "HTML5 Browser"),
    ("pdf_renderer", "PDF Renderer"),
    ("photo_library", "Photo Library"),
    ("clang", "Clang"),
    ("text_processing", "Text Processing"),
    ("asset_compression", "Asset Compression"),
    ("object_detection", "Object Detection"),
    ("background_blur", "Background Blur"),
    ("horizon_detection", "Horizon Detection"),
    ("object_remover", "Object Remover"),
    ("hdr", "HDR"),
    ("photo_filter", "Photo Filter"),
    ("ray_tracer", "Ray Tracer"),
    ("structure_from_motion", "Structure from Motion"),
)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def html_text(raw):
    parser = VisibleText()
    parser.feed(raw)
    return " ".join(html.unescape(" ".join(parser.parts)).split())


def score_after_label(text, label):
    match = re.search(rf"{re.escape(label)}\s+([0-9][0-9,]*)\b", text, re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


def score_before_label(text, label):
    match = re.search(rf"\b([0-9][0-9,]*)\s+{re.escape(label)}\b", text, re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


def section(text, start, end=None):
    start_match = re.search(re.escape(start), text, re.IGNORECASE)
    if not start_match:
        return ""
    tail = text[start_match.end() :]
    if end:
        end_match = re.search(re.escape(end), tail, re.IGNORECASE)
        if end_match:
            tail = tail[: end_match.start()]
    return tail


def parse_page(path):
    raw_bytes = path.read_bytes()
    text = html_text(raw_bytes.decode(errors="replace"))
    single = section(text, "Single-Core Performance", "Multi-Core Performance")
    multi = section(text, "Multi-Core Performance")
    scores = {}
    for prefix, block, label in (
        ("single", single, "Single-Core Score"),
        ("multi", multi, "Multi-Core Score"),
    ):
        headline = score_after_label(block, label)
        if headline is None:
            headline = score_before_label(text, label)
        if headline is not None:
            scores[f"{prefix}_core_score"] = headline
        for slug, workload in WORKLOADS:
            value = score_after_label(block, workload)
            if value is not None:
                scores[f"{prefix}_{slug}_score"] = value
    missing = [name for name in ("single_core_score", "multi_core_score") if name not in scores]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}; saved file may be a Cloudflare challenge page")
    return scores, hashlib.sha256(raw_bytes).hexdigest()


def iter_repetitions(campaign):
    for pair_dir in sorted(campaign.glob("pair-[1-5]")):
        pair = pair_dir.name.removeprefix("pair-")
        for mode in ("nvhe", "protected"):
            geek = pair_dir / mode / "geekbench-cpu"
            if not geek.is_dir():
                continue
            candidates = list(geek.glob("rep-*/rep-*")) + list(geek.glob("rep-*"))
            seen = set()
            for rep_dir in sorted(candidates):
                if rep_dir in seen or not (rep_dir / "VALID").exists() or not (rep_dir / "result-urls.txt").exists():
                    continue
                seen.add(rep_dir)
                urls = [x.strip() for x in (rep_dir / "result-urls.txt").read_text().splitlines()]
                canonical = [(m.group(1), url) for url in urls if (m := CANONICAL_URL.fullmatch(url))]
                if len(canonical) != 1:
                    yield pair, mode, rep_dir, None, None, f"expected one canonical URL, found {len(canonical)}"
                    continue
                result_id, url = canonical[0]
                yield pair, mode, rep_dir, result_id, url, ""


def main():
    parser = argparse.ArgumentParser(
        description="Create geekbench-page-manifest.csv and import <result-id>.html pages"
    )
    parser.add_argument("campaign", type=Path)
    parser.add_argument(
        "--pages",
        type=Path,
        help="directory containing pages saved as <Geekbench result id>.html; default: CAMPAIGN/geekbench-pages",
    )
    parser.add_argument("--strict", action="store_true", help="fail unless every valid repetition has a parsed page")
    args = parser.parse_args()

    campaign = args.campaign.resolve()
    pages = (args.pages or campaign / "geekbench-pages").resolve()
    pages.mkdir(parents=True, exist_ok=True)
    records = []
    imported = missing = failed = 0
    for pair, mode, rep_dir, result_id, url, error in iter_repetitions(campaign):
        rep_text = rep_dir.name.removeprefix("rep-")
        expected = pages / f"{result_id}.html" if result_id else pages / "INVALID.html"
        row = {
            "pair": pair,
            "mode": mode,
            "rep": rep_text,
            "result_id": result_id or "",
            "url": url or "",
            "save_as": str(expected),
            "status": "",
            "detail": error,
        }
        if error:
            row["status"] = "invalid-url"
            failed += 1
        else:
            page = rep_dir / "result-page.html"
            source = page if page.exists() else expected
            if not source.exists():
                row["status"] = "missing-html"
                missing += 1
            else:
                try:
                    scores, digest = parse_page(source)
                    payload = {
                        "result_id": result_id,
                        "url": url,
                        "source_html": str(source),
                        "source_sha256": digest,
                        "scores": scores,
                    }
                    (rep_dir / "scores.json").write_text(json.dumps(payload, indent=2) + "\n")
                    row["status"] = "imported"
                    row["detail"] = f"{len(scores)} scores sha256={digest}"
                    imported += 1
                except (OSError, ValueError) as exc:
                    row["status"] = "parse-error"
                    row["detail"] = str(exc)
                    failed += 1
        records.append(row)

    manifest = campaign / "geekbench-page-manifest.csv"
    fields = ["pair", "mode", "rep", "result_id", "url", "save_as", "status", "detail"]
    with manifest.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    print(f"manifest={manifest} total={len(records)} imported={imported} missing={missing} failed={failed}")
    if args.strict and (missing or failed or not records):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
