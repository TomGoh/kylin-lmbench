import csv
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "experiments" / "munmap-tlbi" / "pixel-analyze-madv-entry-slope.py"


def write_rows(path: Path, mode_label: str, touch: str, rows, probe_mode: str = "single"):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "schema_version",
                "mode",
                "touch",
                "page_size",
                "pages",
                "run_index",
                "op_count",
                "setup_elapsed_ns",
                "setup_minor_faults_delta",
                "elapsed_ns",
                "timed_minor_faults_delta",
                "status",
            ],
        )
        writer.writeheader()
        for run_index, (pages, elapsed_ns) in enumerate(rows):
            writer.writerow(
                {
                    "schema_version": "1",
                    "mode": probe_mode,
                    "touch": touch,
                    "page_size": "4096",
                    "pages": str(pages),
                    "run_index": str(run_index),
                    "op_count": str(pages),
                    "setup_elapsed_ns": "1000",
                    "setup_minor_faults_delta": str(pages if touch == "touched" else 0),
                    "elapsed_ns": str(elapsed_ns),
                    "timed_minor_faults_delta": "0",
                    "status": "ok",
                }
            )


class PixelMadvAnalyzeTest(unittest.TestCase):
    def test_analyzer_computes_did_and_resolution_floor(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            # nvhe touched slope = 100 ns/op; protected touched slope = 160 ns/op.
            # nvhe untouched slope = 10 ns/op; protected untouched slope = 30 ns/op.
            # DiD = (160 - 100) - (30 - 10) = 40 ns/op.
            write_rows(base / "nvhe_touched.csv", "nvhe", "touched", [(100, 10000), (200, 20000)])
            write_rows(base / "protected_touched.csv", "protected", "touched", [(100, 16000), (200, 32000)])
            write_rows(base / "nvhe_untouched.csv", "nvhe", "untouched", [(100, 1000), (200, 2000)])
            write_rows(base / "protected_untouched.csv", "protected", "untouched", [(100, 3000), (200, 6000)])

            result = subprocess.run(
                [
                    "python3",
                    str(ANALYZER),
                    "--boot-pair-id",
                    "pair01",
                    "--nvhe-touched",
                    str(base / "nvhe_touched.csv"),
                    "--protected-touched",
                    str(base / "protected_touched.csv"),
                    "--nvhe-untouched",
                    str(base / "nvhe_untouched.csv"),
                    "--protected-untouched",
                    str(base / "protected_untouched.csv"),
                ],
                cwd=ROOT,
                text=True,
                check=True,
                stdout=subprocess.PIPE,
            )

        rows = list(csv.DictReader(result.stdout.splitlines()))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["boot_pair_id"], "pair01")
        self.assertAlmostEqual(float(row["raw_delta_ns_per_op"]), 60.0)
        self.assertAlmostEqual(float(row["drift_delta_ns_per_op"]), 20.0)
        self.assertAlmostEqual(float(row["per_entry_cost_did_ns_per_op"]), 40.0)
        self.assertGreaterEqual(float(row["resolution_floor_ns_per_op"]), 20.0)

    def test_analyzer_filters_combined_runner_csvs(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            nvhe = base / "nvhe.csv"
            protected = base / "protected.csv"
            with nvhe.open("w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "reject_reason",
                        "cpu_target",
                        "schema_version",
                        "mode",
                        "touch",
                        "page_size",
                        "pages",
                        "run_index",
                        "op_count",
                        "setup_elapsed_ns",
                        "setup_minor_faults_delta",
                        "elapsed_ns",
                        "timed_minor_faults_delta",
                        "cpu_before",
                        "cpu_after",
                        "status",
                    ],
                )
                writer.writeheader()
                for touch, rows in {
                    "touched": [(100, 10000), (200, 20000)],
                    "untouched": [(100, 1000), (200, 2000)],
                }.items():
                    for i, (pages, elapsed) in enumerate(rows):
                        writer.writerow(
                            {
                                "reject_reason": "ok",
                                "cpu_target": "4",
                                "schema_version": "1",
                                "mode": "single",
                                "touch": touch,
                                "page_size": "4096",
                                "pages": pages,
                                "run_index": i,
                                "op_count": pages,
                                "setup_elapsed_ns": "1",
                                "setup_minor_faults_delta": "0",
                                "elapsed_ns": elapsed,
                                "timed_minor_faults_delta": "0",
                                "cpu_before": "4",
                                "cpu_after": "4",
                                "status": "ok",
                            }
                        )
                # This migrated row must be ignored even though reject_reason is ok.
                writer.writerow(
                    {
                        "reject_reason": "ok",
                        "cpu_target": "4",
                        "schema_version": "1",
                        "mode": "single",
                        "touch": "touched",
                        "page_size": "4096",
                        "pages": "300",
                        "run_index": "99",
                        "op_count": "300",
                        "setup_elapsed_ns": "1",
                        "setup_minor_faults_delta": "0",
                        "elapsed_ns": "999999",
                        "timed_minor_faults_delta": "0",
                        "cpu_before": "4",
                        "cpu_after": "5",
                        "status": "ok",
                    }
                )
                # This batched row must be ignored by --probe-mode single.
                writer.writerow(
                    {
                        "reject_reason": "ok",
                        "cpu_target": "4",
                        "schema_version": "1",
                        "mode": "batched",
                        "touch": "touched",
                        "page_size": "4096",
                        "pages": "200",
                        "run_index": "0",
                        "op_count": "1",
                        "setup_elapsed_ns": "1",
                        "setup_minor_faults_delta": "0",
                        "elapsed_ns": "999999",
                        "timed_minor_faults_delta": "0",
                        "cpu_before": "4",
                        "cpu_after": "4",
                        "status": "ok",
                    }
                )
            with protected.open("w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "reject_reason",
                        "cpu_target",
                        "schema_version",
                        "mode",
                        "touch",
                        "page_size",
                        "pages",
                        "run_index",
                        "op_count",
                        "setup_elapsed_ns",
                        "setup_minor_faults_delta",
                        "elapsed_ns",
                        "timed_minor_faults_delta",
                        "cpu_before",
                        "cpu_after",
                        "status",
                    ],
                )
                writer.writeheader()
                for touch, rows in {
                    "touched": [(100, 16000), (200, 32000)],
                    "untouched": [(100, 3000), (200, 6000)],
                }.items():
                    for i, (pages, elapsed) in enumerate(rows):
                        writer.writerow(
                            {
                                "reject_reason": "ok",
                                "cpu_target": "4",
                                "schema_version": "1",
                                "mode": "single",
                                "touch": touch,
                                "page_size": "4096",
                                "pages": pages,
                                "run_index": i,
                                "op_count": pages,
                                "setup_elapsed_ns": "1",
                                "setup_minor_faults_delta": "0",
                                "elapsed_ns": elapsed,
                                "timed_minor_faults_delta": "0",
                                "cpu_before": "4",
                                "cpu_after": "4",
                                "status": "ok",
                            }
                        )

            result = subprocess.run(
                [
                    "python3",
                    str(ANALYZER),
                    "--boot-pair-id",
                    "pair02",
                    "--nvhe-csv",
                    str(nvhe),
                    "--protected-csv",
                    str(protected),
                    "--probe-mode",
                    "single",
                ],
                cwd=ROOT,
                text=True,
                check=True,
                stdout=subprocess.PIPE,
            )

        row = list(csv.DictReader(result.stdout.splitlines()))[0]
        self.assertEqual(row["n_points"], "2")
        self.assertEqual(row["n_max"], "200")
        self.assertAlmostEqual(float(row["per_entry_cost_did_ns_per_op"]), 40.0)


if __name__ == "__main__":
    unittest.main()
