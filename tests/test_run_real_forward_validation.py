from pathlib import Path
import json
import sys
import tempfile
import unittest

import numpy as np


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from diagnose_real_pde_mismatch import RealCaseConfig, solve_real_boundary_forward
from run_real_forward_validation import run_manifest


class RealForwardValidationBatchTests(unittest.TestCase):
    def test_manifest_run_writes_case_and_summary_outputs(self):
        time_s = np.linspace(0.0, 5.0, 21)
        x_mm = np.linspace(0.0, 20.0, 11)
        initial_c = np.full(x_mm.shape, 25.0)
        left_c = 25.0 + 25.0 * (1.0 - np.exp(-time_s / 1.2))
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
            left_c,
            config,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_path = root / "case.npz"
            np.savez(
                dataset_path,
                xt_grid_c=observed_c,
                time_axis_sec=time_s,
                x_axis_mm=x_mm,
                boundary_temperature_c=left_c,
            )
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "defaults": {
                            "diameter_mm": 8.0,
                            "emissivity": 0.95,
                            "sigma_sb": 5.67e-8,
                            "conductivity_bounds": [50.0, 220.0],
                            "h_bounds": [0.0, 25.0],
                            "right_bc_modes": ["robin"],
                            "initial_frame_count": 1,
                            "max_time_s": 5.0,
                            "train_fraction": 0.7,
                            "fit_time_stride": 1,
                        },
                        "cases": [
                            {
                                "case_name": "synthetic_h59",
                                "material": "H59",
                                "dataset_path": str(dataset_path),
                                "rho": 8500.0,
                                "cp": 380.0,
                                "t_inf_c": 25.0,
                                "reference_k_w_mk": 110.0,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            output_dir = root / "outputs"
            summary = run_manifest(manifest_path, output_dir)

            self.assertEqual(len(summary), 1)
            self.assertTrue((output_dir / "synthetic_h59.json").exists())
            self.assertTrue((output_dir / "summary.csv").exists())
            self.assertAlmostEqual(
                summary[0]["conductivity_w_mk"],
                110.0,
                delta=5.0,
            )


if __name__ == "__main__":
    unittest.main()
