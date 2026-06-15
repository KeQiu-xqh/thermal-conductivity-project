from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from run_synthetic_pinn_sweep import SweepTask, expand_coarse_tasks, load_config


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


if __name__ == "__main__":
    unittest.main()
