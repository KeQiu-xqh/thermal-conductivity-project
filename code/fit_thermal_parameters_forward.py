import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from diagnose_real_pde_mismatch import (
    RealCaseConfig,
    load_real_dataset,
    solve_real_boundary_forward_implicit,
)


def _rmse(observed_c, predicted_c):
    residual = np.asarray(observed_c) - np.asarray(predicted_c)
    return float(np.sqrt(np.mean(residual**2)))


def fit_forward_parameters(
    *,
    time_s,
    x_mm,
    observed_c,
    initial_temperature_c,
    left_boundary_c,
    rho,
    cp,
    diameter_mm,
    emissivity,
    sigma_sb,
    t_inf_c,
    conductivity_bounds,
    h_bounds,
    right_bc_modes=("none", "robin"),
    train_fraction=0.8,
    fit_time_stride=1,
    robust_loss="linear",
    robust_f_scale_c=1.0,
    fixed_h=None,
):
    time_s = np.asarray(time_s, dtype=np.float64)
    x_mm = np.asarray(x_mm, dtype=np.float64)
    observed_c = np.asarray(observed_c, dtype=np.float64)
    initial_temperature_c = np.asarray(initial_temperature_c, dtype=np.float64)
    left_boundary_c = np.asarray(left_boundary_c, dtype=np.float64)
    if observed_c.shape != (time_s.size, x_mm.size):
        raise ValueError("Observed field shape does not match time and space axes")
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between zero and one")
    fit_time_stride = int(fit_time_stride)
    if fit_time_stride < 1:
        raise ValueError("fit_time_stride must be at least one")

    fit_indices = np.arange(0, time_s.size, fit_time_stride, dtype=int)
    if fit_indices[-1] != time_s.size - 1:
        fit_indices = np.append(fit_indices, time_s.size - 1)
    fit_time_s = time_s[fit_indices]
    fit_observed_c = observed_c[fit_indices]
    fit_split_index = max(
        2,
        min(fit_time_s.size - 1, int(round(fit_time_s.size * train_fraction))),
    )
    fit_train_slice = slice(1, fit_split_index)
    full_split_index = max(
        2,
        min(time_s.size - 1, int(round(time_s.size * train_fraction))),
    )
    full_train_slice = slice(1, full_split_index)
    full_validation_slice = slice(full_split_index, time_s.size)
    k_low, k_high = map(float, conductivity_bounds)
    h_low, h_high = map(float, h_bounds)
    if fixed_h is None:
        initial_guess = np.array(
            [(k_low + k_high) / 2.0, (h_low + h_high) / 2.0]
        )
        lower_bounds = [k_low, h_low]
        upper_bounds = [k_high, h_high]
        parameter_scales = [k_high - k_low, h_high - h_low]
    else:
        fixed_h = float(fixed_h)
        initial_guess = np.array([(k_low + k_high) / 2.0])
        lower_bounds = [k_low]
        upper_bounds = [k_high]
        parameter_scales = [k_high - k_low]

    candidates = []
    for right_bc_mode in right_bc_modes:
        residual_columns = slice(1, -1) if right_bc_mode == "measured" else slice(1, None)
        template = RealCaseConfig(
            rho=float(rho),
            cp=float(cp),
            conductivity=float(initial_guess[0]),
            h=(
                float(initial_guess[1])
                if fixed_h is None
                else float(fixed_h)
            ),
            diameter_mm=float(diameter_mm),
            emissivity=float(emissivity),
            sigma_sb=float(sigma_sb),
            t_inf_c=float(t_inf_c),
            right_bc_mode=right_bc_mode,
        )

        def predict(parameters, prediction_time_s):
            replacement = {"conductivity": float(parameters[0])}
            if fixed_h is None:
                replacement["h"] = float(parameters[1])
            config = replace(template, **replacement)
            prediction_left_boundary_c = np.interp(
                prediction_time_s,
                time_s,
                left_boundary_c,
            )
            prediction_right_boundary_c = None
            if right_bc_mode == "measured":
                prediction_right_boundary_c = np.interp(
                    prediction_time_s,
                    time_s,
                    observed_c[:, -1],
                )
            return solve_real_boundary_forward_implicit(
                prediction_time_s,
                x_mm,
                initial_temperature_c,
                prediction_left_boundary_c,
                config,
                substeps=32,
                right_boundary_c=prediction_right_boundary_c,
            )

        def residual(parameters):
            predicted_c = predict(parameters, fit_time_s)
            return (
                fit_observed_c[fit_train_slice, residual_columns]
                - predicted_c[fit_train_slice, residual_columns]
            ).ravel()

        optimization = least_squares(
            residual,
            initial_guess,
            bounds=(lower_bounds, upper_bounds),
            x_scale="jac",
            diff_step=1.0e-3,
            loss=robust_loss,
            f_scale=float(robust_f_scale_c),
            ftol=1.0e-9,
            xtol=1.0e-9,
            gtol=1.0e-9,
            max_nfev=80,
        )
        predicted_c = predict(optimization.x, time_s)
        residual_count, parameter_count = optimization.jac.shape
        residual_variance = (
            2.0 * optimization.cost / max(1, residual_count - parameter_count)
        )
        covariance = residual_variance * np.linalg.pinv(
            optimization.jac.T @ optimization.jac
        )
        parameter_std = np.sqrt(np.maximum(0.0, np.diag(covariance)))
        scaled_jacobian = optimization.jac * np.array(
            parameter_scales,
            dtype=np.float64,
        )
        jacobian_condition_number = float(np.linalg.cond(scaled_jacobian))
        k_tolerance = max(1.0e-6, 1.0e-3 * (k_high - k_low))
        identifiability_warnings = []
        if min(
            optimization.x[0] - k_low,
            k_high - optimization.x[0],
        ) <= k_tolerance:
            identifiability_warnings.append("conductivity_at_bound")
        if fixed_h is None:
            h_tolerance = max(1.0e-6, 1.0e-3 * (h_high - h_low))
            if min(
                optimization.x[1] - h_low,
                h_high - optimization.x[1],
            ) <= h_tolerance:
                identifiability_warnings.append("h_at_bound")
        if not np.isfinite(jacobian_condition_number) or jacobian_condition_number > 1.0e4:
            identifiability_warnings.append("ill_conditioned_parameters")
        candidates.append(
            {
                "conductivity_w_mk": float(optimization.x[0]),
                "h_w_m2k": (
                    float(optimization.x[1])
                    if fixed_h is None
                    else float(fixed_h)
                ),
                "conductivity_std_w_mk": float(parameter_std[0]),
                "h_std_w_m2k": (
                    float(parameter_std[1]) if fixed_h is None else 0.0
                ),
                "jacobian_condition_number": jacobian_condition_number,
                "identifiability_warnings": identifiability_warnings,
                "right_bc_mode": right_bc_mode,
                "train_rmse_c": _rmse(
                    observed_c[full_train_slice, residual_columns],
                    predicted_c[full_train_slice, residual_columns],
                ),
                "validation_rmse_c": _rmse(
                    observed_c[full_validation_slice, residual_columns],
                    predicted_c[full_validation_slice, residual_columns],
                ),
                "overall_rmse_c": _rmse(
                    observed_c[:, residual_columns],
                    predicted_c[:, residual_columns],
                ),
                "fit_time_stride": fit_time_stride,
                "robust_loss": robust_loss,
                "robust_f_scale_c": float(robust_f_scale_c),
                "fixed_h_w_m2k": fixed_h,
                "optimizer_success": bool(optimization.success),
                "optimizer_message": optimization.message,
                "optimizer_nfev": int(optimization.nfev),
            }
        )

    candidates.sort(key=lambda row: (row["validation_rmse_c"], row["train_rmse_c"]))
    return {**candidates[0], "candidates": candidates}


def fit_dataset_file(
    *,
    dataset_path,
    output_json_path,
    rho,
    cp,
    diameter_mm,
    emissivity,
    sigma_sb,
    t_inf_c,
    conductivity_bounds,
    h_bounds,
    right_bc_modes,
    initial_frame_count,
    max_time_s,
    train_fraction,
    fit_time_stride,
    robust_loss="linear",
    robust_f_scale_c=1.0,
    fixed_h=None,
):
    dataset_path = Path(dataset_path).expanduser().resolve()
    output_json_path = Path(output_json_path).expanduser().resolve()
    time_s, x_mm, observed_c, initial_c, left_boundary_c = load_real_dataset(
        dataset_path,
        initial_frame_count,
    )
    if max_time_s is not None:
        time_mask = time_s <= float(max_time_s)
        if np.count_nonzero(time_mask) < 3:
            raise ValueError("max_time_s leaves fewer than three time points")
        time_s = time_s[time_mask]
        observed_c = observed_c[time_mask]
        left_boundary_c = left_boundary_c[time_mask]

    fit_result = fit_forward_parameters(
        time_s=time_s,
        x_mm=x_mm,
        observed_c=observed_c,
        initial_temperature_c=initial_c,
        left_boundary_c=left_boundary_c,
        rho=rho,
        cp=cp,
        diameter_mm=diameter_mm,
        emissivity=emissivity,
        sigma_sb=sigma_sb,
        t_inf_c=t_inf_c,
        conductivity_bounds=conductivity_bounds,
        h_bounds=h_bounds,
        right_bc_modes=right_bc_modes,
        train_fraction=train_fraction,
        fit_time_stride=fit_time_stride,
        robust_loss=robust_loss,
        robust_f_scale_c=robust_f_scale_c,
        fixed_h=fixed_h,
    )
    result = {
        "dataset_path": str(dataset_path),
        "sample_count": {
            "time": int(time_s.size),
            "space": int(x_mm.size),
        },
        "time_range_s": [float(time_s[0]), float(time_s[-1])],
        "space_range_mm": [float(x_mm[0]), float(x_mm[-1])],
        "fit_config": {
            "rho_kg_m3": float(rho),
            "cp_j_kgk": float(cp),
            "diameter_mm": float(diameter_mm),
            "emissivity": float(emissivity),
            "sigma_sb": float(sigma_sb),
            "t_inf_c": float(t_inf_c),
            "conductivity_bounds_w_mk": list(map(float, conductivity_bounds)),
            "h_bounds_w_m2k": list(map(float, h_bounds)),
            "right_bc_modes": list(right_bc_modes),
            "initial_frame_count": int(initial_frame_count),
            "max_time_s": None if max_time_s is None else float(max_time_s),
            "train_fraction": float(train_fraction),
            "fit_time_stride": int(fit_time_stride),
            "robust_loss": robust_loss,
            "robust_f_scale_c": float(robust_f_scale_c),
            "fixed_h_w_m2k": None if fixed_h is None else float(fixed_h),
        },
        **fit_result,
    }
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Estimate conductivity with a measured-boundary 1D forward PDE."
    )
    parser.add_argument("dataset_path")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--rho", type=float, required=True)
    parser.add_argument("--cp", type=float, required=True)
    parser.add_argument("--diameter-mm", type=float, default=8.0)
    parser.add_argument("--emissivity", type=float, default=0.95)
    parser.add_argument("--sigma-sb", type=float, default=5.67e-8)
    parser.add_argument("--t-inf-c", type=float, required=True)
    parser.add_argument("--k-min", type=float, default=20.0)
    parser.add_argument("--k-max", type=float, default=350.0)
    parser.add_argument("--h-min", type=float, default=0.0)
    parser.add_argument("--h-max", type=float, default=30.0)
    parser.add_argument("--right-bc-modes", default="none,robin")
    parser.add_argument("--initial-frame-count", type=int, default=5)
    parser.add_argument("--max-time-s", type=float, default=120.0)
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--fit-time-stride", type=int, default=1)
    parser.add_argument("--robust-loss", default="linear")
    parser.add_argument("--robust-f-scale-c", type=float, default=1.0)
    parser.add_argument("--fixed-h", type=float)
    return parser.parse_args()


def main():
    args = parse_args()
    result = fit_dataset_file(
        dataset_path=args.dataset_path,
        output_json_path=args.output_json,
        rho=args.rho,
        cp=args.cp,
        diameter_mm=args.diameter_mm,
        emissivity=args.emissivity,
        sigma_sb=args.sigma_sb,
        t_inf_c=args.t_inf_c,
        conductivity_bounds=(args.k_min, args.k_max),
        h_bounds=(args.h_min, args.h_max),
        right_bc_modes=tuple(
            item.strip()
            for item in args.right_bc_modes.split(",")
            if item.strip()
        ),
        initial_frame_count=args.initial_frame_count,
        max_time_s=args.max_time_s,
        train_fraction=args.train_fraction,
        fit_time_stride=args.fit_time_stride,
        robust_loss=args.robust_loss,
        robust_f_scale_c=args.robust_f_scale_c,
        fixed_h=args.fixed_h,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
