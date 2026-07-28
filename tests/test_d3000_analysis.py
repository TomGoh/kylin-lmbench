import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class D3000AnalysisTest(unittest.TestCase):
    def test_geekbench_wall_time_is_available_without_saved_score_page(self):
        analyzer = load_script(
            "d3000_analyze_results",
            "experiments/d3000-pkvm-apps/analyze-results.py",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            rep = Path(tmpdir)
            (rep / "stdout.txt").write_text("Upload succeeded.\n")
            (rep / "time.txt").write_text(
                "Elapsed (wall clock) time (h:mm:ss or m:ss): 6:38.15\n"
            )
            rows = []
            analyzer.parse_geekbench(rows, 1, "nvhe", 1, rep)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metric"], "wall_time")
        self.assertAlmostEqual(rows[0]["value"], 398.15)
        self.assertFalse(rows[0]["higher_better"])

    def test_exact_sign_test_boundary_with_five_pairs(self):
        deep = load_script(
            "d3000_deep_analysis",
            "experiments/d3000-pkvm-apps/deep-analysis.py",
        )
        self.assertEqual(deep.exact_two_sided_sign_p([1, 1, 1, 1, 1]), 0.0625)
        self.assertEqual(deep.exact_two_sided_sign_p([1, 1, 1, 1, -1]), 0.375)
        self.assertEqual(deep.exact_two_sided_sign_p([0, 0, 0]), 1.0)

    def test_exact_spearman_trend_detects_strict_pair_ordering(self):
        deep = load_script(
            "d3000_deep_analysis_trend",
            "experiments/d3000-pkvm-apps/deep-analysis.py",
        )
        rho, p_value = deep.exact_spearman_trend([5, 4, 3, 2, 1])
        self.assertEqual(rho, -1.0)
        self.assertAlmostEqual(p_value, 2 / 120)


if __name__ == "__main__":
    unittest.main()
