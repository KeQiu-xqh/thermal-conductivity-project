import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from tune_synthetic_pinn_hyperparameters import (  # noqa: E402
    build_variant_config,
    rank_variants,
    representative_tasks,
)


class HyperparameterVariantTests(unittest.TestCase):
    def setUp(self):
        self.base = {
            "materials": {
                "h59": {"rho": 8500.0, "cp": 380.0, "true_k": 100.0},
                "6061": {"rho": 2700.0, "cp": 900.0, "true_k": 160.0},
            },
            "coarse_scan": {"data_seed": 1003},
            "pinn": {
                "epochs": 1000,
                "hidden_width": 64,
                "hidden_depth": 4,
                "collocation_points": 1024,
            },
        }

    def test_representative_tasks_cover_both_materials_and_difficult_window(self):
        tasks = representative_tasks(self.base)
        identities = {
            (task["material"], task["time_length_s"], task["space_length_mm"], task["noise_sigma_c"])
            for task in tasks
        }
        self.assertIn(("h59", 60.0, 50.0, 1.0), identities)
        self.assertIn(("6061", 60.0, 70.0, 1.0), identities)
        self.assertIn(("h59", 120.0, 70.0, 0.0), identities)
        self.assertIn(("6061", 120.0, 70.0, 0.0), identities)

    def test_representative_tasks_expand_requested_pinn_seeds(self):
        tasks = representative_tasks(self.base, pinn_seeds=[42, 43, 44])
        self.assertEqual(len(tasks), 12)
        self.assertEqual({task["pinn_seed"] for task in tasks}, {42, 43, 44})

    def test_build_variant_config_changes_only_requested_pinn_fields(self):
        variant = build_variant_config(
            self.base,
            "collocation_2048",
            {"collocation_points": 2048},
        )
        self.assertEqual(variant["pinn"]["collocation_points"], 2048)
        self.assertEqual(variant["pinn"]["hidden_width"], 64)
        self.assertEqual(self.base["pinn"]["collocation_points"], 1024)
        self.assertEqual(variant["tuning"]["variant_name"], "collocation_2048")


class HyperparameterRankingTests(unittest.TestCase):
    def test_rank_variants_prefers_lowest_cost_once_accuracy_gate_is_met(self):
        summaries = [
            {
                "variant": "expensive",
                "completed_cases": 4,
                "expected_cases": 4,
                "stable_cases": 4,
                "median_k_relative_error": 0.002,
                "max_k_relative_error": 0.005,
                "estimated_cost": 3.0,
            },
            {
                "variant": "efficient",
                "completed_cases": 4,
                "expected_cases": 4,
                "stable_cases": 4,
                "median_k_relative_error": 0.006,
                "max_k_relative_error": 0.012,
                "estimated_cost": 1.0,
            },
        ]
        ranked = rank_variants(summaries)
        self.assertEqual(ranked[0]["variant"], "efficient")
        self.assertTrue(ranked[0]["meets_accuracy_gate"])

    def test_rank_variants_prefers_stable_accurate_lower_cost_variant(self):
        summaries = [
            {
                "variant": "large",
                "completed_cases": 4,
                "stable_cases": 4,
                "median_k_relative_error": 0.01,
                "max_k_relative_error": 0.03,
                "estimated_cost": 2.0,
            },
            {
                "variant": "compact",
                "completed_cases": 4,
                "stable_cases": 4,
                "median_k_relative_error": 0.012,
                "max_k_relative_error": 0.03,
                "estimated_cost": 1.0,
            },
            {
                "variant": "unstable",
                "completed_cases": 4,
                "stable_cases": 3,
                "median_k_relative_error": 0.001,
                "max_k_relative_error": 0.01,
                "estimated_cost": 0.5,
            },
        ]
        ranked = rank_variants(summaries)
        self.assertEqual(ranked[0]["variant"], "compact")
        self.assertEqual(ranked[-1]["variant"], "unstable")

    def test_rank_variants_places_incomplete_runs_last(self):
        summaries = [
            {
                "variant": "complete",
                "completed_cases": 4,
                "expected_cases": 4,
                "stable_cases": 3,
                "median_k_relative_error": 0.02,
                "max_k_relative_error": 0.04,
                "estimated_cost": 1.0,
            },
            {
                "variant": "incomplete",
                "completed_cases": 1,
                "expected_cases": 4,
                "stable_cases": 1,
                "median_k_relative_error": 0.001,
                "max_k_relative_error": 0.001,
                "estimated_cost": 0.5,
            },
        ]
        ranked = rank_variants(summaries)
        self.assertEqual(ranked[0]["variant"], "complete")
        self.assertEqual(ranked[-1]["variant"], "incomplete")


if __name__ == "__main__":
    unittest.main()
