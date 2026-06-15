from pathlib import Path
import json
import sys
import tempfile
import unittest

import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import train_pinn_1d  # type: ignore
import train_pinn_1d_minibatch  # type: ignore
from train_pinn_1d import (  # type: ignore
    SimplePINN,
    apply_material_preset,
    build_best_physical_result,
    build_optimizer,
    build_quality_checks,
    compute_training_losses,
    load_checkpoint_into_model,
    normalize_dataset,
    prepare_training_context,
    save_training_outputs,
    sample_training_loss_points,
    step_window_rows,
    train_model,
)


class BaseArgs:
    dataset_path = "dummy_dataset.npz"
    hidden_width = 8
    hidden_depth = 2
    alpha_init = 2.5e-5
    h_init = 12.0
    fixed_h = None
    allow_joint_h_reporting = False
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
    alpha_lr = None
    h_lr = None
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
    material_preset = "custom"
    expected_k_min = None
    expected_k_max = None
    convergence_tail_steps = 300
    min_quality_steps = 1000
    max_alpha_tail_rel_range = 0.05
    max_h_tail_rel_range = 0.05
    resume_checkpoint = None


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
    def test_training_loss_always_uses_full_data_loss(self):
        dataset = make_dataset()
        context = prepare_training_context(dataset, BaseArgs(), torch.device("cpu"))
        loss_points = sample_training_loss_points(BaseArgs(), torch.device("cpu"), context)

        self.assertNotIn("data_indices", loss_points)

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

    def test_pde_sampling_is_uniform_over_full_normalized_domain(self):
        class Args(BaseArgs):
            collocation_points = 100

        loss_points = sample_training_loss_points(Args(), torch.device("cpu"))
        collocation = loss_points["collocation"]

        self.assertEqual(tuple(collocation.shape), (100, 2))
        self.assertTrue(torch.all(collocation >= 0.0))
        self.assertTrue(torch.all(collocation <= 1.0))


class MiniBatchSamplingTests(unittest.TestCase):
    def test_minibatch_loss_points_include_data_indices(self):
        class Args(BaseArgs):
            data_batch_size = 5
            collocation_points = 12

        dataset = make_dataset(Args())
        context = prepare_training_context(dataset, Args(), torch.device("cpu"))

        loss_points = train_pinn_1d_minibatch.sample_training_loss_points_minibatch(
            Args(), torch.device("cpu"), context
        )

        self.assertIn("data_indices", loss_points)
        self.assertEqual(tuple(loss_points["data_indices"].shape), (5,))
        self.assertTrue(torch.all(loss_points["data_indices"] >= 0))
        self.assertTrue(torch.all(loss_points["data_indices"] < context["coords"].shape[0]))

    def test_minibatch_compute_training_losses_uses_sampled_data_only(self):
        class Args(BaseArgs):
            data_batch_size = 2
            collocation_points = 12
            pde_weight = 0.0
            bc_weight = 0.0
            ic_weight = 0.0

        dataset = make_dataset(Args())
        context = prepare_training_context(dataset, Args(), torch.device("cpu"))
        model = SimplePINN(hidden_width=8, hidden_depth=2)
        data_indices = torch.tensor([0, 1], dtype=torch.long)
        loss_points = {
            "data_indices": data_indices,
            "collocation": torch.rand(Args.collocation_points, 2),
            "t_left": torch.rand(64, 1),
            "t_right": torch.rand(64, 1),
        }

        losses = train_pinn_1d_minibatch.compute_training_losses_minibatch(
            model,
            dataset,
            Args(),
            torch.device("cpu"),
            context,
            loss_points=loss_points,
        )

        with torch.no_grad():
            expected = torch.mean((model(context["coords"][data_indices]) - context["targets"][data_indices]).pow(2))
        self.assertAlmostEqual(float(losses[1].item()), float(expected.item()), places=7)

    def test_minibatch_train_model_runs_without_recursive_sampler_patch(self):
        class Args(BaseArgs):
            epochs = 1
            data_batch_size = 4
            collocation_points = 12

        dataset = make_dataset(Args())
        model = SimplePINN(hidden_width=8, hidden_depth=2)

        history = train_pinn_1d_minibatch.train_model_minibatch(
            model,
            dataset,
            Args(),
            torch.device("cpu"),
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["stage"], "adam")


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

    def test_quality_checks_require_fixed_h_or_explicit_joint_h_override(self):
        class JointArgs(BaseArgs):
            min_quality_steps = 3
            convergence_tail_steps = 3
            fixed_h = None
            allow_joint_h_reporting = False

        history = [
            {"alpha_m2_s": 2.0e-5, "h_w_m2k": 10.0},
            {"alpha_m2_s": 2.01e-5, "h_w_m2k": 10.01},
            {"alpha_m2_s": 2.0e-5, "h_w_m2k": 10.0},
        ]
        summary = {"completed_steps": 3, "thermal_conductivity_w_mk": 60.0}

        checks = build_quality_checks(history, summary, JointArgs())

        self.assertFalse(checks["recommended_for_reporting"])
        self.assertIn("joint_h_requires_multistart_validation", checks["warnings"])

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


class BestPhysicalSelectionTests(unittest.TestCase):
    def test_step_window_rows_uses_step_values_not_history_row_count(self):
        history = [
            {"step": 0, "alpha_m2_s": 1.0},
            {"step": 100, "alpha_m2_s": 1.01},
            {"step": 200, "alpha_m2_s": 1.02},
            {"step": 350, "alpha_m2_s": 1.03},
            {"step": 500, "alpha_m2_s": 1.04},
        ]

        rows = step_window_rows(history, end_step=500, window_steps=300)

        self.assertEqual([row["step"] for row in rows], [200, 350, 500])

    def test_best_physical_prefers_reportable_plateau_over_lowest_data_loss(self):
        class Args(BaseArgs):
            expected_k_min = 130.0
            expected_k_max = 190.0
            rho = 2700.0
            cp = 900.0
            min_quality_steps = 500
            convergence_tail_steps = 200

        history = []
        for step in range(0, 701, 100):
            alpha = 6.58e-5 if step <= 500 else 9.30e-5
            history.append(
                {
                    "step": step,
                    "stage": "adam",
                    "lr": 1.0e-3,
                    "loss": 1.0 / (step + 1),
                    "data_loss": 0.003 if step <= 500 else 0.002,
                    "pde_loss": 0.05,
                    "bc_loss": 0.0,
                    "ic_loss": 0.0,
                    "alpha_m2_s": alpha,
                    "h_w_m2k": 11.2 if step <= 500 else 10.8,
                }
            )

        result = build_best_physical_result(history, Args())

        self.assertTrue(result["found"])
        self.assertEqual(result["step"], 500)
        self.assertAlmostEqual(result["thermal_conductivity_w_mk"], 159.894, places=3)
        self.assertGreater(history[-1]["alpha_m2_s"] * Args.rho * Args.cp, Args.expected_k_max)


class CheckpointCompatibilityTests(unittest.TestCase):
    def test_legacy_model_only_checkpoint_reports_legacy_resume_mode(self):
        model = SimplePINN(hidden_width=8, hidden_depth=2)

        with tempfile.TemporaryDirectory() as tmp_dir:
            checkpoint_path = Path(tmp_dir) / "legacy.pt"
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "model_config": {"hidden_width": 8, "hidden_depth": 2},
                },
                checkpoint_path,
            )

            loaded_model = SimplePINN(hidden_width=8, hidden_depth=2)
            metadata = load_checkpoint_into_model(loaded_model, checkpoint_path, torch.device("cpu"))

        self.assertEqual(metadata["resume_mode"], "model_only_legacy")
        self.assertFalse(metadata["full_resume_available"])


class PhysicalParameterLearningRateTests(unittest.TestCase):
    def test_optimizer_uses_separate_alpha_and_h_learning_rates(self):
        class Args(BaseArgs):
            lr = 1.0e-3
            alpha_lr = 2.0e-3
            h_lr = 1.0e-2

        model = SimplePINN(hidden_width=8, hidden_depth=2)
        optimizer = build_optimizer(model, Args())

        self.assertEqual([group["lr"] for group in optimizer.param_groups], [1.0e-3, 2.0e-3, 1.0e-2])

    def test_fixed_h_is_not_added_to_optimizer_and_does_not_change(self):
        class Args(BaseArgs):
            fixed_h = 10.0

        model = SimplePINN(hidden_width=8, hidden_depth=2, fixed_h=Args.fixed_h)
        optimizer = build_optimizer(model, Args())
        initial_h = float(model.h.item())
        loss = model(torch.rand(4, 2)).pow(2).mean() + model.alpha
        loss.backward()
        optimizer.step()

        self.assertAlmostEqual(float(model.h.item()), initial_h, places=7)
        self.assertEqual([group["name"] for group in optimizer.param_groups], ["network", "alpha"])


class LbfgsSamplingTests(unittest.TestCase):
    def test_lbfgs_reuses_same_sampled_points_inside_closure(self):
        class Args(BaseArgs):
            epochs = 0
            lbfgs_steps = 1
            collocation_points = 12

        dataset = make_dataset(Args())
        model = SimplePINN(hidden_width=8, hidden_depth=2)
        seen_ids = []
        original_compute = train_pinn_1d.compute_training_losses

        def wrapped_compute(model, dataset, args, device, context, loss_points=None):
            if loss_points is not None:
                seen_ids.append(
                    (
                        id(loss_points["collocation"]),
                        id(loss_points["t_left"]),
                        id(loss_points["t_right"]),
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


class OutputLayoutTests(unittest.TestCase):
    def test_training_outputs_are_grouped_by_output_stem(self):
        dataset = make_dataset()
        model = SimplePINN(hidden_width=8, hidden_depth=2)
        history = [
            {
                "epoch": 0,
                "step": 0,
                "stage": "adam",
                "lr": 1.0e-3,
                "loss": 1.0,
                "data_loss": 1.0,
                "pde_loss": 0.0,
                "bc_loss": 0.0,
                "ic_loss": 0.0,
                "alpha_m2_s": 2.5e-5,
                "h_w_m2k": 12.0,
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            original_models_dir = train_pinn_1d.MODELS_DIR
            original_figures_dir = train_pinn_1d.FIGURES_DIR
            try:
                train_pinn_1d.MODELS_DIR = Path(tmp_dir) / "models"
                train_pinn_1d.FIGURES_DIR = Path(tmp_dir) / "figures"
                paths = save_training_outputs(
                    model,
                    dataset,
                    history,
                    BaseArgs(),
                    "case_001",
                    torch.device("cpu"),
                )
                expected_dir_name = "case_001"
                for path in paths.values():
                    self.assertEqual(path.parent.name, expected_dir_name)
                    self.assertTrue(path.name.startswith("case_001"))
                    self.assertTrue(path.exists())
            finally:
                train_pinn_1d.MODELS_DIR = original_models_dir
                train_pinn_1d.FIGURES_DIR = original_figures_dir

    def test_best_physical_result_writes_matching_checkpoint(self):
        class Args(BaseArgs):
            expected_k_min = 50.0
            expected_k_max = 80.0
            min_quality_steps = 1
            convergence_tail_steps = 2

        dataset = make_dataset(Args())
        model = SimplePINN(hidden_width=8, hidden_depth=2)
        history = []
        for step in range(3):
            history.append(
                {
                    "epoch": step,
                    "step": step,
                    "stage": "adam",
                    "lr": 1.0e-3,
                    "loss": 1.0,
                    "data_loss": 0.01,
                    "pde_loss": 0.01,
                    "bc_loss": 0.0,
                    "ic_loss": 0.0,
                    "alpha_m2_s": 2.5e-5,
                    "h_w_m2k": 12.0,
                }
            )
        args = Args()
        args._training_state = {
            "candidate_states": {
                2: {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            },
            "resume_mode": "none",
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            original_models_dir = train_pinn_1d.MODELS_DIR
            original_figures_dir = train_pinn_1d.FIGURES_DIR
            try:
                train_pinn_1d.MODELS_DIR = Path(tmp_dir) / "models"
                train_pinn_1d.FIGURES_DIR = Path(tmp_dir) / "figures"
                paths = save_training_outputs(
                    model,
                    dataset,
                    history,
                    args,
                    "case_best",
                    torch.device("cpu"),
                )
                self.assertIn("best_physical_model", paths)
                self.assertTrue(paths["best_physical_model"].exists())
                with open(paths["summary"], "r", encoding="utf-8") as handle:
                    summary = json.load(handle)
                self.assertIn(summary["recommended_result_source"], {"final", "best_physical"})
                self.assertEqual(
                    Path(summary["best_physical"]["model_path"]),
                    paths["best_physical_model"].resolve(),
                )
            finally:
                train_pinn_1d.MODELS_DIR = original_models_dir
                train_pinn_1d.FIGURES_DIR = original_figures_dir


if __name__ == "__main__":
    unittest.main()
