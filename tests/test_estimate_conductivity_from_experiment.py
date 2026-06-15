from pathlib import Path
import sys
import unittest

import numpy as np


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from diagnose_real_pde_mismatch import RealCaseConfig, solve_real_boundary_forward
from estimate_conductivity_from_experiment import estimate_heated_end_windows


class HeatedEndWindowEstimatorTests(unittest.TestCase):
    def test_recovers_conductivity_before_corrupted_support_region(self):
        time_s = np.linspace(0.0, 30.0, 121)
        x_mm = np.linspace(0.0, 100.0, 51)
        initial_c = np.full(x_mm.shape, 25.0)
        left_c = 25.0 + 45.0 * (1.0 - np.exp(-time_s / 4.0))
        config = RealCaseConfig(
            rho=2700.0,
            cp=900.0,
            conductivity=167.0,
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
        observed_c[:, x_mm >= 70.0] += 4.0

        result = estimate_heated_end_windows(
            time_s=time_s,
            x_mm=x_mm,
            observed_c=observed_c,
            rho=2700.0,
            cp=900.0,
            t_inf_c=25.0,
            expected_k_range=(130.0, 190.0),
            window_lengths_mm=(30.0, 40.0, 50.0, 60.0),
            fixed_h=10.0,
        )

        self.assertTrue(result["recommended_for_reporting"])
        self.assertAlmostEqual(
            result["selected"]["conductivity_w_mk"],
            167.0,
            delta=6.0,
        )
        self.assertTrue(all(row["window_end_mm"] < 70.0 for row in result["candidates"]))


if __name__ == "__main__":
    unittest.main()
