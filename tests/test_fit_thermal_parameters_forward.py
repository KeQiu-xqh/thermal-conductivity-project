from pathlib import Path
import sys
import tempfile
import unittest
import json

import numpy as np


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from diagnose_real_pde_mismatch import RealCaseConfig, solve_real_boundary_forward
from fit_thermal_parameters_forward import fit_dataset_file, fit_forward_parameters


class ForwardParameterFitTests(unittest.TestCase):
    def test_recovers_conductivity_from_exact_synthetic_field(self):
        time_s = np.linspace(0.0, 20.0, 61)
        x_mm = np.linspace(0.0, 45.0, 24)
        initial_c = np.full(x_mm.shape, 25.0)
        left_boundary_c = 25.0 + 45.0 * (1.0 - np.exp(-time_s / 4.0))
        true_config = RealCaseConfig(
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
        observed_c = solve_real_boundary_forward(
            time_s,
            x_mm,
            initial_c,
            left_boundary_c,
            true_config,
        )

        result = fit_forward_parameters(
            time_s=time_s,
            x_mm=x_mm,
            observed_c=observed_c,
            initial_temperature_c=initial_c,
            left_boundary_c=left_boundary_c,
            rho=8500.0,
            cp=380.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            conductivity_bounds=(50.0, 220.0),
            h_bounds=(0.0, 25.0),
            right_bc_modes=("none", "robin"),
            train_fraction=0.7,
            fit_time_stride=1,
        )

        self.assertEqual(result["right_bc_mode"], "robin")
        self.assertAlmostEqual(result["conductivity_w_mk"], 110.0, delta=3.0)
        self.assertAlmostEqual(result["h_w_m2k"], 8.0, delta=2.0)
        self.assertLess(result["train_rmse_c"], 0.05)
        self.assertLess(result["validation_rmse_c"], 0.05)
        self.assertLess(result["conductivity_std_w_mk"], 2.0)
        self.assertNotIn("conductivity_at_bound", result["identifiability_warnings"])
        self.assertNotIn("h_at_bound", result["identifiability_warnings"])

    def test_dataset_file_fit_writes_reproducible_json(self):
        time_s = np.linspace(0.0, 6.0, 25)
        x_mm = np.linspace(0.0, 24.0, 13)
        initial_c = np.full(x_mm.shape, 25.0)
        left_boundary_c = 25.0 + 30.0 * (1.0 - np.exp(-time_s / 1.5))
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
        observed_c = solve_real_boundary_forward(
            time_s,
            x_mm,
            initial_c,
            left_boundary_c,
            config,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "synthetic.npz"
            output_path = Path(temp_dir) / "fit.json"
            np.savez(
                dataset_path,
                xt_grid_c=observed_c,
                time_axis_sec=time_s,
                x_axis_mm=x_mm,
                boundary_temperature_c=left_boundary_c,
            )

            result = fit_dataset_file(
                dataset_path=dataset_path,
                output_json_path=output_path,
                rho=8500.0,
                cp=380.0,
                diameter_mm=8.0,
                emissivity=0.95,
                sigma_sb=5.67e-8,
                t_inf_c=25.0,
                conductivity_bounds=(50.0, 220.0),
                h_bounds=(0.0, 25.0),
                right_bc_modes=("robin",),
                initial_frame_count=1,
                max_time_s=6.0,
                train_fraction=0.7,
                fit_time_stride=1,
            )

            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertAlmostEqual(result["conductivity_w_mk"], 110.0, delta=4.0)
            self.assertEqual(saved["dataset_path"], str(dataset_path.resolve()))
            self.assertEqual(saved["sample_count"]["time"], time_s.size)

    def test_robust_loss_resists_localized_support_temperature_bias(self):
        time_s = np.linspace(0.0, 12.0, 49)
        x_mm = np.linspace(0.0, 48.0, 25)
        initial_c = np.full(x_mm.shape, 25.0)
        left_boundary_c = 25.0 + 40.0 * (1.0 - np.exp(-time_s / 2.5))
        config = RealCaseConfig(
            rho=2700.0,
            cp=900.0,
            conductivity=167.0,
            h=8.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            right_bc_mode="robin",
        )
        observed_c = solve_real_boundary_forward(
            time_s,
            x_mm,
            initial_c,
            left_boundary_c,
            config,
        )
        corrupted_c = observed_c.copy()
        corrupted_c[:, 10:14] += 3.0
        corrupted_c[:, -3:] -= 3.0

        result = fit_forward_parameters(
            time_s=time_s,
            x_mm=x_mm,
            observed_c=corrupted_c,
            initial_temperature_c=initial_c,
            left_boundary_c=left_boundary_c,
            rho=2700.0,
            cp=900.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            conductivity_bounds=(80.0, 300.0),
            h_bounds=(0.0, 25.0),
            right_bc_modes=("robin",),
            train_fraction=0.7,
            robust_loss="soft_l1",
            robust_f_scale_c=0.3,
        )

        self.assertAlmostEqual(result["conductivity_w_mk"], 167.0, delta=10.0)

    def test_measured_right_boundary_recovers_internal_subdomain_conductivity(self):
        time_s = np.linspace(0.0, 15.0, 61)
        x_mm = np.linspace(0.0, 60.0, 31)
        initial_c = np.full(x_mm.shape, 25.0)
        left_boundary_c = 25.0 + 40.0 * (1.0 - np.exp(-time_s / 3.0))
        config = RealCaseConfig(
            rho=2700.0,
            cp=900.0,
            conductivity=167.0,
            h=8.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            right_bc_mode="robin",
        )
        full_field = solve_real_boundary_forward(
            time_s,
            x_mm,
            initial_c,
            left_boundary_c,
            config,
        )
        subdomain = full_field[:, 5:24]
        subdomain_x_mm = x_mm[5:24] - x_mm[5]
        subdomain_initial_c = subdomain[0]

        result = fit_forward_parameters(
            time_s=time_s,
            x_mm=subdomain_x_mm,
            observed_c=subdomain,
            initial_temperature_c=subdomain_initial_c,
            left_boundary_c=subdomain[:, 0],
            rho=2700.0,
            cp=900.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            conductivity_bounds=(80.0, 300.0),
            h_bounds=(0.0, 25.0),
            right_bc_modes=("measured",),
            train_fraction=0.7,
        )

        self.assertAlmostEqual(result["conductivity_w_mk"], 167.0, delta=5.0)

    def test_fixed_h_fits_only_conductivity(self):
        time_s = np.linspace(0.0, 10.0, 41)
        x_mm = np.linspace(0.0, 40.0, 21)
        initial_c = np.full(x_mm.shape, 25.0)
        left_c = 25.0 + 35.0 * (1.0 - np.exp(-time_s / 2.0))
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
        observed_c = solve_real_boundary_forward(
            time_s,
            x_mm,
            initial_c,
            left_c,
            config,
        )

        result = fit_forward_parameters(
            time_s=time_s,
            x_mm=x_mm,
            observed_c=observed_c,
            initial_temperature_c=initial_c,
            left_boundary_c=left_c,
            rho=8500.0,
            cp=380.0,
            diameter_mm=8.0,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_c=25.0,
            conductivity_bounds=(50.0, 220.0),
            h_bounds=(0.0, 30.0),
            right_bc_modes=("robin",),
            train_fraction=0.7,
            fixed_h=10.0,
        )

        self.assertAlmostEqual(result["conductivity_w_mk"], 110.0, delta=3.0)
        self.assertEqual(result["h_w_m2k"], 10.0)
        self.assertEqual(result["h_std_w_m2k"], 0.0)
        self.assertNotIn("h_at_bound", result["identifiability_warnings"])


if __name__ == "__main__":
    unittest.main()
