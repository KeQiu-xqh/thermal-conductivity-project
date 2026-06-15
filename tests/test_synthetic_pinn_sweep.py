from pathlib import Path
import json
import sys
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
