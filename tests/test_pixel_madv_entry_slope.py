import csv
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "experiments" / "munmap-tlbi" / "pixel_madv_entry_slope.c"


class PixelMadvEntrySlopeTest(unittest.TestCase):
    def compile_tool(self, tmpdir: Path) -> Path:
        out = tmpdir / "pixel_madv_entry_slope"
        subprocess.run(
            [
                "cc",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-o",
                str(out),
                str(SRC),
            ],
            check=True,
            cwd=ROOT,
        )
        return out

    def run_tool(self, tool: Path, *args: str):
        return subprocess.run(
            [str(tool), *args],
            check=True,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_single_touched_outputs_csv_rows_for_each_page_count(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self.compile_tool(Path(d))
            result = self.run_tool(
                tool,
                "--mode",
                "single",
                "--touch",
                "touched",
                "--pages",
                "1,2",
                "--runs",
                "2",
                "--seed",
                "7",
            )

        rows = list(csv.DictReader(result.stdout.splitlines()))
        self.assertEqual(len(rows), 4)
        self.assertEqual(sorted({row["pages"] for row in rows}), ["1", "2"])
        self.assertEqual({row["mode"] for row in rows}, {"single"})
        self.assertEqual({row["touch"] for row in rows}, {"touched"})
        self.assertEqual({row["page_size"] for row in rows}, {"4096"})
        for row in rows:
            self.assertGreaterEqual(int(row["setup_elapsed_ns"]), 0)
            self.assertGreaterEqual(int(row["setup_minor_faults_delta"]), 0)
            self.assertGreaterEqual(int(row["elapsed_ns"]), 0)
            self.assertGreaterEqual(int(row["timed_minor_faults_delta"]), 0)
            self.assertIn("cpu_before", row)
            self.assertIn("cpu_after", row)
            self.assertEqual(row["status"], "ok")

    def test_batched_untouched_outputs_one_row_per_run(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self.compile_tool(Path(d))
            result = self.run_tool(
                tool,
                "--mode",
                "batched",
                "--touch",
                "untouched",
                "--pages",
                "3",
                "--runs",
                "3",
            )

        rows = list(csv.DictReader(result.stdout.splitlines()))
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["mode"] for row in rows}, {"batched"})
        self.assertEqual({row["touch"] for row in rows}, {"untouched"})
        self.assertEqual({row["pages"] for row in rows}, {"3"})
        self.assertEqual({row["op_count"] for row in rows}, {"1"})


if __name__ == "__main__":
    unittest.main()
