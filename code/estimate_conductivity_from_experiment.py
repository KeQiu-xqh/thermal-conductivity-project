import argparse
import json
from pathlib import Path

import numpy as np

from diagnose_real_pde_mismatch import load_real_dataset
from fit_thermal_parameters_forward import fit_forward_parameters


MATERIAL_PRESETS = {
    "h59": {
        "rho": 8500.0,
        "cp": 380.0,
        "expected_k_range": (80.0, 140.0),
    },
    "6061": {
        "rho": 2700.0,
        "cp": 900.0,
        "expected_k_range": (130.0, 190.0),
    },
}


def estimate_heated_end_windows(
    *,
    time_s,
    x_mm,
    observed_c,
    rho,
    cp,
    t_inf_c,
    expected_k_range,
    window_lengths_mm=(30.0, 40.0, 50.0, 60.0),
    fixed_h=10.0,
    diameter_mm=8.0,
    emissivity=0.95,
    sigma_sb=5.67e-8,
    initial_frame_count=5,
    train_fraction=0.7,
    conductivity_bounds=(20.0, 350.0),
    max_validation_rmse_c=1.0,
):
    time_s = np.asarray(time_s, dtype=np.float64)
    x_mm = np.asarray(x_mm, dtype=np.float64)
    observed_c = np.asarray(observed_c, dtype=np.float64)
    expected_low, expected_high = map(float, expected_k_range)
    candidates = []

    for requested_length_mm in window_lengths_mm:
        selected_columns = x_mm <= float(requested_length_mm)
        if np.count_nonzero(selected_columns) < 8:
            continue
        window_x_mm = x_mm[selected_columns]
        window_observed_c = observed_c[:, selected_columns]
        frame_count = max(
            1,
            min(int(initial_frame_count), window_observed_c.shape[0]),
        )
        initial_c = window_observed_c[:frame_count].mean(axis=0)
        left_boundary_c = window_observed_c[:, 0].copy()
        initial_c[0] = left_boundary_c[0]
        fit = fit_forward_parameters(
            time_s=time_s,
            x_mm=window_x_mm - window_x_mm[0],
            observed_c=window_observed_c,
            initial_temperature_c=initial_c,
            left_boundary_c=left_boundary_c,
            rho=rho,
            cp=cp,
            diameter_mm=diameter_mm,
            emissivity=emissivity,
            sigma_sb=sigma_sb,
            t_inf_c=t_inf_c,
            conductivity_bounds=conductivity_bounds,
            h_bounds=(0.0, 30.0),
            right_bc_modes=("measured",),
            train_fraction=train_fraction,
            fixed_h=fixed_h,
        )
        conductivity = fit["conductivity_w_mk"]
        accepted = (
            expected_low <= conductivity <= expected_high
            and "conductivity_at_bound" not in fit["identifiability_warnings"]
            and fit["validation_rmse_c"] <= max_validation_rmse_c
        )
        candidates.append(
            {
                "requested_window_length_mm": float(requested_length_mm),
                "window_end_mm": float(window_x_mm[-1] - window_x_mm[0]),
                "space_point_count": int(window_x_mm.size),
                "accepted": accepted,
                **{
                    key: fit[key]
                    for key in (
                        "conductivity_w_mk",
                        "conductivity_std_w_mk",
                        "h_w_m2k",
                        "train_rmse_c",
                        "validation_rmse_c",
                        "overall_rmse_c",
                        "jacobian_condition_number",
                        "identifiability_warnings",
                    )
                },
            }
        )

    accepted_candidates = [row for row in candidates if row["accepted"]]
    accepted_candidates.sort(
        key=lambda row: (
            row["validation_rmse_c"],
            row["conductivity_std_w_mk"],
        )
    )
    selected = accepted_candidates[0] if accepted_candidates else None
    warnings = []
    if selected is None:
        warnings.append("no_physical_window_candidate")
    if len(accepted_candidates) == 1:
        warnings.append("single_physical_window_candidate")
    if len(accepted_candidates) >= 2:
        accepted_k = np.array(
            [row["conductivity_w_mk"] for row in accepted_candidates],
            dtype=np.float64,
        )
        relative_range = float(
            (accepted_k.max() - accepted_k.min()) / max(np.median(accepted_k), 1.0e-9)
        )
        if relative_range > 0.2:
            warnings.append("physical_window_candidates_not_stable")

    return {
        "expected_k_range_w_mk": [expected_low, expected_high],
        "fixed_h_w_m2k": float(fixed_h),
        "selected": selected,
        "candidates": candidates,
        "accepted_candidate_count": len(accepted_candidates),
        "recommended_for_reporting": selected is not None,
        "warnings": warnings,
    }


def estimate_dataset(
    *,
    dataset_path,
    output_json_path,
    material,
    t_inf_c,
    max_time_s=120.0,
    window_lengths_mm=(30.0, 40.0, 50.0, 60.0),
    fixed_h=10.0,
):
    material_key = material.lower()
    if material_key not in MATERIAL_PRESETS:
        raise ValueError(f"Unsupported material: {material}")
    preset = MATERIAL_PRESETS[material_key]
    dataset_path = Path(dataset_path).expanduser().resolve()
    time_s, x_mm, observed_c, _initial_c, _left_boundary_c = load_real_dataset(
        dataset_path,
        initial_frame_count=5,
    )
    if max_time_s is not None:
        mask = time_s <= float(max_time_s)
        time_s = time_s[mask]
        observed_c = observed_c[mask]
    result = estimate_heated_end_windows(
        time_s=time_s,
        x_mm=x_mm,
        observed_c=observed_c,
        rho=preset["rho"],
        cp=preset["cp"],
        t_inf_c=t_inf_c,
        expected_k_range=preset["expected_k_range"],
        window_lengths_mm=window_lengths_mm,
        fixed_h=fixed_h,
    )
    result = {
        "dataset_path": str(dataset_path),
        "material": material_key,
        "t_inf_c": float(t_inf_c),
        "max_time_s": None if max_time_s is None else float(max_time_s),
        **result,
    }
    output_json_path = Path(output_json_path).expanduser().resolve()
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Estimate H59 or 6061 conductivity from heated-end subdomains."
    )
    parser.add_argument("dataset_path")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--material", choices=sorted(MATERIAL_PRESETS), required=True)
    parser.add_argument("--t-inf-c", type=float, required=True)
    parser.add_argument("--max-time-s", type=float, default=120.0)
    parser.add_argument("--window-lengths-mm", default="30,40,50,60")
    parser.add_argument("--fixed-h", type=float, default=10.0)
    return parser.parse_args()


def main():
    args = parse_args()
    result = estimate_dataset(
        dataset_path=args.dataset_path,
        output_json_path=args.output_json,
        material=args.material,
        t_inf_c=args.t_inf_c,
        max_time_s=args.max_time_s,
        window_lengths_mm=tuple(
            float(item)
            for item in args.window_lengths_mm.split(",")
            if item.strip()
        ),
        fixed_h=args.fixed_h,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
