from pathlib import Path
import sys
import unittest

import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import train_pinn_1d  # type: ignore
from train_pinn_1d import (  # type: ignore
    SimplePINN,
    apply_material_preset,
    apply_training_preset,
    build_quality_checks,
    compute_training_losses,
    normalize_dataset,
    prepare_training_context,
    sample_training_loss_points,
    train_model,
)


class BaseArgs:
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
    initial_mode = "measured"
    measured_initial_frame_count = 1
    lr = 1.0e-3
    epochs = 1
    collocation_points = 20
    data_weight = 1.0
    pde_weight = 0.1
    bc_weight = 0.1
    ic_weight = 0.1
    lr_scheduler = "none"
    lr_factor = 0.5
    lr_patience = 0
    min_lr = 1.0e-6
    lbfgs_steps = 0
    lbfgs_lr = 0.1
    lbfgs_history_size = 5
    lbfgs_line_search = "none"
    early_stop_window = 0
    early_stop_loss_rel_tol = 1.0e-4
    early_stop_param_rel_tol = 5.0e-4
    data_batch_size = 0
    pde_sampling = "uniform"
    pde_hot_x_max = 0.2
    pde_early_t_max = 0.3
    data_weighting = "none"
    data_weighting_lambda = 1.0
    data_weighting_temp_scale_c = 10.0
    data_weighting_max_extra = 4.0
    training_preset = "none"
    material_preset = "custom"
    expected_k_min = None
    expected_k_max = None
    convergence_tail_steps = 300
    min_quality_steps = 1000
    max_alpha_tail_rel_range = 0.05
    max_h_tail_rel_range = 0.05


def make_dataset(args=BaseArgs):
    xt_grid = np.array(
        [
            [30.0, 29.0, 28.0, 27.0],
            [35.0, 32.0, 29.0, 27.5],
            [45.0, 37.0, 31.0, 28.0],
        ],
        dtype=np.float32,
    )
    return normalize_dataset(
        {
            "xt_grid_c": xt_grid,
            "inputs_xt": np.array(
                [
                    [0.0, 0.0],
                    [1.0, 0.0],
                    [2.0, 0.0],
                    [3.0, 0.0],
                    [0.0, 1.0],
                    [1.0, 1.0],
                    [2.0, 1.0],
                    [3.0, 1.0],
                    [0.0, 2.0],
                    [1.0, 2.0],
                    [2.0, 2.0],
                    [3.0, 2.0],
                ],
                dtype=np.float32,
            ),
            "temperature_c": xt_grid.reshape(-1, 1),
            "time_axis_sec": np.array([0.0, 1.0, 2.0], dtype=np.float32),
            "x_axis_heat_px": np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float32),
            "boundary_temperature_c": np.array([30.0, 35.0, 45.0], dtype=np.float32),
            "far_end_temperature_c": np.array([27.0, 27.5, 28.0], dtype=np.float32),
            "x_axis_mm": np.array([0.0, 2.0, 4.0, 6.0], dtype=np.float32),
        },
        args,
    )


class SamplingControlTests(unittest.TestCase):
    def test_data_batch_size_zero_keeps_full_data_loss(self):
        dataset = make_dataset()
        context = prepare_training_context(dataset, BaseArgs(), torch.device("cpu"))
        loss_points = sample_training_loss_points(BaseArgs(), torch.device("cpu"), context)

        self.assertIsNone(loss_points["data_indices"])

        model = SimplePINN(hidden_width=8, hidden_depth=2)
        full_losses = compute_training_losses(model, dataset, BaseArgs(), torch.device("cpu"), context)
        sampled_losses = compute_training_losses(
            model,
            dataset,
            BaseArgs(),
            torch.device("cpu"),
            context,
            loss_points=loss_points,
        )

        self.assertAlmostEqual(float(full_losses[1].item()), float(sampled_losses[1].item()), places=7)

    def test_data_batch_size_samples_requested_count_without_exceeding_data(self):
        class Args(BaseArgs):
            data_batch_size = 5

        dataset = make_dataset(Args())
        context = prepare_training_context(dataset, Args(), torch.device("cpu"))
        loss_points = sample_training_loss_points(Args(), torch.device("cpu"), context)

        self.assertEqual(tuple(loss_points["data_indices"].shape), (5,))
        self.assertLess(int(loss_points["data_indices"].max().item()), context["coords"].shape[0])

    def test_mixed_pde_sampling_uses_global_hot_end_and_early_time_regions(self):
        class Args(BaseArgs):
            collocation_points = 100
            pde_sampling = "mixed"
            pde_hot_x_max = 0.2
            pde_early_t_max = 0.3

        loss_points = sample_training_loss_points(Args(), torch.device("cpu"))
        collocation = loss_points["collocation"]

        self.assertEqual(tuple(collocation.shape), (100, 2))
        self.assertTrue(torch.all(collocation[:70, 0] >= 0.0))
        self.assertTrue(torch.all(collocation[:70, 0] <= 1.0))
        self.assertTrue(torch.all(collocation[70:90, 0] <= 0.2))
        self.assertTrue(torch.all(collocation[90:, 1] <= 0.3))


class TrainingPresetTests(unittest.TestCase):
    def test_stable_preset_enables_only_large_data_minibatch(self):
        class Args(BaseArgs):
            training_preset = "stable"

        args = apply_training_preset(Args())

        self.assertEqual(args.data_batch_size, 16384)
        self.assertEqual(args.pde_sampling, "uniform")
        self.assertEqual(args.data_weighting, "none")

    def test_experimental_preset_keeps_mixed_sampling_and_data_weighting(self):
        class Args(BaseArgs):
            training_preset = "experimental"

        args = apply_training_preset(Args())

        self.assertEqual(args.data_batch_size, 16384)
        self.assertEqual(args.pde_sampling, "mixed")
        self.assertEqual(args.data_weighting, "delta-initial")


class MaterialPresetTests(unittest.TestCase):
    def test_h59_material_preset_sets_properties_and_expected_range(self):
        class Args(BaseArgs):
            material_preset = "h59"

        args = apply_material_preset(Args())

        self.assertEqual(args.rho, 8500.0)
        self.assertEqual(args.cp, 380.0)
        self.assertEqual(args.expected_k_min, 80.0)
        self.assertEqual(args.expected_k_max, 120.0)

    def test_explicit_expected_range_overrides_material_default(self):
        class Args(BaseArgs):
            material_preset = "h59"
            expected_k_min = 90.0
            expected_k_max = 105.0

        args = apply_material_preset(Args())

        self.assertEqual(args.expected_k_min, 90.0)
        self.assertEqual(args.expected_k_max, 105.0)


class QualityCheckTests(unittest.TestCase):
    def test_quality_checks_reject_undertrained_history(self):
        history = [
            {"alpha_m2_s": 1.0e-5, "h_w_m2k": 12.0},
            {"alpha_m2_s": 1.4e-5, "h_w_m2k": 11.0},
            {"alpha_m2_s": 1.8e-5, "h_w_m2k": 10.8},
        ]
        summary = {"completed_steps": 3, "thermal_conductivity_w_mk": 95.0}

        checks = build_quality_checks(history, summary, BaseArgs())

        self.assertFalse(checks["enough_steps"])
        self.assertFalse(checks["parameters_stable"])
        self.assertFalse(checks["recommended_for_reporting"])
        self.assertIn("completed_steps_below_min_quality_steps", checks["warnings"])

    def test_quality_checks_reject_out_of_material_range_result(self):
        class Args(BaseArgs):
            expected_k_min = 80.0
            expected_k_max = 120.0

        history = [
            {"alpha_m2_s": 2.0e-5, "h_w_m2k": 10.0},
            {"alpha_m2_s": 2.01e-5, "h_w_m2k": 10.01},
            {"alpha_m2_s": 2.02e-5, "h_w_m2k": 10.0},
        ] * 400
        summary = {"completed_steps": 1200, "thermal_conductivity_w_mk": 71.0}

        checks = build_quality_checks(history, summary, Args())

        self.assertTrue(checks["enough_steps"])
        self.assertTrue(checks["parameters_stable"])
        self.assertFalse(checks["expected_k_in_range"])
        self.assertFalse(checks["recommended_for_reporting"])


class DataWeightingTests(unittest.TestCase):
    def test_delta_initial_weights_start_at_one_and_emphasize_heated_front(self):
        class Args(BaseArgs):
            data_weighting = "delta-initial"
            data_weighting_lambda = 1.0
            data_weighting_temp_scale_c = 10.0
            data_weighting_max_extra = 4.0

        dataset = make_dataset(Args())
        context = prepare_training_context(dataset, Args(), torch.device("cpu"))
        weights = context["data_weights"].cpu().numpy().reshape(dataset["xt_grid_c"].shape)

        self.assertTrue(np.allclose(weights[0], np.ones_like(weights[0])))
        self.assertGreater(weights[2, 0], weights[1, 0])
        self.assertLessEqual(float(weights.max()), 5.0)


class LbfgsSamplingTests(unittest.TestCase):
    def test_lbfgs_reuses_same_sampled_points_inside_closure(self):
        class Args(BaseArgs):
            epochs = 0
            lbfgs_steps = 1
            data_batch_size = 5
            collocation_points = 12

        dataset = make_dataset(Args())
        model = SimplePINN(hidden_width=8, hidden_depth=2)
        seen_ids = []
        original_compute = train_pinn_1d.compute_training_losses

        def wrapped_compute(model, dataset, args, device, context, loss_points=None):
            if loss_points is not None:
                seen_ids.append(
                    (
                        id(loss_points["data_indices"]),
                        id(loss_points["collocation"]),
                        id(loss_points["t_left"]),
                    )
                )
            return original_compute(model, dataset, args, device, context, loss_points=loss_points)

        try:
            train_pinn_1d.compute_training_losses = wrapped_compute
            train_model(model, dataset, Args(), torch.device("cpu"))
        finally:
            train_pinn_1d.compute_training_losses = original_compute

        self.assertGreaterEqual(len(seen_ids), 2)
        self.assertEqual(len(set(seen_ids)), 1)


if __name__ == "__main__":
    unittest.main()
