import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn

from view_dat import PROJECT_ROOT


DERIVED_DATA_DIR = PROJECT_ROOT / "data" / "derived"
MODELS_DIR = PROJECT_ROOT / "outputs" / "models"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
DEFAULT_DATASET = DERIVED_DATA_DIR / "thermal90-20260522-run02_rod_xt_data.npz"
DEFAULT_EPOCHS = 3000
DEFAULT_LR = 1e-3
DEFAULT_HIDDEN_WIDTH = 64
DEFAULT_HIDDEN_DEPTH = 4
DEFAULT_COLLLOCATION_POINTS = 2048
DEFAULT_DATA_WEIGHT = 10.0
DEFAULT_PDE_WEIGHT = 1.0
DEFAULT_BC_WEIGHT = 3.0
DEFAULT_IC_WEIGHT = 3.0
DEFAULT_RHO = 2700.0
DEFAULT_CP = 900.0
DEFAULT_DIAMETER_MM = 8.0
DEFAULT_VISIBLE_LENGTH_MM = 136.0
DEFAULT_EMISSIVITY = 0.95
DEFAULT_SIGMA_SB = 5.67e-8
DEFAULT_T_INF_C = 25.0
DEFAULT_ALPHA_INIT = 2.5e-5
DEFAULT_H_INIT = 12.0
DEFAULT_INITIAL_MODE = "measured"
DEFAULT_MEASURED_INITIAL_FRAME_COUNT = 5
DEFAULT_RIGHT_BC_MODE = "none"
DEFAULT_DATA_BATCH_SIZE = 0
DEFAULT_PDE_SAMPLING = "uniform"
DEFAULT_PDE_HOT_X_MAX = 0.2
DEFAULT_PDE_EARLY_T_MAX = 0.3
DEFAULT_DATA_WEIGHTING = "none"
DEFAULT_DATA_WEIGHTING_LAMBDA = 1.0
DEFAULT_DATA_WEIGHTING_TEMP_SCALE_C = 10.0
DEFAULT_DATA_WEIGHTING_MAX_EXTRA = 4.0
DEFAULT_TRAINING_PRESET = "none"
DEFAULT_MATERIAL_PRESET = "custom"
MATERIAL_PRESETS = {
    "6061": {"rho": 2700.0, "cp": 900.0, "expected_k_min": 130.0, "expected_k_max": 190.0},
    "304": {"rho": 7930.0, "cp": 500.0, "expected_k_min": 10.0, "expected_k_max": 25.0},
    "h59": {"rho": 8500.0, "cp": 380.0, "expected_k_min": 80.0, "expected_k_max": 120.0},
}


def parse_args():
    parser = argparse.ArgumentParser(description="Train a 1D PINN with convection and radiation losses.")
    parser.add_argument("dataset_path", nargs="?", default=str(DEFAULT_DATASET))
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_LR)
    parser.add_argument("--hidden-width", type=int, default=DEFAULT_HIDDEN_WIDTH)
    parser.add_argument("--hidden-depth", type=int, default=DEFAULT_HIDDEN_DEPTH)
    parser.add_argument("--collocation-points", type=int, default=DEFAULT_COLLLOCATION_POINTS)
    parser.add_argument("--data-weight", type=float, default=DEFAULT_DATA_WEIGHT)
    parser.add_argument("--pde-weight", type=float, default=DEFAULT_PDE_WEIGHT)
    parser.add_argument("--bc-weight", type=float, default=DEFAULT_BC_WEIGHT)
    parser.add_argument("--ic-weight", type=float, default=DEFAULT_IC_WEIGHT)
    parser.add_argument("--rho", type=float, default=DEFAULT_RHO)
    parser.add_argument("--cp", type=float, default=DEFAULT_CP)
    parser.add_argument("--material-preset", choices=["custom", "6061", "304", "h59"], default=DEFAULT_MATERIAL_PRESET)
    parser.add_argument("--expected-k-min", type=float, default=None)
    parser.add_argument("--expected-k-max", type=float, default=None)
    parser.add_argument("--diameter-mm", type=float, default=DEFAULT_DIAMETER_MM)
    parser.add_argument("--visible-length-mm", type=float, default=DEFAULT_VISIBLE_LENGTH_MM)
    parser.add_argument("--emissivity", type=float, default=DEFAULT_EMISSIVITY)
    parser.add_argument("--sigma-sb", type=float, default=DEFAULT_SIGMA_SB)
    parser.add_argument("--t-inf-c", type=float, default=DEFAULT_T_INF_C)
    parser.add_argument("--alpha-init", type=float, default=DEFAULT_ALPHA_INIT)
    parser.add_argument("--h-init", type=float, default=DEFAULT_H_INIT)
    parser.add_argument("--lr-scheduler", choices=["none", "plateau"], default="none")
    parser.add_argument("--lr-factor", type=float, default=0.5)
    parser.add_argument("--lr-patience", type=int, default=200)
    parser.add_argument("--min-lr", type=float, default=1e-6)
    parser.add_argument("--resume-checkpoint", default=None)
    parser.add_argument("--lbfgs-steps", type=int, default=0)
    parser.add_argument("--lbfgs-lr", type=float, default=1.0)
    parser.add_argument("--lbfgs-history-size", type=int, default=50)
    parser.add_argument("--lbfgs-line-search", choices=["none", "strong_wolfe"], default="strong_wolfe")
    parser.add_argument("--early-stop-window", type=int, default=0)
    parser.add_argument("--early-stop-loss-rel-tol", type=float, default=1e-4)
    parser.add_argument("--early-stop-param-rel-tol", type=float, default=5e-4)
    parser.add_argument("--data-batch-size", type=int, default=DEFAULT_DATA_BATCH_SIZE)
    parser.add_argument("--pde-sampling", choices=["uniform", "mixed"], default=DEFAULT_PDE_SAMPLING)
    parser.add_argument("--pde-hot-x-max", type=float, default=DEFAULT_PDE_HOT_X_MAX)
    parser.add_argument("--pde-early-t-max", type=float, default=DEFAULT_PDE_EARLY_T_MAX)
    parser.add_argument("--data-weighting", choices=["none", "delta-initial"], default=DEFAULT_DATA_WEIGHTING)
    parser.add_argument("--data-weighting-lambda", type=float, default=DEFAULT_DATA_WEIGHTING_LAMBDA)
    parser.add_argument("--data-weighting-temp-scale-c", type=float, default=DEFAULT_DATA_WEIGHTING_TEMP_SCALE_C)
    parser.add_argument("--data-weighting-max-extra", type=float, default=DEFAULT_DATA_WEIGHTING_MAX_EXTRA)
    parser.add_argument("--training-preset", choices=["none", "stable", "experimental"], default=DEFAULT_TRAINING_PRESET)
    parser.add_argument("--convergence-tail-steps", type=int, default=300)
    parser.add_argument("--min-quality-steps", type=int, default=1000)
    parser.add_argument("--max-alpha-tail-rel-range", type=float, default=0.05)
    parser.add_argument("--max-h-tail-rel-range", type=float, default=0.05)
    parser.add_argument("--initial-mode", choices=["ambient", "measured"], default=DEFAULT_INITIAL_MODE)
    parser.add_argument("--measured-initial-frame-count", type=int, default=DEFAULT_MEASURED_INITIAL_FRAME_COUNT)
    parser.add_argument("--right-bc-mode", choices=["none", "robin"], default=DEFAULT_RIGHT_BC_MODE)
    parser.add_argument(
        "--calibration-mode",
        choices=["average", "length", "diameter", "manual"],
        default="diameter",
    )
    parser.add_argument("--mm-per-px", type=float, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output-stem", default=None)
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()
    args = apply_material_preset(args)
    return apply_training_preset(args)


def apply_material_preset(args):
    preset = getattr(args, "material_preset", DEFAULT_MATERIAL_PRESET)
    if preset == "custom":
        return args
    if preset not in MATERIAL_PRESETS:
        raise ValueError(f"Unsupported material preset: {preset}")
    config = MATERIAL_PRESETS[preset]
    args.rho = config["rho"]
    args.cp = config["cp"]
    if getattr(args, "expected_k_min", None) is None:
        args.expected_k_min = config["expected_k_min"]
    if getattr(args, "expected_k_max", None) is None:
        args.expected_k_max = config["expected_k_max"]
    return args


def apply_training_preset(args):
    preset = getattr(args, "training_preset", DEFAULT_TRAINING_PRESET)
    if preset == "none":
        return args
    if preset == "stable":
        args.data_batch_size = 16384
        args.pde_sampling = "uniform"
        args.data_weighting = "none"
        return args
    if preset == "experimental":
        args.data_batch_size = 16384
        args.pde_sampling = "mixed"
        args.data_weighting = "delta-initial"
        return args
    raise ValueError(f"Unsupported training preset: {preset}")


def tail_relative_range(history, key, tail_steps):
    values = [float(row[key]) for row in history[-tail_steps:] if key in row and row[key] is not None]
    if not values:
        return None
    denominator = max(abs(values[-1]), 1.0e-12)
    return float((max(values) - min(values)) / denominator)


def build_quality_checks(history, summary, args):
    completed_steps = int(summary.get("completed_steps", len(history)))
    tail_steps = max(1, int(getattr(args, "convergence_tail_steps", 300)))
    min_quality_steps = max(0, int(getattr(args, "min_quality_steps", 1000)))
    max_alpha_range = float(getattr(args, "max_alpha_tail_rel_range", 0.05))
    max_h_range = float(getattr(args, "max_h_tail_rel_range", 0.05))

    alpha_tail_rel_range = tail_relative_range(history, "alpha_m2_s", tail_steps)
    h_tail_rel_range = tail_relative_range(history, "h_w_m2k", tail_steps)
    enough_steps = completed_steps >= min_quality_steps
    parameters_stable = (
        alpha_tail_rel_range is not None
        and h_tail_rel_range is not None
        and alpha_tail_rel_range <= max_alpha_range
        and h_tail_rel_range <= max_h_range
    )

    expected_k_min = getattr(args, "expected_k_min", None)
    expected_k_max = getattr(args, "expected_k_max", None)
    conductivity = summary.get("thermal_conductivity_w_mk")
    expected_k_in_range = None
    if expected_k_min is not None and expected_k_max is not None and conductivity is not None:
        expected_k_in_range = float(expected_k_min) <= float(conductivity) <= float(expected_k_max)

    warnings = []
    if not enough_steps:
        warnings.append("completed_steps_below_min_quality_steps")
    if not parameters_stable:
        warnings.append("tail_parameters_not_stable")
    if expected_k_in_range is False:
        warnings.append("thermal_conductivity_outside_expected_material_range")
    if getattr(args, "training_preset", DEFAULT_TRAINING_PRESET) == "experimental":
        warnings.append("experimental_training_preset_not_for_formal_reporting")

    if expected_k_in_range is None:
        recommended = enough_steps and parameters_stable and getattr(args, "training_preset", DEFAULT_TRAINING_PRESET) != "experimental"
    else:
        recommended = (
            enough_steps
            and parameters_stable
            and expected_k_in_range
            and getattr(args, "training_preset", DEFAULT_TRAINING_PRESET) != "experimental"
        )

    return {
        "recommended_for_reporting": bool(recommended),
        "warnings": warnings,
        "enough_steps": bool(enough_steps),
        "parameters_stable": bool(parameters_stable),
        "tail_steps": tail_steps,
        "min_quality_steps": min_quality_steps,
        "alpha_tail_rel_range": alpha_tail_rel_range,
        "h_tail_rel_range": h_tail_rel_range,
        "max_alpha_tail_rel_range": max_alpha_range,
        "max_h_tail_rel_range": max_h_range,
        "expected_k_min": None if expected_k_min is None else float(expected_k_min),
        "expected_k_max": None if expected_k_max is None else float(expected_k_max),
        "expected_k_in_range": expected_k_in_range,
    }


def choose_device(device_arg):
    if device_arg == "cuda":
        return torch.device("cuda")
    if device_arg == "cpu":
        return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_xt_dataset(dataset_path):
    data = np.load(dataset_path)
    xt_grid_c = data["xt_grid_c"].astype(np.float32)
    time_axis_sec = data["time_axis_sec"].astype(np.float32)
    x_axis_heat_px = data["x_axis_heat_px"].astype(np.float32)
    boundary_temperature_c = data["boundary_temperature_c"].astype(np.float32)
    far_end_temperature_c = data["far_end_temperature_c"].astype(np.float32)
    x_axis_mm = (
        data["x_axis_mm"].astype(np.float32)
        if "x_axis_mm" in data.files and len(data["x_axis_mm"]) > 0
        else None
    )

    t_mesh, x_mesh = np.meshgrid(time_axis_sec, x_axis_heat_px, indexing="ij")
    inputs_xt = np.stack([x_mesh.reshape(-1), t_mesh.reshape(-1)], axis=1).astype(np.float32)
    temperature_c = xt_grid_c.reshape(-1, 1).astype(np.float32)

    return {
        "xt_grid_c": xt_grid_c,
        "inputs_xt": inputs_xt,
        "temperature_c": temperature_c,
        "time_axis_sec": time_axis_sec,
        "x_axis_heat_px": x_axis_heat_px,
        "boundary_temperature_c": boundary_temperature_c,
        "far_end_temperature_c": far_end_temperature_c,
        "x_axis_mm": x_axis_mm,
    }


def build_boundary_interpolator(times, values):
    times = np.asarray(times, dtype=np.float32)
    values = np.asarray(values, dtype=np.float32)

    def interpolate(query_times):
        query_times = np.asarray(query_times, dtype=np.float32)
        return np.interp(query_times, times, values, left=values[0], right=values[-1]).astype(np.float32)

    return interpolate


def sample_collocation_points(count, time_min, time_max, x_min, x_max, device):
    t = torch.rand(count, 1, device=device) * (time_max - time_min) + time_min
    x = torch.rand(count, 1, device=device) * (x_max - x_min) + x_min
    return torch.cat([x, t], dim=1)


def sample_mixed_collocation_points(count, hot_x_max, early_t_max, device):
    hot_count = int(count * 0.2)
    early_count = int(count * 0.1)
    uniform_count = max(0, count - hot_count - early_count)
    hot_x_max = min(max(float(hot_x_max), 0.0), 1.0)
    early_t_max = min(max(float(early_t_max), 0.0), 1.0)
    parts = []
    if uniform_count:
        parts.append(sample_collocation_points(uniform_count, 0.0, 1.0, 0.0, 1.0, device))
    if hot_count:
        parts.append(sample_collocation_points(hot_count, 0.0, 1.0, 0.0, hot_x_max, device))
    if early_count:
        parts.append(sample_collocation_points(early_count, 0.0, early_t_max, 0.0, 1.0, device))
    if not parts:
        return torch.empty((0, 2), dtype=torch.float32, device=device)
    return torch.cat(parts, dim=0)


def estimate_mm_per_px(roi_width_px, roi_height_px, visible_length_mm, diameter_mm):
    length_based = float(visible_length_mm) / float(roi_width_px)
    diameter_based = float(diameter_mm) / float(roi_height_px)
    combined = 0.5 * (length_based + diameter_based)
    return {
        "length_based_mm_per_px": length_based,
        "diameter_based_mm_per_px": diameter_based,
        "combined_mm_per_px": combined,
    }


def convert_alpha_to_conductivity(alpha_m2_s, rho_kg_m3, cp_j_kgk):
    return float(alpha_m2_s) * float(rho_kg_m3) * float(cp_j_kgk)


def pde_residual_physical(
    temperature_c,
    temperature_t_c_s,
    temperature_xx_c_m2,
    alpha_m2_s,
    h_w_m2k,
    rho_kg_m3,
    cp_j_kgk,
    diameter_m,
    emissivity,
    sigma_sb,
    t_inf_k,
):
    temperature_k = float(temperature_c) + 273.15
    conv_coeff = 4.0 * float(h_w_m2k) / (float(rho_kg_m3) * float(cp_j_kgk) * float(diameter_m))
    rad_coeff = 4.0 * float(emissivity) * float(sigma_sb) / (float(rho_kg_m3) * float(cp_j_kgk) * float(diameter_m))
    return (
        float(temperature_t_c_s)
        - float(alpha_m2_s) * float(temperature_xx_c_m2)
        + conv_coeff * (temperature_k - float(t_inf_k))
        + rad_coeff * (temperature_k**4 - float(t_inf_k) ** 4)
    )


def inverse_softplus(value):
    value = max(float(value), 1e-12)
    return math.log(math.expm1(value))


class SimplePINN(nn.Module):
    def __init__(self, hidden_width=64, hidden_depth=4, alpha_init=DEFAULT_ALPHA_INIT, h_init=DEFAULT_H_INIT):
        super().__init__()
        layers = [nn.Linear(2, hidden_width), nn.Tanh()]
        for _ in range(hidden_depth - 1):
            layers.extend([nn.Linear(hidden_width, hidden_width), nn.Tanh()])
        layers.append(nn.Linear(hidden_width, 1))
        self.network = nn.Sequential(*layers)
        self.alpha_raw = nn.Parameter(torch.tensor(inverse_softplus(alpha_init), dtype=torch.float32))
        self.h_raw = nn.Parameter(torch.tensor(inverse_softplus(h_init), dtype=torch.float32))

    @property
    def alpha(self):
        return torch.nn.functional.softplus(self.alpha_raw) + 1e-9

    @property
    def h(self):
        return torch.nn.functional.softplus(self.h_raw) + 1e-6

    def forward(self, coords):
        return self.network(coords)


def resolve_mm_per_px(dataset, args):
    if args.mm_per_px is not None:
        return float(args.mm_per_px), {"mode": "manual", "manual_mm_per_px": float(args.mm_per_px)}
    if dataset["x_axis_mm"] is not None and len(dataset["x_axis_mm"]) > 1:
        inferred = float(dataset["x_axis_mm"][1] - dataset["x_axis_mm"][0])
        return inferred, {"mode": "dataset", "dataset_mm_per_px": inferred}

    calibration = estimate_mm_per_px(
        roi_width_px=dataset["xt_grid_c"].shape[1],
        roi_height_px=4,
        visible_length_mm=args.visible_length_mm,
        diameter_mm=args.diameter_mm,
    )
    if args.calibration_mode == "length":
        value = calibration["length_based_mm_per_px"]
    elif args.calibration_mode == "average":
        value = calibration["combined_mm_per_px"]
    else:
        value = calibration["diameter_based_mm_per_px"]
    calibration["mode"] = args.calibration_mode
    return value, calibration


def normalize_dataset(dataset, args):
    x = dataset["inputs_xt"][:, 0]
    t = dataset["inputs_xt"][:, 1]
    u = dataset["temperature_c"][:, 0]

    x_min = float(x.min())
    x_max = float(x.max())
    t_min = float(t.min())
    t_max = float(t.max())
    u_mean = float(u.mean())
    u_std = float(u.std()) if float(u.std()) > 1e-6 else 1.0

    mm_per_px, calibration = resolve_mm_per_px(dataset, args)
    x_span_m = (x_max - x_min) * mm_per_px * 1e-3
    t_span_s = t_max - t_min if t_max > t_min else 1.0

    normalized = dict(dataset)
    normalized["x_min"] = x_min
    normalized["x_max"] = x_max
    normalized["t_min"] = t_min
    normalized["t_max"] = t_max
    normalized["u_mean"] = u_mean
    normalized["u_std"] = u_std
    normalized["mm_per_px"] = mm_per_px
    normalized["calibration"] = calibration
    normalized["x_span_m"] = x_span_m
    normalized["t_span_s"] = t_span_s
    normalized["x_norm"] = ((x - x_min) / (x_max - x_min)).astype(np.float32)
    normalized["t_norm"] = ((t - t_min) / t_span_s).astype(np.float32)
    normalized["u_norm"] = ((u - u_mean) / u_std).astype(np.float32)
    normalized["xt_grid_norm"] = ((dataset["xt_grid_c"] - u_mean) / u_std).astype(np.float32)
    normalized["boundary_norm"] = ((dataset["boundary_temperature_c"] - u_mean) / u_std).astype(np.float32)
    normalized["far_end_norm"] = ((dataset["far_end_temperature_c"] - u_mean) / u_std).astype(np.float32)
    return normalized


def build_initial_profile_target(dataset, initial_mode, t_inf_c, measured_frame_count):
    x_count = dataset["xt_grid_c"].shape[1]
    if initial_mode == "ambient":
        ambient_norm = (float(t_inf_c) - dataset["u_mean"]) / dataset["u_std"]
        return np.full((x_count, 1), ambient_norm, dtype=np.float32)

    frame_count = max(1, min(int(measured_frame_count), dataset["xt_grid_c"].shape[0]))
    measured_profile_c = dataset["xt_grid_c"][:frame_count].mean(axis=0)
    measured_profile_norm = ((measured_profile_c - dataset["u_mean"]) / dataset["u_std"]).astype(np.float32)
    return measured_profile_norm.reshape(-1, 1)


def build_initial_profile_c(dataset, initial_mode, t_inf_c, measured_frame_count):
    x_count = dataset["xt_grid_c"].shape[1]
    if initial_mode == "ambient":
        return np.full((x_count,), float(t_inf_c), dtype=np.float32)
    frame_count = max(1, min(int(measured_frame_count), dataset["xt_grid_c"].shape[0]))
    return dataset["xt_grid_c"][:frame_count].mean(axis=0).astype(np.float32)


def build_data_weights(dataset, args):
    mode = getattr(args, "data_weighting", DEFAULT_DATA_WEIGHTING)
    if mode == "none":
        return np.ones((dataset["temperature_c"].shape[0], 1), dtype=np.float32)
    if mode != "delta-initial":
        raise ValueError(f"Unsupported data weighting mode: {mode}")

    initial_profile = build_initial_profile_c(
        dataset,
        initial_mode=args.initial_mode,
        t_inf_c=args.t_inf_c,
        measured_frame_count=args.measured_initial_frame_count,
    )
    scale = max(float(getattr(args, "data_weighting_temp_scale_c", DEFAULT_DATA_WEIGHTING_TEMP_SCALE_C)), 1e-6)
    max_extra = max(float(getattr(args, "data_weighting_max_extra", DEFAULT_DATA_WEIGHTING_MAX_EXTRA)), 0.0)
    weight_lambda = float(getattr(args, "data_weighting_lambda", DEFAULT_DATA_WEIGHTING_LAMBDA))
    delta = np.abs(dataset["xt_grid_c"] - initial_profile.reshape(1, -1))
    extra = np.clip(delta / scale, 0.0, max_extra)
    weights = 1.0 + weight_lambda * extra
    return weights.astype(np.float32).reshape(-1, 1)


def compute_temperature_and_derivatives(model, coords, dataset):
    coords = coords.clone().detach().requires_grad_(True)
    pred_norm = model(coords)
    grads = torch.autograd.grad(pred_norm, coords, torch.ones_like(pred_norm), create_graph=True)[0]
    pred_c = pred_norm * dataset["u_std"] + dataset["u_mean"]
    temp_t_c_s = dataset["u_std"] * grads[:, 1:2] / dataset["t_span_s"]
    temp_x_c_m = dataset["u_std"] * grads[:, 0:1] / dataset["x_span_m"]
    temp_xx_norm = torch.autograd.grad(
        grads[:, 0:1],
        coords,
        torch.ones_like(grads[:, 0:1]),
        create_graph=True,
    )[0][:, 0:1]
    temp_xx_c_m2 = dataset["u_std"] * temp_xx_norm / (dataset["x_span_m"] ** 2)
    return coords, pred_norm, pred_c, temp_t_c_s, temp_x_c_m, temp_xx_c_m2


def compute_pde_loss(model, coords, dataset, args):
    _, _, pred_c, temp_t_c_s, _, temp_xx_c_m2 = compute_temperature_and_derivatives(model, coords, dataset)
    temperature_k = pred_c + 273.15
    t_inf_k = args.t_inf_c + 273.15
    diameter_m = args.diameter_mm * 1e-3
    conv_coeff = 4.0 * model.h / (args.rho * args.cp * diameter_m)
    rad_coeff = 4.0 * args.emissivity * args.sigma_sb / (args.rho * args.cp * diameter_m)
    residual = temp_t_c_s - model.alpha * temp_xx_c_m2 + conv_coeff * (temperature_k - t_inf_k) + rad_coeff * (
        temperature_k.pow(4) - t_inf_k**4
    )
    return torch.mean(residual.pow(2))


def compute_right_boundary_loss(model, sample_count, dataset, args, device, t_samples=None):
    if getattr(args, "right_bc_mode", DEFAULT_RIGHT_BC_MODE) == "none":
        return torch.zeros((), dtype=torch.float32, device=device)

    if t_samples is None:
        t = torch.rand(sample_count, 1, device=device)
    else:
        t = t_samples.to(device=device, dtype=torch.float32)
    x = torch.ones_like(t)
    coords = torch.cat([x, t], dim=1)
    _, _, pred_c, _, temp_x_c_m, _ = compute_temperature_and_derivatives(model, coords, dataset)
    temperature_k = pred_c + 273.15
    t_inf_k = args.t_inf_c + 273.15
    conductivity = model.alpha * args.rho * args.cp
    residual = -conductivity * temp_x_c_m - model.h * (temperature_k - t_inf_k) - args.emissivity * args.sigma_sb * (
        temperature_k.pow(4) - t_inf_k**4
    )
    return torch.mean(residual.pow(2))


def build_lr_scheduler(optimizer, args):
    if getattr(args, "lr_scheduler", "none") == "none":
        return None
    if args.lr_scheduler == "plateau":
        return torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=float(getattr(args, "lr_factor", 0.5)),
            patience=int(getattr(args, "lr_patience", 200)),
            min_lr=float(getattr(args, "min_lr", 1e-6)),
        )
    raise ValueError(f"Unsupported lr scheduler: {args.lr_scheduler}")


def load_checkpoint_into_model(model, checkpoint_path, device):
    checkpoint_path = Path(checkpoint_path).expanduser().resolve()
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if "model_state" not in checkpoint:
        raise KeyError(f"Checkpoint lacks model_state: {checkpoint_path}")
    model.load_state_dict(checkpoint["model_state"])
    return {key: value for key, value in checkpoint.items() if key != "model_state"}


def get_optimizer_lr(optimizer):
    return float(optimizer.param_groups[0]["lr"])


def prepare_training_context(dataset, args, device):
    coords = torch.tensor(np.column_stack([dataset["x_norm"], dataset["t_norm"]]), dtype=torch.float32, device=device)
    targets = torch.tensor(dataset["u_norm"].reshape(-1, 1), dtype=torch.float32, device=device)
    data_weights = torch.tensor(build_data_weights(dataset, args), dtype=torch.float32, device=device)
    time_axis_norm = ((dataset["time_axis_sec"] - dataset["t_min"]) / dataset["t_span_s"]).astype(np.float32)
    boundary_interp = build_boundary_interpolator(time_axis_norm, dataset["boundary_norm"])
    x_axis_norm = ((dataset["x_axis_heat_px"] - dataset["x_min"]) / (dataset["x_max"] - dataset["x_min"])).astype(np.float32)
    x_initial = torch.tensor(x_axis_norm.reshape(-1, 1), dtype=torch.float32, device=device)
    t_zero = torch.zeros_like(x_initial)
    initial_target = torch.tensor(
        build_initial_profile_target(
            dataset,
            initial_mode=args.initial_mode,
            t_inf_c=args.t_inf_c,
            measured_frame_count=args.measured_initial_frame_count,
        ),
        dtype=torch.float32,
        device=device,
    )
    return {
        "coords": coords,
        "targets": targets,
        "data_weights": data_weights,
        "boundary_interp": boundary_interp,
        "x_initial": x_initial,
        "t_zero": t_zero,
        "initial_target": initial_target,
    }


def sample_data_indices(args, device, context=None):
    batch_size = max(0, int(getattr(args, "data_batch_size", DEFAULT_DATA_BATCH_SIZE)))
    if batch_size <= 0 or context is None:
        return None
    data_count = int(context["coords"].shape[0])
    sample_count = min(batch_size, data_count)
    return torch.randperm(data_count, device=device)[:sample_count]


def sample_pde_points(args, device):
    if getattr(args, "pde_sampling", DEFAULT_PDE_SAMPLING) == "mixed":
        return sample_mixed_collocation_points(
            count=args.collocation_points,
            hot_x_max=getattr(args, "pde_hot_x_max", DEFAULT_PDE_HOT_X_MAX),
            early_t_max=getattr(args, "pde_early_t_max", DEFAULT_PDE_EARLY_T_MAX),
            device=device,
        )
    return sample_collocation_points(
        count=args.collocation_points,
        time_min=0.0,
        time_max=1.0,
        x_min=0.0,
        x_max=1.0,
        device=device,
    )


def sample_training_loss_points(args, device, context=None):
    boundary_count = max(64, args.collocation_points // 4)
    return {
        "data_indices": sample_data_indices(args, device, context),
        "collocation": sample_pde_points(args, device),
        "t_left": torch.rand(boundary_count, 1, device=device),
        "t_right": torch.rand(boundary_count, 1, device=device),
    }


def compute_training_losses(model, dataset, args, device, context, loss_points=None):
    if loss_points is None:
        loss_points = sample_training_loss_points(args, device)

    data_indices = loss_points.get("data_indices")
    if data_indices is None:
        data_coords = context["coords"]
        data_targets = context["targets"]
        data_weights = context["data_weights"]
    else:
        data_coords = context["coords"][data_indices]
        data_targets = context["targets"][data_indices]
        data_weights = context["data_weights"][data_indices]
    pred = model(data_coords)
    data_loss = torch.mean(data_weights * (pred - data_targets).pow(2))

    pde_loss = compute_pde_loss(model, loss_points["collocation"], dataset, args)

    t_left = loss_points["t_left"]
    x_left = torch.zeros_like(t_left)
    left_target = torch.tensor(
        context["boundary_interp"](t_left.detach().cpu().numpy().reshape(-1)),
        dtype=torch.float32,
        device=device,
    ).view(-1, 1)
    bc_left_loss = torch.mean((model(torch.cat([x_left, t_left], dim=1)) - left_target).pow(2))
    bc_right_loss = compute_right_boundary_loss(
        model,
        sample_count=max(64, args.collocation_points // 4),
        dataset=dataset,
        args=args,
        device=device,
        t_samples=loss_points["t_right"],
    )
    bc_loss = bc_left_loss + bc_right_loss

    ic_pred = model(torch.cat([context["x_initial"], context["t_zero"]], dim=1))
    ic_loss = torch.mean((ic_pred - context["initial_target"]).pow(2))

    loss = (
        args.data_weight * data_loss
        + args.pde_weight * pde_loss
        + args.bc_weight * bc_loss
        + args.ic_weight * ic_loss
    )
    return loss, data_loss, pde_loss, bc_loss, ic_loss


def make_history_row(step, stage, optimizer, model, losses):
    loss, data_loss, pde_loss, bc_loss, ic_loss = losses
    return {
        "epoch": int(step),
        "step": int(step),
        "stage": stage,
        "lr": get_optimizer_lr(optimizer),
        "loss": float(loss.item()),
        "data_loss": float(data_loss.item()),
        "pde_loss": float(pde_loss.item()),
        "bc_loss": float(bc_loss.item()),
        "ic_loss": float(ic_loss.item()),
        "alpha_m2_s": float(model.alpha.item()),
        "h_w_m2k": float(model.h.item()),
    }


def should_stop_early(history, window, loss_rel_tol, param_rel_tol):
    if window <= 0 or len(history) < window + 1:
        return False
    before = history[-window - 1]
    current = history[-1]
    loss_scale = max(abs(before["loss"]), 1e-12)
    alpha_scale = max(abs(before["alpha_m2_s"]), 1e-12)
    h_scale = max(abs(before["h_w_m2k"]), 1e-12)
    loss_rel_change = abs(before["loss"] - current["loss"]) / loss_scale
    alpha_rel_change = abs(before["alpha_m2_s"] - current["alpha_m2_s"]) / alpha_scale
    h_rel_change = abs(before["h_w_m2k"] - current["h_w_m2k"]) / h_scale
    return (
        loss_rel_change <= loss_rel_tol
        and alpha_rel_change <= param_rel_tol
        and h_rel_change <= param_rel_tol
    )


def train_model(model, dataset, args, device):
    model.to(device)
    context = prepare_training_context(dataset, args, device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = build_lr_scheduler(optimizer, args)
    history = []

    for epoch in range(args.epochs):
        optimizer.zero_grad()
        loss_points = sample_training_loss_points(args, device, context)
        losses = compute_training_losses(model, dataset, args, device, context, loss_points=loss_points)
        loss = losses[0]
        loss.backward()
        optimizer.step()
        if scheduler is not None:
            scheduler.step(float(loss.item()))

        history.append(make_history_row(epoch, "adam", optimizer, model, losses))
        if should_stop_early(
            history,
            window=int(getattr(args, "early_stop_window", 0)),
            loss_rel_tol=float(getattr(args, "early_stop_loss_rel_tol", 1e-4)),
            param_rel_tol=float(getattr(args, "early_stop_param_rel_tol", 5e-4)),
        ):
            history[-1]["early_stop"] = True
            break

    lbfgs_steps = max(0, int(getattr(args, "lbfgs_steps", 0)))
    if lbfgs_steps > 0:
        line_search = None if getattr(args, "lbfgs_line_search", "strong_wolfe") == "none" else "strong_wolfe"
        lbfgs_optimizer = torch.optim.LBFGS(
            model.parameters(),
            lr=float(getattr(args, "lbfgs_lr", 1.0)),
            max_iter=1,
            history_size=int(getattr(args, "lbfgs_history_size", 50)),
            line_search_fn=line_search,
        )
        for lbfgs_step in range(lbfgs_steps):
            loss_points = sample_training_loss_points(args, device, context)

            def closure():
                lbfgs_optimizer.zero_grad()
                losses = compute_training_losses(model, dataset, args, device, context, loss_points=loss_points)
                losses[0].backward()
                return losses[0]

            lbfgs_optimizer.step(closure)
            with torch.enable_grad():
                captured_losses = compute_training_losses(model, dataset, args, device, context, loss_points=loss_points)
            step = len(history)
            history.append(make_history_row(step, "lbfgs", lbfgs_optimizer, model, captured_losses))
            if should_stop_early(
                history,
                window=int(getattr(args, "early_stop_window", 0)),
                loss_rel_tol=float(getattr(args, "early_stop_loss_rel_tol", 1e-4)),
                param_rel_tol=float(getattr(args, "early_stop_param_rel_tol", 5e-4)),
            ):
                history[-1]["early_stop"] = True
                break

    return history


def compute_full_unweighted_data_loss(model, dataset, device):
    coords = torch.tensor(np.column_stack([dataset["x_norm"], dataset["t_norm"]]), dtype=torch.float32, device=device)
    targets = torch.tensor(dataset["u_norm"].reshape(-1, 1), dtype=torch.float32, device=device)
    with torch.no_grad():
        pred = model(coords)
    return float(torch.mean((pred - targets).pow(2)).item())


def save_training_outputs(model, dataset, history, args, output_stem, device):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / f"{output_stem}_pinn.pt"
    history_path = MODELS_DIR / f"{output_stem}_history.json"
    result_path = MODELS_DIR / f"{output_stem}_summary.json"
    pred_heatmap_path = FIGURES_DIR / f"{output_stem}_pinn_pred_heatmap.png"
    loss_curve_path = FIGURES_DIR / f"{output_stem}_pinn_loss_curve.png"
    param_curve_path = FIGURES_DIR / f"{output_stem}_pinn_alpha_h_curve.png"

    coords = torch.tensor(np.column_stack([dataset["x_norm"], dataset["t_norm"]]), dtype=torch.float32, device=device)
    with torch.no_grad():
        pred_norm = model(coords).cpu().numpy().reshape(dataset["xt_grid_c"].shape)
    pred_c = pred_norm * dataset["u_std"] + dataset["u_mean"]
    mse_c = float(np.mean((pred_c - dataset["xt_grid_c"]) ** 2))
    final_unweighted_data_loss = compute_full_unweighted_data_loss(model, dataset, device)

    alpha_m2_s = float(model.alpha.item())
    h_w_m2k = float(model.h.item())
    conductivity = convert_alpha_to_conductivity(alpha_m2_s, args.rho, args.cp)
    stage_counts = {}
    for row in history:
        stage = row.get("stage", "unknown")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    torch.save(
        {
            "model_state": model.state_dict(),
            "args": vars(args),
            "model_config": {
                "hidden_width": int(args.hidden_width),
                "hidden_depth": int(args.hidden_depth),
                "alpha_init": float(args.alpha_init),
                "h_init": float(args.h_init),
            },
            "final_alpha_m2_s": alpha_m2_s,
            "final_h_w_m2k": h_w_m2k,
            "final_thermal_conductivity_w_mk": conductivity,
        },
        model_path,
    )
    with open(history_path, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)

    summary = {
        "dataset_path": str(Path(args.dataset_path).resolve()),
        "epochs": args.epochs,
        "completed_steps": len(history),
        "stage_counts": stage_counts,
        "temperature_mse_c2": mse_c,
        "full_temperature_mse_c2": mse_c,
        "final_unweighted_data_loss": final_unweighted_data_loss,
        "output_stem": output_stem,
        "mm_per_px": dataset["mm_per_px"],
        "calibration": dataset["calibration"],
        "alpha_m2_s": alpha_m2_s,
        "h_w_m2k": h_w_m2k,
        "thermal_conductivity_w_mk": conductivity,
        "material_preset": getattr(args, "material_preset", DEFAULT_MATERIAL_PRESET),
        "expected_k_min": None if getattr(args, "expected_k_min", None) is None else float(args.expected_k_min),
        "expected_k_max": None if getattr(args, "expected_k_max", None) is None else float(args.expected_k_max),
        "rho_kg_m3": float(args.rho),
        "cp_j_kgk": float(args.cp),
        "diameter_m": float(args.diameter_mm * 1e-3),
        "emissivity": float(args.emissivity),
        "sigma_sb": float(args.sigma_sb),
        "t_inf_k": float(args.t_inf_c + 273.15),
        "initial_mode": args.initial_mode,
        "measured_initial_frame_count": int(args.measured_initial_frame_count),
        "right_bc_mode": args.right_bc_mode,
        "training_preset": getattr(args, "training_preset", DEFAULT_TRAINING_PRESET),
        "data_batch_size": int(args.data_batch_size),
        "pde_sampling": args.pde_sampling,
        "pde_hot_x_max": float(args.pde_hot_x_max),
        "pde_early_t_max": float(args.pde_early_t_max),
        "data_weighting": args.data_weighting,
        "data_weighting_config": {
            "lambda": float(args.data_weighting_lambda),
            "temp_scale_c": float(args.data_weighting_temp_scale_c),
            "max_extra": float(args.data_weighting_max_extra),
        },
        "optimizer": {
            "adam_lr": float(args.lr),
            "lr_scheduler": args.lr_scheduler,
            "lr_factor": float(args.lr_factor),
            "lr_patience": int(args.lr_patience),
            "min_lr": float(args.min_lr),
            "lbfgs_steps": int(args.lbfgs_steps),
            "lbfgs_lr": float(args.lbfgs_lr),
            "lbfgs_history_size": int(args.lbfgs_history_size),
            "lbfgs_line_search": args.lbfgs_line_search,
            "final_lr": float(history[-1]["lr"]) if history else float(args.lr),
        },
        "resume_checkpoint": str(Path(args.resume_checkpoint).resolve()) if args.resume_checkpoint else None,
        "early_stop": bool(history[-1].get("early_stop", False)) if history else False,
        "equation_used": "T_t = alpha*T_xx - 4h/(rho*cp*D)*(T-T_inf) - 4*epsilon*sigma/(rho*cp*D)*(T^4-T_inf^4)",
        "boundary_used": (
            "left Dirichlet from first rod column after support; "
            + ("no explicit right boundary (visible subdomain)" if args.right_bc_mode == "none" else "right Robin with convection and radiation")
        ),
        "initial_condition_used": (
            "ambient uniform field"
            if args.initial_mode == "ambient"
            else f"measured early-frame average over first {int(args.measured_initial_frame_count)} frames"
        ),
        "loss_model_note": "显式考虑轴向导热、侧向对流与辐射；辐射项按 Kelvin 计算。可见右边界不是物理末端时可关闭右端边界损失。",
    }
    summary["quality_checks"] = build_quality_checks(history, summary, args)
    if summary["quality_checks"]["warnings"]:
        print("结果质量警告:", "; ".join(summary["quality_checks"]["warnings"]))
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    plt.figure(figsize=(8, 5))
    steps = [row.get("step", idx) for idx, row in enumerate(history)]
    plt.plot(steps, [row["loss"] for row in history], label="total loss")
    plt.plot(steps, [row["data_loss"] for row in history], label="data")
    plt.plot(steps, [row["pde_loss"] for row in history], label="pde")
    plt.yscale("log")
    plt.xlabel("Optimizer Step")
    plt.ylabel("Loss")
    plt.title("PINN Loss Curves")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(loss_curve_path, dpi=200)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(steps, [row["alpha_m2_s"] for row in history], label="alpha (m^2/s)")
    plt.plot(steps, [row["h_w_m2k"] for row in history], label="h (W/m^2/K)")
    plt.xlabel("Optimizer Step")
    plt.ylabel("Parameter Value")
    plt.title("Learned Physical Parameters")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(param_curve_path, dpi=200)
    plt.close()

    extent = [
        float(dataset["x_axis_heat_px"][0]),
        float(dataset["x_axis_heat_px"][-1]),
        float(dataset["time_axis_sec"][-1]),
        float(dataset["time_axis_sec"][0]),
    ]
    plt.figure(figsize=(9, 5))
    plt.imshow(pred_c, aspect="auto", cmap="inferno", extent=extent)
    plt.colorbar(label="Predicted Temperature (C)")
    plt.xlabel("Distance From Heated End (px)")
    plt.ylabel("Time (s)")
    plt.title("PINN Predicted x-t Temperature Map")
    plt.tight_layout()
    plt.savefig(pred_heatmap_path, dpi=200)
    plt.close()

    return {
        "model": model_path,
        "history": history_path,
        "summary": result_path,
        "loss_curve": loss_curve_path,
        "param_curve": param_curve_path,
        "pred_heatmap": pred_heatmap_path,
    }


def main():
    args = parse_args()
    set_seed(args.seed)
    device = choose_device(args.device)
    dataset_path = Path(args.dataset_path).expanduser().resolve()
    dataset = normalize_dataset(load_xt_dataset(dataset_path), args)

    output_stem = args.output_stem or dataset_path.stem
    model = SimplePINN(
        hidden_width=args.hidden_width,
        hidden_depth=args.hidden_depth,
        alpha_init=args.alpha_init,
        h_init=args.h_init,
    )
    if args.resume_checkpoint:
        checkpoint_metadata = load_checkpoint_into_model(model, args.resume_checkpoint, device)
        print("loaded checkpoint:", Path(args.resume_checkpoint).expanduser().resolve())
        if checkpoint_metadata.get("model_config"):
            print("checkpoint model_config:", checkpoint_metadata["model_config"])

    if args.skip_train:
        print("skip_train=True，仅完成数据加载与模型初始化。")
        print("dataset:", dataset_path)
        print("xt_grid shape:", dataset["xt_grid_c"].shape)
        print("mm_per_px:", dataset["mm_per_px"])
        return

    history = train_model(model, dataset, args, device)
    output_paths = save_training_outputs(model, dataset, history, args, output_stem, device)

    print("训练完成。")
    print("最终 alpha_m2_s:", float(model.alpha.item()))
    print("最终 h_w_m2k:", float(model.h.item()))
    for label, path in output_paths.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
