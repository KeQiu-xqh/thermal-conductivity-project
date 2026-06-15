import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import solve_banded


@dataclass(frozen=True)
class RealCaseConfig:
    rho: float
    cp: float
    conductivity: float
    h: float
    diameter_mm: float
    emissivity: float
    sigma_sb: float
    t_inf_c: float
    right_bc_mode: str

    @property
    def alpha(self):
        return self.conductivity / (self.rho * self.cp)


def solve_real_boundary_forward(
    time_s,
    x_mm,
    initial_temperature_c,
    left_boundary_c,
    config,
    *,
    left_boundary_time_s=None,
):
    time_s = np.asarray(time_s, dtype=np.float64)
    x_m = np.asarray(x_mm, dtype=np.float64) * 1.0e-3
    initial_temperature_c = np.asarray(initial_temperature_c, dtype=np.float64)
    left_boundary_c = np.asarray(left_boundary_c, dtype=np.float64)
    if left_boundary_time_s is None:
        left_boundary_time_s = time_s
    else:
        left_boundary_time_s = np.asarray(left_boundary_time_s, dtype=np.float64)
    if time_s.ndim != 1 or x_m.ndim != 1:
        raise ValueError("time_s and x_mm must be one-dimensional")
    if len(time_s) < 2 or len(x_m) < 3:
        raise ValueError("At least two time points and three spatial points are required")
    if initial_temperature_c.shape != x_m.shape:
        raise ValueError("Initial temperature profile shape does not match x axis")
    if left_boundary_c.shape != left_boundary_time_s.shape:
        raise ValueError("Left boundary shape does not match its time axis")
    if (
        left_boundary_time_s[0] > time_s[0]
        or left_boundary_time_s[-1] < time_s[-1]
    ):
        raise ValueError("Left boundary time axis must cover the solver time axis")
    dx_values = np.diff(x_m)
    if not np.allclose(dx_values, dx_values[0], rtol=1e-5, atol=1e-10):
        raise ValueError("Forward solver currently requires a uniform spatial grid")
    if config.right_bc_mode not in {"none", "robin"}:
        raise ValueError(f"Unsupported right boundary mode: {config.right_bc_mode}")

    dx_m = float(dx_values[0])
    diameter_m = config.diameter_mm * 1.0e-3
    ambient_k = config.t_inf_c + 273.15
    conv_coeff = 4.0 * config.h / (config.rho * config.cp * diameter_m)
    rad_coeff = (
        4.0
        * config.emissivity
        * config.sigma_sb
        / (config.rho * config.cp * diameter_m)
    )

    def left_at(t_value):
        return float(np.interp(t_value, left_boundary_time_s, left_boundary_c))

    def side_loss(temperature_c):
        return conv_coeff * (temperature_c - config.t_inf_c) + rad_coeff * (
            (temperature_c + 273.15) ** 4 - ambient_k**4
        )

    def rhs(t_value, state):
        full_t = np.empty(x_m.size, dtype=np.float64)
        full_t[0] = left_at(t_value)
        full_t[1:] = state
        derivative = np.empty_like(state)

        interior = full_t[1:-1]
        laplacian = (full_t[:-2] - 2.0 * interior + full_t[2:]) / dx_m**2
        derivative[:-1] = config.alpha * laplacian - side_loss(interior)

        t_before = full_t[-2]
        t_right = full_t[-1]
        if config.right_bc_mode == "none":
            ghost_right = t_before
        else:
            end_flux = config.h * (t_right - config.t_inf_c) + (
                config.emissivity
                * config.sigma_sb
                * ((t_right + 273.15) ** 4 - ambient_k**4)
            )
            ghost_right = t_before - 2.0 * dx_m * end_flux / config.conductivity
        laplacian_right = (t_before - 2.0 * t_right + ghost_right) / dx_m**2
        derivative[-1] = config.alpha * laplacian_right - side_loss(t_right)
        return derivative

    def jacobian(_t_value, state):
        state_size = state.size
        jac = np.zeros((state_size, state_size), dtype=np.float64)
        temperature_k = state + 273.15
        side_loss_derivative = conv_coeff + 4.0 * rad_coeff * temperature_k**3
        diffusion = config.alpha / dx_m**2
        diagonal = -2.0 * diffusion - side_loss_derivative
        np.fill_diagonal(jac, diagonal)
        if state_size > 1:
            row = np.arange(state_size - 1)
            jac[row, row + 1] = diffusion
            jac[row + 1, row] = diffusion
            jac[-1, -2] = 2.0 * diffusion

        if config.right_bc_mode == "robin":
            t_right_k = state[-1] + 273.15
            end_flux_derivative = (
                config.h
                + 4.0 * config.emissivity * config.sigma_sb * t_right_k**3
            )
            jac[-1, -1] -= (
                2.0 * config.alpha * end_flux_derivative
                / (config.conductivity * dx_m)
            )
        return jac

    result = solve_ivp(
        rhs,
        (float(time_s[0]), float(time_s[-1])),
        initial_temperature_c[1:],
        t_eval=time_s,
        method="BDF",
        jac=jacobian,
        rtol=1.0e-7,
        atol=1.0e-9,
    )
    if not result.success:
        raise RuntimeError(f"Forward PDE solve failed: {result.message}")

    predicted = np.empty((time_s.size, x_m.size), dtype=np.float64)
    predicted[:, 0] = np.interp(time_s, left_boundary_time_s, left_boundary_c)
    predicted[:, 1:] = result.y.T
    predicted[0] = initial_temperature_c
    return predicted


def solve_real_boundary_forward_implicit(
    time_s,
    x_mm,
    initial_temperature_c,
    left_boundary_c,
    config,
    *,
    substeps=4,
    right_boundary_c=None,
):
    time_s = np.asarray(time_s, dtype=np.float64)
    x_m = np.asarray(x_mm, dtype=np.float64) * 1.0e-3
    initial_temperature_c = np.asarray(initial_temperature_c, dtype=np.float64)
    left_boundary_c = np.asarray(left_boundary_c, dtype=np.float64)
    if right_boundary_c is not None:
        right_boundary_c = np.asarray(right_boundary_c, dtype=np.float64)
    substeps = int(substeps)
    if time_s.ndim != 1 or x_m.ndim != 1:
        raise ValueError("time_s and x_mm must be one-dimensional")
    if len(time_s) < 2 or len(x_m) < 3:
        raise ValueError("At least two time points and three spatial points are required")
    if initial_temperature_c.shape != x_m.shape:
        raise ValueError("Initial temperature profile shape does not match x axis")
    if left_boundary_c.shape != time_s.shape:
        raise ValueError("Left boundary shape does not match time axis")
    if substeps < 1:
        raise ValueError("substeps must be at least one")
    if config.right_bc_mode not in {"none", "robin", "measured"}:
        raise ValueError(f"Unsupported right boundary mode: {config.right_bc_mode}")
    if config.right_bc_mode == "measured":
        if right_boundary_c is None:
            raise ValueError("right_boundary_c is required for measured mode")
        if right_boundary_c.shape != time_s.shape:
            raise ValueError("Right boundary shape does not match time axis")
    dx_values = np.diff(x_m)
    if not np.allclose(dx_values, dx_values[0], rtol=1e-5, atol=1e-10):
        raise ValueError("Forward solver currently requires a uniform spatial grid")
    if np.any(np.diff(time_s) <= 0.0):
        raise ValueError("time_s must be strictly increasing")

    dx_m = float(dx_values[0])
    diameter_m = config.diameter_mm * 1.0e-3
    ambient_k = config.t_inf_c + 273.15
    diffusion = config.alpha / dx_m**2
    conv_coeff = 4.0 * config.h / (config.rho * config.cp * diameter_m)
    rad_coeff = (
        4.0
        * config.emissivity
        * config.sigma_sb
        / (config.rho * config.cp * diameter_m)
    )

    predicted = np.empty((time_s.size, x_m.size), dtype=np.float64)
    predicted[0] = initial_temperature_c
    if config.right_bc_mode == "measured":
        state = initial_temperature_c[1:-1].copy()
    else:
        state = initial_temperature_c[1:].copy()
    state_size = state.size

    for time_index in range(1, time_s.size):
        interval_start = time_s[time_index - 1]
        interval_end = time_s[time_index]
        dt = (interval_end - interval_start) / substeps
        for substep_index in range(1, substeps + 1):
            fraction = substep_index / substeps
            left_temperature = (
                left_boundary_c[time_index - 1]
                + fraction
                * (left_boundary_c[time_index] - left_boundary_c[time_index - 1])
            )
            if config.right_bc_mode == "measured":
                right_temperature_boundary = (
                    right_boundary_c[time_index - 1]
                    + fraction
                    * (
                        right_boundary_c[time_index]
                        - right_boundary_c[time_index - 1]
                    )
                )
            temperature_k = state + 273.15
            radiation = rad_coeff * (temperature_k**4 - ambient_k**4)
            radiation_derivative = 4.0 * rad_coeff * temperature_k**3
            radiation_constant = radiation - radiation_derivative * state

            diagonal = (
                1.0 / dt
                + conv_coeff
                + radiation_derivative
                + 2.0 * diffusion
            )
            rhs = (
                state / dt
                + conv_coeff * config.t_inf_c
                - radiation_constant
            )
            lower = np.full(state_size - 1, -diffusion, dtype=np.float64)
            upper = np.full(state_size - 1, -diffusion, dtype=np.float64)
            rhs[0] += diffusion * left_temperature

            if config.right_bc_mode == "measured":
                rhs[-1] += diffusion * right_temperature_boundary
            else:
                lower[-1] = -2.0 * diffusion
            if config.right_bc_mode == "robin":
                right_temperature = state[-1]
                right_temperature_k = right_temperature + 273.15
                end_flux = config.h * (right_temperature - config.t_inf_c) + (
                    config.emissivity
                    * config.sigma_sb
                    * (right_temperature_k**4 - ambient_k**4)
                )
                end_flux_derivative = (
                    config.h
                    + 4.0
                    * config.emissivity
                    * config.sigma_sb
                    * right_temperature_k**3
                )
                end_flux_constant = (
                    end_flux - end_flux_derivative * right_temperature
                )
                end_factor = 2.0 * config.alpha / (
                    config.conductivity * dx_m
                )
                diagonal[-1] += end_factor * end_flux_derivative
                rhs[-1] -= end_factor * end_flux_constant

            banded = np.zeros((3, state_size), dtype=np.float64)
            banded[0, 1:] = upper
            banded[1] = diagonal
            banded[2, :-1] = lower
            state = solve_banded((1, 1), banded, rhs)

        predicted[time_index, 0] = left_boundary_c[time_index]
        if config.right_bc_mode == "measured":
            predicted[time_index, 1:-1] = state
            predicted[time_index, -1] = right_boundary_c[time_index]
        else:
            predicted[time_index, 1:] = state

    predicted[:, 0] = left_boundary_c
    if config.right_bc_mode == "measured":
        predicted[:, -1] = right_boundary_c
    predicted[0] = initial_temperature_c
    return predicted


def compute_residual_metrics(observed_c, predicted_c):
    observed_c = np.asarray(observed_c, dtype=np.float64)
    predicted_c = np.asarray(predicted_c, dtype=np.float64)
    if observed_c.shape != predicted_c.shape:
        raise ValueError("Observed and predicted fields must have the same shape")
    residual = observed_c - predicted_c
    x_count = residual.shape[1]
    third = max(1, x_count // 3)
    near = residual[:, :third]
    middle = residual[:, third : 2 * third]
    far = residual[:, 2 * third :]

    def rmse(values):
        return float(np.sqrt(np.mean(values**2)))

    return {
        "overall_rmse_c": rmse(residual),
        "overall_mean_bias_c": float(np.mean(residual)),
        "near_rmse_c": rmse(near),
        "middle_rmse_c": rmse(middle),
        "far_rmse_c": rmse(far),
        "near_mean_bias_c": float(np.mean(near)),
        "middle_mean_bias_c": float(np.mean(middle)),
        "far_mean_bias_c": float(np.mean(far)),
        "rmse_by_x_c": np.sqrt(np.mean(residual**2, axis=0)).tolist(),
        "mean_bias_by_x_c": np.mean(residual, axis=0).tolist(),
        "rmse_by_time_c": np.sqrt(np.mean(residual**2, axis=1)).tolist(),
        "mean_bias_by_time_c": np.mean(residual, axis=1).tolist(),
    }


def load_real_dataset(path, initial_frame_count):
    with np.load(path) as data:
        observed = data["xt_grid_c"].astype(np.float64)
        time_s = data["time_axis_sec"].astype(np.float64)
        if "x_axis_mm" in data.files:
            x_mm = data["x_axis_mm"].astype(np.float64)
        else:
            raise ValueError("Dataset must contain x_axis_mm")
        left_boundary = data["boundary_temperature_c"].astype(np.float64)
    frame_count = max(1, min(int(initial_frame_count), observed.shape[0]))
    initial = observed[:frame_count].mean(axis=0)
    initial[0] = left_boundary[0]
    return time_s, x_mm, observed, initial, left_boundary


def diagnose_pattern(metrics):
    near = metrics["near_rmse_c"]
    middle = metrics["middle_rmse_c"]
    far = metrics["far_rmse_c"]
    far_bias = metrics["far_mean_bias_c"]
    if far > 1.5 * max(near, 1.0e-9):
        direction = "experimental_far_end_hotter" if far_bias > 0 else "experimental_far_end_colder"
        return {
            "pattern": "far_end_mismatch",
            "direction": direction,
            "likely_causes": [
                "right_boundary_or_support_heat_transfer",
                "space_scale_or_effective_length_error",
                "one_dimensional_model_mismatch",
            ],
        }
    if near > 1.5 * max(far, 1.0e-9):
        return {
            "pattern": "hot_end_mismatch",
            "direction": "near_end_dominant",
            "likely_causes": [
                "hot_end_roi_or_contact_region",
                "left_boundary_not_representative_of_rod_boundary",
            ],
        }
    if max(near, middle, far) < 1.0:
        return {
            "pattern": "close_match",
            "direction": "small_residual",
            "likely_causes": [],
        }
    return {
        "pattern": "distributed_mismatch",
        "direction": "whole_domain",
        "likely_causes": [
            "time_or_space_calibration_error",
            "side_loss_mismatch",
            "one_dimensional_model_mismatch",
        ],
    }


def save_diagnostic_figure(path, time_s, x_mm, observed, predicted, metrics, title):
    residual = observed - predicted
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    extent = [float(x_mm[0]), float(x_mm[-1]), float(time_s[-1]), float(time_s[0])]
    for ax, field, label in (
        (axes[0, 0], observed, "Experiment (C)"),
        (axes[0, 1], predicted, "PDE reference (C)"),
        (axes[1, 0], residual, "Experiment - PDE (C)"),
    ):
        image = ax.imshow(field, aspect="auto", extent=extent, cmap="coolwarm")
        ax.set_title(label)
        ax.set_xlabel("x (mm)")
        ax.set_ylabel("time (s)")
        fig.colorbar(image, ax=ax)

    axes[1, 1].plot(x_mm, metrics["rmse_by_x_c"], label="RMSE")
    axes[1, 1].plot(x_mm, metrics["mean_bias_by_x_c"], label="Mean bias")
    axes[1, 1].axhline(0.0, color="black", linewidth=0.8)
    axes[1, 1].set_xlabel("x (mm)")
    axes[1, 1].set_ylabel("temperature error (C)")
    axes[1, 1].set_title("Residual by position")
    axes[1, 1].legend()
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def parse_float_list(value):
    return [float(item) for item in value.split(",") if item.strip()]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare real rod temperatures with a reference 1D PDE forward model."
    )
    parser.add_argument("dataset_path")
    parser.add_argument("--case-name", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--rho", type=float, default=8500.0)
    parser.add_argument("--cp", type=float, default=380.0)
    parser.add_argument("--reference-k", type=float, default=110.0)
    parser.add_argument("--diameter-mm", type=float, default=8.0)
    parser.add_argument("--emissivity", type=float, default=0.95)
    parser.add_argument("--sigma-sb", type=float, default=5.67e-8)
    parser.add_argument("--t-inf-c", type=float, required=True)
    parser.add_argument("--initial-frame-count", type=int, default=5)
    parser.add_argument("--h-values", default="0,5,10,15,20")
    parser.add_argument("--k-values", default="60,80,100,110,120,140")
    parser.add_argument("--right-bc-modes", default="none,robin")
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    time_s, x_mm, observed, initial, left_boundary = load_real_dataset(
        args.dataset_path,
        args.initial_frame_count,
    )

    scans = []
    fields = {}
    for conductivity in parse_float_list(args.k_values):
        for h_value in parse_float_list(args.h_values):
            for right_mode in [item.strip() for item in args.right_bc_modes.split(",") if item.strip()]:
                config = RealCaseConfig(
                    rho=args.rho,
                    cp=args.cp,
                    conductivity=conductivity,
                    h=h_value,
                    diameter_mm=args.diameter_mm,
                    emissivity=args.emissivity,
                    sigma_sb=args.sigma_sb,
                    t_inf_c=args.t_inf_c,
                    right_bc_mode=right_mode,
                )
                predicted = solve_real_boundary_forward(
                    time_s,
                    x_mm,
                    initial,
                    left_boundary,
                    config,
                )
                metrics = compute_residual_metrics(observed, predicted)
                key = (conductivity, h_value, right_mode)
                fields[key] = predicted
                scans.append(
                    {
                        "conductivity_w_mk": conductivity,
                        "h_w_m2k": h_value,
                        "right_bc_mode": right_mode,
                        **{name: value for name, value in metrics.items() if not isinstance(value, list)},
                    }
                )

    scans.sort(key=lambda row: row["overall_rmse_c"])
    reference_key = (float(args.reference_k), 10.0, "none")
    if reference_key not in fields:
        reference_key = min(
            fields,
            key=lambda key: (
                abs(key[0] - args.reference_k),
                abs(key[1] - 10.0),
                key[2] != "none",
            ),
        )
    reference_predicted = fields[reference_key]
    reference_metrics = compute_residual_metrics(observed, reference_predicted)
    best = scans[0]
    diagnosis = diagnose_pattern(reference_metrics)
    result = {
        "case_name": args.case_name,
        "dataset_path": str(Path(args.dataset_path).expanduser().resolve()),
        "reference": {
            "conductivity_w_mk": reference_key[0],
            "h_w_m2k": reference_key[1],
            "right_bc_mode": reference_key[2],
            **reference_metrics,
        },
        "best_grid_case": best,
        "diagnosis": diagnosis,
        "scan": scans,
    }
    json_path = output_dir / f"{args.case_name}_diagnosis.json"
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    figure_path = output_dir / f"{args.case_name}_diagnosis.png"
    save_diagnostic_figure(
        figure_path,
        time_s,
        x_mm,
        observed,
        reference_predicted,
        reference_metrics,
        f"{args.case_name}: reference k={reference_key[0]:g}, h={reference_key[1]:g}",
    )
    print(json_path)
    print(figure_path)
    print("reference_rmse_c:", reference_metrics["overall_rmse_c"])
    print("best_grid_case:", best)
    print("diagnosis:", diagnosis)


if __name__ == "__main__":
    main()
