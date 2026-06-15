import argparse
import csv
import json
from pathlib import Path

from fit_thermal_parameters_forward import fit_dataset_file


def _resolve_dataset_path(manifest_path, dataset_path):
    dataset_path = Path(dataset_path).expanduser()
    if dataset_path.is_absolute():
        return dataset_path.resolve()
    project_root = manifest_path.parent.parent
    return (project_root / dataset_path).resolve()


def run_manifest(manifest_path, output_dir, *, force=False):
    manifest_path = Path(manifest_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    defaults = manifest.get("defaults", {})
    summary_rows = []

    for case in manifest["cases"]:
        settings = {**defaults, **case}
        case_name = settings["case_name"]
        case_output_path = output_dir / f"{case_name}.json"
        if case_output_path.exists() and not force:
            result = json.loads(case_output_path.read_text(encoding="utf-8"))
        else:
            result = fit_dataset_file(
                dataset_path=_resolve_dataset_path(
                    manifest_path,
                    settings["dataset_path"],
                ),
                output_json_path=case_output_path,
                rho=settings["rho"],
                cp=settings["cp"],
                diameter_mm=settings["diameter_mm"],
                emissivity=settings["emissivity"],
                sigma_sb=settings["sigma_sb"],
                t_inf_c=settings["t_inf_c"],
                conductivity_bounds=tuple(settings["conductivity_bounds"]),
                h_bounds=tuple(settings["h_bounds"]),
                right_bc_modes=tuple(settings["right_bc_modes"]),
                initial_frame_count=settings["initial_frame_count"],
                max_time_s=settings.get("max_time_s"),
                train_fraction=settings["train_fraction"],
                fit_time_stride=settings["fit_time_stride"],
                robust_loss=settings.get("robust_loss", "linear"),
                robust_f_scale_c=settings.get("robust_f_scale_c", 1.0),
                fixed_h=settings.get("fixed_h"),
            )

        reference_k = settings.get("reference_k_w_mk")
        relative_error_pct = None
        if reference_k is not None:
            relative_error_pct = (
                100.0
                * (result["conductivity_w_mk"] - float(reference_k))
                / float(reference_k)
            )
        summary_rows.append(
            {
                "case_name": case_name,
                "material": settings["material"],
                "dataset_path": result["dataset_path"],
                "reference_k_w_mk": reference_k,
                "conductivity_w_mk": result["conductivity_w_mk"],
                "conductivity_std_w_mk": result["conductivity_std_w_mk"],
                "relative_error_pct": relative_error_pct,
                "h_w_m2k": result["h_w_m2k"],
                "right_bc_mode": result["right_bc_mode"],
                "train_rmse_c": result["train_rmse_c"],
                "validation_rmse_c": result["validation_rmse_c"],
                "overall_rmse_c": result["overall_rmse_c"],
                "jacobian_condition_number": result["jacobian_condition_number"],
                "identifiability_warnings": ";".join(
                    result["identifiability_warnings"]
                ),
            }
        )

    summary_json_path = output_dir / "summary.json"
    summary_json_path.write_text(
        json.dumps(summary_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_csv_path = output_dir / "summary.csv"
    with summary_csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    return summary_rows


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run measured-boundary forward-PDE fits from a JSON manifest."
    )
    parser.add_argument("manifest_path")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    summary = run_manifest(
        args.manifest_path,
        args.output_dir,
        force=args.force,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
