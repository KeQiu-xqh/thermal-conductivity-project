from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from train_pinn_1d import (  # type: ignore
    build_initial_profile_target,
    build_boundary_interpolator,
    compute_right_boundary_loss,
    convert_alpha_to_conductivity,
    estimate_mm_per_px,
    load_xt_dataset,
    normalize_dataset,
    pde_residual_physical,
    sample_collocation_points,
    SimplePINN,
)


class LoadXtDatasetTests(unittest.TestCase):
    def test_load_xt_dataset_reads_grid_and_boundary_metadata(self):
        xt_grid = np.array(
            [
                [30.0, 28.0, 26.0],
                [32.0, 29.0, 27.0],
                [34.0, 30.0, 28.0],
            ],
            dtype=np.float32,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "toy_xt.npz"
            np.savez(
                path,
                xt_grid_c=xt_grid,
                time_axis_sec=np.array([0.0, 1.0, 2.0], dtype=np.float32),
                x_axis_heat_px=np.array([0.0, 1.0, 2.0], dtype=np.float32),
                x_axis_mm=np.array([0.0, 2.0, 4.0], dtype=np.float32),
                boundary_temperature_c=np.array([30.0, 32.0, 34.0], dtype=np.float32),
                far_end_temperature_c=np.array([26.0, 27.0, 28.0], dtype=np.float32),
            )

            dataset = load_xt_dataset(path)

        self.assertEqual(dataset["xt_grid_c"].shape, (3, 3))
        self.assertTrue(np.allclose(dataset["temperature_c"], xt_grid.reshape(-1, 1)))
        self.assertEqual(dataset["inputs_xt"].shape, (9, 2))
        self.assertEqual(dataset["time_axis_sec"].tolist(), [0.0, 1.0, 2.0])
        self.assertEqual(dataset["boundary_temperature_c"].tolist(), [30.0, 32.0, 34.0])
        self.assertEqual(dataset["x_axis_mm"].tolist(), [0.0, 2.0, 4.0])


class BoundaryInterpolatorTests(unittest.TestCase):
    def test_boundary_interpolator_matches_linear_series(self):
        times = np.array([0.0, 1.0, 2.0], dtype=np.float32)
        values = np.array([30.0, 32.0, 36.0], dtype=np.float32)
        interp = build_boundary_interpolator(times, values)

        query = np.array([0.5, 1.5], dtype=np.float32)
        result = interp(query)

        self.assertTrue(np.allclose(result, np.array([31.0, 34.0], dtype=np.float32)))


class PinnSmokeTests(unittest.TestCase):
    def test_model_forward_and_collocation_sampling_have_expected_shapes(self):
        model = SimplePINN(hidden_width=8, hidden_depth=2)
        coords = np.array([[0.0, 0.0], [1.0, 2.0]], dtype=np.float32)

        import torch

        coords_tensor = torch.tensor(coords, dtype=torch.float32)
        pred = model(coords_tensor)
        collocation = sample_collocation_points(
            count=16,
            time_min=0.0,
            time_max=2.0,
            x_min=0.0,
            x_max=5.0,
            device=coords_tensor.device,
        )

        self.assertEqual(tuple(pred.shape), (2, 1))
        self.assertEqual(tuple(collocation.shape), (16, 2))
        self.assertTrue(torch.isfinite(pred).all())


class PhysicalConversionTests(unittest.TestCase):
    def test_mm_per_px_estimate_combines_length_and_diameter(self):
        calibration = estimate_mm_per_px(
            roi_width_px=73,
            roi_height_px=4,
            visible_length_mm=136.0,
            diameter_mm=8.0,
        )
        self.assertAlmostEqual(calibration["length_based_mm_per_px"], 136.0 / 73.0)
        self.assertAlmostEqual(calibration["diameter_based_mm_per_px"], 2.0)
        self.assertGreater(calibration["combined_mm_per_px"], 1.9)

    def test_alpha_to_conductivity_matches_manual_formula(self):
        conductivity = convert_alpha_to_conductivity(
            alpha_m2_s=2.0e-5,
            rho_kg_m3=2700.0,
            cp_j_kgk=900.0,
        )
        self.assertAlmostEqual(conductivity, 2.0e-5 * 2700.0 * 900.0)

    def test_pde_residual_zero_at_ambient_equilibrium(self):
        residual = pde_residual_physical(
            temperature_c=25.0,
            temperature_t_c_s=0.0,
            temperature_xx_c_m2=0.0,
            alpha_m2_s=1.0e-5,
            h_w_m2k=10.0,
            rho_kg_m3=2700.0,
            cp_j_kgk=900.0,
            diameter_m=0.008,
            emissivity=0.95,
            sigma_sb=5.67e-8,
            t_inf_k=298.15,
        )
        self.assertAlmostEqual(residual, 0.0, places=10)


class ConstraintModeTests(unittest.TestCase):
    def test_measured_initial_profile_uses_early_frame_average(self):
        dataset = {
            "xt_grid_c": np.array(
                [
                    [30.0, 31.0, 32.0],
                    [36.0, 37.0, 38.0],
                    [50.0, 51.0, 52.0],
                ],
                dtype=np.float32,
            ),
            "u_mean": 40.0,
            "u_std": 10.0,
        }

        measured = build_initial_profile_target(
            dataset,
            initial_mode="measured",
            t_inf_c=25.0,
            measured_frame_count=2,
        )
        ambient = build_initial_profile_target(
            dataset,
            initial_mode="ambient",
            t_inf_c=25.0,
            measured_frame_count=2,
        )

        self.assertTrue(np.allclose(measured, np.array([[-0.7], [-0.6], [-0.5]], dtype=np.float32)))
        self.assertTrue(np.allclose(ambient, np.full((3, 1), -1.5, dtype=np.float32)))

    def test_right_boundary_loss_can_be_disabled_for_visible_subdomain(self):
        class Args:
            visible_length_mm = 136.0
            diameter_mm = 8.0
            calibration_mode = "diameter"
            mm_per_px = None
            t_inf_c = 25.0
            rho = 2700.0
            cp = 900.0
            emissivity = 0.95
            sigma_sb = 5.67e-8
            right_bc_mode = "none"

        xt_grid = np.array(
            [
                [30.0, 29.0, 28.0],
                [31.0, 30.0, 29.0],
            ],
            dtype=np.float32,
        )
        dataset = normalize_dataset(
            {
                "xt_grid_c": xt_grid,
                "inputs_xt": np.array(
                    [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]],
                    dtype=np.float32,
                ),
                "temperature_c": xt_grid.reshape(-1, 1),
                "time_axis_sec": np.array([0.0, 1.0], dtype=np.float32),
                "x_axis_heat_px": np.array([0.0, 1.0, 2.0], dtype=np.float32),
                "boundary_temperature_c": np.array([30.0, 31.0], dtype=np.float32),
                "far_end_temperature_c": np.array([28.0, 29.0], dtype=np.float32),
                "x_axis_mm": np.array([0.0, 2.0, 4.0], dtype=np.float32),
            },
            Args(),
        )
        model = SimplePINN(hidden_width=8, hidden_depth=2)

        import torch

        loss = compute_right_boundary_loss(model, sample_count=8, dataset=dataset, args=Args(), device=torch.device("cpu"))
        self.assertEqual(float(loss.item()), 0.0)


if __name__ == "__main__":
    unittest.main()
