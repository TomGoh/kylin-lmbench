import csv
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARIZER = ROOT / "experiments" / "munmap-tlbi" / "pixel-summarize-madv-entry-slope.py"


class PixelMadvSummarizeTest(unittest.TestCase):
    def test_summarizer_reports_resolution_floor_from_pair_rows(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pairs.csv"
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "boot_pair_id",
                        "per_entry_cost_did_ns_per_op",
                        "drift_delta_ns_per_op",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "boot_pair_id": "pair01",
                        "per_entry_cost_did_ns_per_op": "40",
                        "drift_delta_ns_per_op": "5",
                    }
                )
                writer.writerow(
                    {
                        "boot_pair_id": "pair02",
                        "per_entry_cost_did_ns_per_op": "60",
                        "drift_delta_ns_per_op": "-7",
                    }
                )
                writer.writerow(
                    {
                        "boot_pair_id": "pair03",
                        "per_entry_cost_did_ns_per_op": "80",
                        "drift_delta_ns_per_op": "9",
                    }
                )

            result = subprocess.run(
                [
                    "python3",
                    str(SUMMARIZER),
                    "--input",
                    str(path),
                    "--label",
                    "single",
                    "--bootstrap-reps",
                    "0",
                ],
                cwd=ROOT,
                text=True,
                check=True,
                stdout=subprocess.PIPE,
            )

        row = list(csv.DictReader(result.stdout.splitlines()))[0]
        self.assertEqual(row["label"], "single")
        self.assertEqual(row["n_boot_pairs"], "3")
        self.assertAlmostEqual(float(row["per_entry_median_ns_per_op"]), 60.0)
        self.assertAlmostEqual(float(row["per_entry_mean_ns_per_op"]), 60.0)
        self.assertAlmostEqual(float(row["drift_delta_median_ns_per_op"]), 5.0)
        self.assertAlmostEqual(float(row["abs_median_drift_ns_per_op"]), 5.0)
        self.assertAlmostEqual(float(row["resolution_floor_ns_per_op"]), 5.0)


if __name__ == "__main__":
    unittest.main()
