from pathlib import Path
import json
import sys
import tempfile
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from run_synthetic_pinn_sweep import (
    SweepTask,
    build_pinn_command,
    decide_task_action,
    expand_coarse_tasks,
    load_config,
    write_status,
)
from analyze_synthetic_sweep import analyze_case, select_blind_estimate, select_refinement_cases


class SweepConfigTests(unittest.TestCase):
    def test_default_config_expands_to_300_coarse_tasks(self):
        config = load_config(PROJECT_ROOT / "configs" / "synthetic_pinn_h59_6061.json")
        tasks = expand_coarse_tasks(config)
        self.assertEqual(len(tasks), 300)
        self.assertEqual({task.material for task in tasks}, {"h59", "6061"})

    def test_task_id_is_stable_and_contains_both_seed_types(self):
        task = SweepTask("h59", 120.0, 70.0, 0.2, data_seed=1003, pinn_seed=42)
        self.assertEqual(task.task_id, task.task_id)
        self.assertIn("data1003", task.task_id)
        self.assertIn("pinn42", task.task_id)

    def test_config_loader_accepts_utf8_bom_from_windows_powershell(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "config.json"
            path.write_text('{"schema_version": 1}', encoding="utf-8-sig")
            self.assertEqual(load_config(path)["schema_version"], 1)


class SweepRunnerTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(PROJECT_ROOT / "configs" / "synthetic_pinn_h59_6061.json")
        self.task = SweepTask("h59", 120.0, 70.0, 0.2, 1003, 42)

    def test_command_uses_custom_material_and_never_passes_truth_range(self):
        command = build_pinn_command(self.task, self.config, Path("observations.npz"), "case")
        joined = " ".join(command)
        self.assertIn("--material-preset custom", joined)
        self.assertNotIn("--expected-k-min", joined)
        self.assertNotIn("--expected-k-max", joined)
        self.assertNotIn("true_k", joined)

    def test_completed_matching_task_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = Path(tmp_dir)
            summary = task_dir / "summary.json"
            summary.write_text(json.dumps({"ok": True}), encoding="utf-8")
            write_status(task_dir, "completed", config_hash="abc", summary_path=summary)
            self.assertEqual(decide_task_action(task_dir, "abc"), "skip")

    def test_hash_mismatch_creates_new_batch_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = Path(tmp_dir)
            write_status(task_dir, "completed", config_hash="old", summary_path=None)
            self.assertEqual(decide_task_action(task_dir, "new"), "new_batch")


class SweepAnalysisTests(unittest.TestCase):
    def test_rejected_summary_uses_final_estimate_but_marks_not_stable(self):
        summary = {
            "thermal_conductivity_w_mk": 80.0,
            "alpha_m2_s": 2.5e-5,
            "h_w_m2k": 10.0,
            "completed_steps": 2000,
            "temperature_mse_c2": 0.1,
            "quality_checks": {
                "enough_steps": True,
                "parameters_stable": False,
                "warnings": ["tail_parameters_not_stable"],
            },
            "best_physical": {"found": False},
        }
        source, *_ = select_blind_estimate(summary)
        self.assertEqual(source, "final")
        row = analyze_case(
            summary,
            {
                "material": "h59",
                "true_k": 100.0,
                "true_alpha": 100.0 / (8500.0 * 380.0),
                "true_h": 10.0,
                "time_length_s": 60.0,
                "space_length_mm": 50.0,
                "noise_sigma_c": 0.2,
                "data_seed": 1003,
            },
            np.array([[25.0, 25.0], [80.0, 40.0]]),
        )
        self.assertFalse(row["blind_stability_pass"])

    def test_error_and_dimensionless_metrics(self):
        summary = {
            "thermal_conductivity_w_mk": 110.0,
            "alpha_m2_s": 110.0 / (8500.0 * 380.0),
            "h_w_m2k": 11.0,
            "completed_steps": 2000,
            "temperature_mse_c2": 0.1,
            "quality_checks": {"enough_steps": True, "parameters_stable": True, "warnings": []},
            "best_physical": {"found": False},
        }
        truth = {
            "material": "h59",
            "true_k": 100.0,
            "true_alpha": 100.0 / (8500.0 * 380.0),
            "true_h": 10.0,
            "time_length_s": 60.0,
            "space_length_mm": 50.0,
            "noise_sigma_c": 0.2,
            "data_seed": 1003,
        }
        row = analyze_case(summary, truth, np.array([[25.0, 25.0], [80.0, 40.0]]))
        self.assertAlmostEqual(row["k_relative_error"], 0.10)
        self.assertGreater(row["fourier_number"], 0.0)
        self.assertGreater(row["snr"], 0.0)

    def test_refinement_includes_threshold_and_best_cases(self):
        rows = [
            {
                "material": "h59",
                "time_length_s": 60.0,
                "space_length_mm": 50.0,
                "noise_sigma_c": 0.2,
                "data_seed": 1003,
                "pinn_seed": 42,
                "k_relative_error": 0.11,
                "blind_stability_pass": True,
            },
            {
                "material": "6061",
                "time_length_s": 120.0,
                "space_length_mm": 70.0,
                "noise_sigma_c": 0.1,
                "data_seed": 1003,
                "pinn_seed": 42,
                "k_relative_error": 0.02,
                "blind_stability_pass": True,
            },
        ]
        selected = select_refinement_cases(rows, self.config_for_refinement())
        reasons = {
            reason
            for item in selected
            for reason in item["selection_reason"].split("|")
        }
        self.assertIn("near_10_percent", reasons)
        self.assertIn("best_case", reasons)

    @staticmethod
    def config_for_refinement():
        return {
            "refinement": {
                "pinn_seeds": [42, 43, 44, 45, 46],
                "near_error_threshold_margin": 0.03,
                "best_cases_per_material": 1,
            }
        }


if __name__ == "__main__":
    unittest.main()
