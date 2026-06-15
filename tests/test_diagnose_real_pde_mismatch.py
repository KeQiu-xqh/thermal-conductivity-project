from pathlib import Path
import sys
import unittest

import numpy as np


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from diagnose_real_pde_mismatch import (
    RealCaseConfig,
    compute_residual_metrics,
    solve_real_boundary_forward,
    solve_real_boundary_forward_implicit,
)


class RealBoundaryForwardTests(unittest.TestCase):
    def test_solver_preserves_measured_left_boundary_and_initial_profile(self):
        time_s = np.linspace(0.0, 2.0, 9)
        x_mm = np.linspace(0.0, 12.0, 7)
        initial_c = np.linspace(40.0, 25.0, x_mm.size)
        left_c = 40.0 + 5.0 * time_s
        config = RealCaseConfig(
            rho=8500.0,
            cp=380.0,
            conductivity=110.0,
            h=10.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            right_bc_mode="none",
        )

        predicted = solve_real_boundary_forward(
            time_s=time_s,
            x_mm=x_mm,
            initial_temperature_c=initial_c,
            left_boundary_c=left_c,
            config=config,
        )

        np.testing.assert_allclose(predicted[:, 0], left_c, atol=1e-6)
        np.testing.assert_allclose(predicted[0], initial_c, atol=1e-6)
        self.assertTrue(np.isfinite(predicted).all())

    def test_sparse_output_can_use_full_resolution_left_boundary(self):
        full_time_s = np.linspace(0.0, 4.0, 41)
        sparse_indices = np.arange(0, full_time_s.size, 4)
        sparse_time_s = full_time_s[sparse_indices]
        x_mm = np.linspace(0.0, 12.0, 7)
        initial_c = np.linspace(35.0, 25.0, x_mm.size)
        full_left_c = 35.0 + 20.0 * (1.0 - np.exp(-full_time_s / 0.7))
        config = RealCaseConfig(
            rho=8500.0,
            cp=380.0,
            conductivity=110.0,
            h=10.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            right_bc_mode="robin",
        )

        full_prediction = solve_real_boundary_forward(
            full_time_s,
            x_mm,
            initial_c,
            full_left_c,
            config,
        )
        sparse_prediction = solve_real_boundary_forward(
            sparse_time_s,
            x_mm,
            initial_c,
            full_left_c,
            config,
            left_boundary_time_s=full_time_s,
        )

        np.testing.assert_allclose(
            sparse_prediction,
            full_prediction[sparse_indices],
            atol=2.0e-4,
        )

    def test_implicit_solver_matches_bdf_reference(self):
        time_s = np.linspace(0.0, 8.0, 81)
        x_mm = np.linspace(0.0, 30.0, 21)
        initial_c = np.linspace(32.0, 25.0, x_mm.size)
        left_c = 32.0 + 35.0 * (1.0 - np.exp(-time_s / 1.5))
        config = RealCaseConfig(
            rho=8500.0,
            cp=380.0,
            conductivity=110.0,
            h=8.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            right_bc_mode="robin",
        )

        reference = solve_real_boundary_forward(
            time_s,
            x_mm,
            initial_c,
            left_c,
            config,
        )
        implicit = solve_real_boundary_forward_implicit(
            time_s,
            x_mm,
            initial_c,
            left_c,
            config,
            substeps=4,
        )

        self.assertLess(float(np.sqrt(np.mean((reference - implicit) ** 2))), 0.05)

    def test_implicit_solver_preserves_measured_right_boundary(self):
        time_s = np.linspace(0.0, 4.0, 21)
        x_mm = np.linspace(0.0, 20.0, 11)
        initial_c = np.linspace(35.0, 25.0, x_mm.size)
        left_c = 35.0 + 10.0 * time_s
        right_c = 25.0 + 2.0 * time_s
        config = RealCaseConfig(
            rho=8500.0,
            cp=380.0,
            conductivity=110.0,
            h=8.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            right_bc_mode="measured",
        )

        predicted = solve_real_boundary_forward_implicit(
            time_s,
            x_mm,
            initial_c,
            left_c,
            config,
            right_boundary_c=right_c,
        )

        np.testing.assert_allclose(predicted[:, 0], left_c, atol=1.0e-8)
        np.testing.assert_allclose(predicted[:, -1], right_c, atol=1.0e-8)


class ResidualMetricTests(unittest.TestCase):
    def test_metrics_identify_far_end_bias(self):
        observed = np.zeros((5, 6), dtype=np.float64)
        predicted = np.zeros_like(observed)
        observed[:, -2:] = 4.0

        metrics = compute_residual_metrics(observed, predicted)

        self.assertGreater(metrics["far_rmse_c"], metrics["near_rmse_c"])
        self.assertGreater(metrics["far_mean_bias_c"], 0.0)
        self.assertEqual(len(metrics["rmse_by_x_c"]), observed.shape[1])
        self.assertEqual(len(metrics["rmse_by_time_c"]), observed.shape[0])


if __name__ == "__main__":
    unittest.main()
