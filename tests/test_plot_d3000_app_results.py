import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "mmap" / "scripts" / "plot-d3000-app-results.py"


def load_plot_module():
    spec = importlib.util.spec_from_file_location("plot_d3000_app_results", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metric_rows(pair, mode, project, scenario, metric, values, unit, higher_better):
    return [
        {
            "pair": str(pair),
            "mode": mode,
            "project": project,
            "scenario": scenario,
            "rep": str(index),
            "metric": metric,
            "value": str(value),
            "unit": unit,
            "higher_better": str(higher_better),
        }
        for index, value in enumerate(values, 1)
    ]


class PlotD3000AppResultsTest(unittest.TestCase):
    def test_uses_boot_medians_and_normalizes_penalty_direction(self):
        mod = load_plot_module()
        rows = []
        rows += metric_rows(1, "nvhe", "redis", "r2-pipeline", "throughput", [98, 99, 100, 101, 500], "ops/s", True)
        rows += metric_rows(1, "protected", "redis", "r2-pipeline", "throughput", [88, 89, 90, 91, 400], "ops/s", True)
        rows += metric_rows(1, "nvhe", "redis", "r1-steady", "latency_avg", [9, 10, 10, 10, 100], "ms", False)
        rows += metric_rows(1, "protected", "redis", "r1-steady", "latency_avg", [11, 12, 12, 12, 120], "ms", False)

        data = mod.aggregate_rows(rows)

        self.assertAlmostEqual(data.boot_medians[(1, "nvhe", "redis", "r2-pipeline", "throughput")], 100.0)
        self.assertAlmostEqual(data.boot_medians[(1, "protected", "redis", "r2-pipeline", "throughput")], 90.0)
        self.assertAlmostEqual(data.penalties_pct[("redis", "r2-pipeline", "throughput")][1], 10.0)
        self.assertAlmostEqual(data.penalties_pct[("redis", "r1-steady", "latency_avg")][1], 20.0)

    def test_renders_overview_load_curve_and_pair_matrix(self):
        mod = load_plot_module()
        rows = []
        rows += metric_rows(1, "nvhe", "redis", "r1-steady", "latency_avg", [1.0] * 5, "ms", False)
        rows += metric_rows(1, "protected", "redis", "r1-steady", "latency_avg", [1.1] * 5, "ms", False)
        rows += metric_rows(1, "nvhe", "geekbench", "cpu", "wall_time", [400.0] * 5, "s", False)
        rows += metric_rows(1, "protected", "geekbench", "cpu", "wall_time", [402.0] * 5, "s", False)
        for load, nvhe_consumer, protected_consumer, nvhe_confirm, protected_confirm in (
            (50, 900, 930, 1100, 1150),
            (70, 1400, 1500, 2000, 2100),
            (85, 2600, 3120, 3500, 4200),
        ):
            scenario = f"q3-rate{load}"
            rows += metric_rows(1, "nvhe", "rabbitmq", scenario, "consumer_p99", [nvhe_consumer] * 5, "us", False)
            rows += metric_rows(1, "protected", "rabbitmq", scenario, "consumer_p99", [protected_consumer] * 5, "us", False)
            rows += metric_rows(1, "nvhe", "rabbitmq", scenario, "confirm_p99", [nvhe_confirm] * 5, "us", False)
            rows += metric_rows(1, "protected", "rabbitmq", scenario, "confirm_p99", [protected_confirm] * 5, "us", False)
        data = mod.aggregate_rows(rows)

        with tempfile.TemporaryDirectory() as tmpdir:
            overview = Path(tmpdir) / "overview.svg"
            load = Path(tmpdir) / "load.svg"
            matrix = Path(tmpdir) / "matrix.svg"
            mod.write_application_overview(data, overview, source_label="fixture/metrics.csv")
            mod.write_rabbitmq_load_curve(data, load, source_label="fixture/metrics.csv")
            mod.write_pair_matrix(data, matrix, source_label="fixture/metrics.csv", expected_pairs=5)
            overview_svg = overview.read_text()
            load_svg = load.read_text()
            matrix_svg = matrix.read_text()

        self.assertIn("D3000 pKVM application penalty overview", overview_svg)
        self.assertIn("n=1 paired boot per shown metric", overview_svg)
        self.assertIn("Q3 85% consumer p99", overview_svg)
        self.assertIn("Geekbench suite wall time", overview_svg)
        self.assertIn("D3000 RabbitMQ: tail latency versus fixed offered load", load_svg)
        self.assertIn("85%: +20.0%", load_svg)
        self.assertIn("Publisher confirm p99", load_svg)
        self.assertIn("blank cells are incomplete pairs, not zeroes", matrix_svg)
        self.assertIn("Pair 5", matrix_svg)
        self.assertIn("+20.0%", matrix_svg)


if __name__ == "__main__":
    unittest.main()
