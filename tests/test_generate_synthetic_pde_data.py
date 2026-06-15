from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from generate_synthetic_pde_data import (
    MaterialConfig,
    PhysicsConfig,
    SamplingConfig,
    build_observation_dataset,
    left_boundary_c,
    solve_forward_field,
    write_synthetic_case,
)
from train_pinn_1d import load_xt_dataset


def make_material():
    return MaterialConfig("h59", rho=8500.0, cp=380.0, true_k=100.0)


def make_physics():
    return PhysicsConfig(
        true_h=10.0,
        diameter_mm=8.0,
        emissivity=0.95,
        sigma_sb=5.67e-8,
        t_inf_c=25.0,
        left_delta_t_c=70.0,
        left_tau_s=20.0,
        domain_length_mm=30.0,
    )


def make_sampling(dx_mm=1.5):
    return SamplingConfig(
        internal_dx_mm=dx_mm,
        observation_dx_mm=1.5,
        observation_fps=6.0,
        rtol=1e-7,
        atol=1e-9,
    )


class ForwardSolverTests(unittest.TestCase):
    def test_material_alpha_is_derived_from_true_k(self):
        material = make_material()
        self.assertAlmostEqual(material.alpha, 100.0 / (8500.0 * 380.0))

    def test_left_boundary_starts_at_ambient_and_rises_smoothly(self):
        physics = make_physics()
        self.assertAlmostEqual(float(left_boundary_c(0.0, physics)), physics.t_inf_c)
        self.assertGreater(float(left_boundary_c(60.0, physics)), float(left_boundary_c(10.0, physics)))

    def test_forward_solution_is_finite_and_has_expected_shape(self):
        solution = solve_forward_field(make_material(), make_physics(), make_sampling(), 10.0)
        self.assertEqual(solution.temperature_c.shape, (solution.time_s.size, solution.x_m.size))
        self.assertTrue(np.isfinite(solution.temperature_c).all())
        np.testing.assert_allclose(
            solution.temperature_c[:, 0],
            left_boundary_c(solution.time_s, make_physics()),
            atol=1e-7,
        )

    def test_refined_grid_changes_observations_by_less_than_point_one_c(self):
        coarse = solve_forward_field(make_material(), make_physics(), make_sampling(1.5), 10.0)
        fine = solve_forward_field(make_material(), make_physics(), make_sampling(0.75), 10.0)
        coarse_obs = build_observation_dataset(coarse, 10.0, 30.0, 0.0, 1003, 1.5, 6.0)
        fine_obs = build_observation_dataset(fine, 10.0, 30.0, 0.0, 1003, 1.5, 6.0)
        self.assertLess(float(np.max(np.abs(coarse_obs["clean_xt_grid_c"] - fine_obs["clean_xt_grid_c"]))), 0.1)


class SyntheticExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.solution = solve_forward_field(make_material(), make_physics(), make_sampling(0.75), 10.0)

    def test_same_seed_produces_identical_noisy_grid(self):
        first = build_observation_dataset(self.solution, 10.0, 30.0, 0.2, 1003, 1.5, 6.0)
        second = build_observation_dataset(self.solution, 10.0, 30.0, 0.2, 1003, 1.5, 6.0)
        np.testing.assert_array_equal(first["xt_grid_c"], second["xt_grid_c"])

    def test_training_npz_contains_no_true_parameter_keys_and_loads_in_pinn(self):
        dataset = build_observation_dataset(self.solution, 10.0, 30.0, 0.2, 1003, 1.5, 6.0)
        truth = {
            "case_id": "h59_t10_l30_n0p2_data1003",
            "material": "h59",
            "true_k": 100.0,
            "true_alpha": make_material().alpha,
            "true_h": 10.0,
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            observation_path, truth_path = write_synthetic_case(Path(tmp_dir), dataset, truth)
            with np.load(observation_path) as data:
                self.assertFalse(any(key.startswith("true_") for key in data.files))
                self.assertNotIn("clean_xt_grid_c", data.files)
            loaded = load_xt_dataset(observation_path)
            self.assertEqual(loaded["xt_grid_c"].shape, dataset["xt_grid_c"].shape)
            self.assertTrue(truth_path.exists())


if __name__ == "__main__":
    unittest.main()
