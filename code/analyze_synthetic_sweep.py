import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from run_synthetic_pinn_sweep import PROJECT_ROOT, SYNTHETIC_OUTPUT_ROOT, load_config


def select_blind_estimate(summary):
    quality = summary.get("quality_checks", {})
    best = summary.get("best_physical", {})
    if quality.get("parameters_stable"):
        return (
            "final",
            float(summary["thermal_conductivity_w_mk"]),
            float(summary["alpha_m2_s"]),
            float(summary["h_w_m2k"]),
        )
    if best.get("found"):
        return (
            "stable_plateau",
            float(best["thermal_conductivity_w_mk"]),
            float(best["alpha_m2_s"]),
            float(best["h_w_m2k"]),
        )
    return (
        "final",
        float(summary["thermal_conductivity_w_mk"]),
        float(summary["alpha_m2_s"]),
        float(summary["h_w_m2k"]),
    )


def analyze_case(summary, truth, clean_xt_grid_c, pinn_seed=None, task_status="completed"):
    estimate_source, k_est, alpha_est, h_est = select_blind_estimate(summary)
    quality = summary.get("quality_checks", {})
    enough_steps = bool(quality.get("enough_steps", False))
    parameters_stable = bool(quality.get("parameters_stable", False))
    finite_losses = math.isfinite(float(summary.get("final_unweighted_data_loss", 0.0)))
    blind_stability_pass = enough_steps and parameters_stable and finite_losses
    noise_sigma = float(truth["noise_sigma_c"])
    temperature_rise = float(np.max(clean_xt_grid_c - clean_xt_grid_c[0]))
    snr = math.inf if noise_sigma == 0.0 else temperature_rise / noise_sigma
    length_m = float(truth["space_length_mm"]) * 1e-3
    return {
        "material": truth["material"],
        "time_length_s": float(truth["time_length_s"]),
        "space_length_mm": float(truth["space_length_mm"]),
        "noise_sigma_c": noise_sigma,
        "data_seed": int(truth["data_seed"]),
        "pinn_seed": None if pinn_seed is None else int(pinn_seed),
        "task_status": task_status,
        "estimate_source": estimate_source,
        "blind_stability_pass": blind_stability_pass,
        "k_est": k_est,
        "alpha_est": alpha_est,
        "h_est": h_est,
        "true_k": float(truth["true_k"]),
        "true_alpha": float(truth["true_alpha"]),
        "true_h": float(truth["true_h"]),
        "k_relative_error": abs(k_est - float(truth["true_k"])) / float(truth["true_k"]),
        "alpha_relative_error": abs(alpha_est - float(truth["true_alpha"])) / float(truth["true_alpha"]),
        "h_relative_error": abs(h_est - float(truth["true_h"])) / float(truth["true_h"]),
        "temperature_mse_c2": float(summary.get("temperature_mse_c2", math.nan)),
        "fourier_number": float(truth["true_alpha"]) * float(truth["time_length_s"]) / length_m**2,
        "snr": snr,
        "quality_warnings": "|".join(quality.get("warnings", [])),
    }


def _base_case_key(row):
    return (
        row["material"],
        float(row["time_length_s"]),
        float(row["space_length_mm"]),
        float(row["noise_sigma_c"]),
        int(row["data_seed"]),
    )


def select_refinement_cases(rows, config):
    refinement = config["refinement"]
    margin = float(refinement["near_error_threshold_margin"])
    reasons = defaultdict(set)
    valid_rows = [row for row in rows if math.isfinite(float(row["k_relative_error"]))]
    for row in valid_rows:
        error = float(row["k_relative_error"])
        key = _base_case_key(row)
        if abs(error - 0.10) <= margin:
            reasons[key].add("near_10_percent")
        if abs(error - 0.20) <= margin:
            reasons[key].add("near_20_percent")
        if not row.get("blind_stability_pass", False):
            reasons[key].add("unstable_or_rejected")

    grouped = defaultdict(list)
    for row in valid_rows:
        if row.get("blind_stability_pass", False):
            grouped[row["material"]].append(row)
    for material, material_rows in grouped.items():
        best_count = int(refinement["best_cases_per_material"])
        for row in sorted(material_rows, key=lambda item: item["k_relative_error"])[:best_count]:
            reasons[_base_case_key(row)].add("best_case")

    by_slice = defaultdict(list)
    for row in valid_rows:
        by_slice[(row["material"], row["noise_sigma_c"], row["data_seed"])].append(row)
    for slice_rows in by_slice.values():
        for first in slice_rows:
            for second in slice_rows:
                adjacent_time = first["space_length_mm"] == second["space_length_mm"] and abs(
                    first["time_length_s"] - second["time_length_s"]
                ) > 0
                adjacent_space = first["time_length_s"] == second["time_length_s"] and abs(
                    first["space_length_mm"] - second["space_length_mm"]
                ) > 0
                if not (adjacent_time or adjacent_space):
                    continue
                if (first["k_relative_error"] <= 0.20) != (second["k_relative_error"] <= 0.20):
                    reasons[_base_case_key(first)].add("success_failure_boundary")
                    reasons[_base_case_key(second)].add("success_failure_boundary")

    records = []
    for key, reason_set in sorted(reasons.items()):
        material, time_s, length_mm, noise, data_seed = key
        for pinn_seed in refinement["pinn_seeds"]:
            for reason in sorted(reason_set):
                records.append(
                    {
                        "material": material,
                        "time_length_s": time_s,
                        "space_length_mm": length_mm,
                        "noise_sigma_c": noise,
                        "data_seed": data_seed,
                        "pinn_seed": int(pinn_seed),
                        "selection_reason": reason,
                    }
                )
    unique = {}
    for record in records:
        key = (
            record["material"],
            record["time_length_s"],
            record["space_length_mm"],
            record["noise_sigma_c"],
            record["data_seed"],
            record["pinn_seed"],
        )
        if key in unique:
            previous = unique[key]["selection_reason"].split("|")
            unique[key]["selection_reason"] = "|".join(sorted(set(previous + [record["selection_reason"]])))
        else:
            unique[key] = record
    return list(unique.values())


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def analyze_batch(batch_id, config):
    batch_root = SYNTHETIC_OUTPUT_ROOT / batch_id
    rows = []
    task_root = batch_root / "tasks"
    if not task_root.exists():
        return rows
    for status_path in sorted(task_root.glob("*/status.json")):
        status = _read_json(status_path)
        if status.get("state") != "completed":
            continue
        summary_path = Path(status["summary_path"])
        truth_path = Path(status["truth_path"])
        if not summary_path.exists() or not truth_path.exists():
            continue
        summary = _read_json(summary_path)
        truth = _read_json(truth_path)
        clean_path = truth_path.with_name(truth_path.stem + "_clean.npz")
        with np.load(clean_path) as clean_data:
            clean = clean_data["clean_xt_grid_c"]
        match = re.search(r"_pinn(\d+)$", status_path.parent.name)
        pinn_seed = int(match.group(1)) if match else None
        rows.append(analyze_case(summary, truth, clean, pinn_seed=pinn_seed))
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _noise_label(value):
    return f"{float(value):g}".replace(".", "p")


def generate_figures(analysis_dir, rows, config):
    times = [float(value) for value in config["coarse_scan"]["time_lengths_s"]]
    lengths = [float(value) for value in config["coarse_scan"]["space_lengths_mm"]]
    for material in config["materials"]:
        material_rows = [row for row in rows if row["material"] == material]
        for noise in config["coarse_scan"]["noise_sigma_c"]:
            grid = np.full((len(times), len(lengths)), np.nan)
            for row in material_rows:
                if float(row["noise_sigma_c"]) != float(noise):
                    continue
                grid[times.index(row["time_length_s"]), lengths.index(row["space_length_mm"])] = row[
                    "k_relative_error"
                ]
            plt.figure(figsize=(8, 5))
            plt.imshow(grid, origin="lower", aspect="auto", vmin=0.0, vmax=0.5)
            plt.xticks(range(len(lengths)), [f"{value:g}" for value in lengths])
            plt.yticks(range(len(times)), [f"{value:g}" for value in times])
            plt.xlabel("Space length (mm)")
            plt.ylabel("Time length (s)")
            plt.colorbar(label="Relative k error")
            plt.title(f"{material.upper()} noise sigma={noise:g} C")
            plt.tight_layout()
            plt.savefig(
                analysis_dir / f"{material}_noise_{_noise_label(noise)}_k_error_heatmap.png",
                dpi=180,
            )
            plt.close()

    finite_rows = [row for row in rows if math.isfinite(row["snr"]) and row["snr"] > 0]
    if finite_rows:
        plt.figure(figsize=(7, 5))
        for material in config["materials"]:
            selected = [row for row in finite_rows if row["material"] == material]
            if selected:
                plt.scatter(
                    [row["fourier_number"] for row in selected],
                    [row["snr"] for row in selected],
                    c=[row["k_relative_error"] for row in selected],
                    label=material.upper(),
                    vmin=0,
                    vmax=0.5,
                )
        plt.xscale("log")
        plt.yscale("log")
        plt.xlabel("Fourier number")
        plt.ylabel("SNR")
        plt.legend()
        plt.colorbar(label="Relative k error")
        plt.tight_layout()
        plt.savefig(analysis_dir / "fo_snr_scatter.png", dpi=180)
        plt.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze synthetic PINN sweep results.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--batch-id", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)
    rows = analyze_batch(args.batch_id, config)
    analysis_dir = SYNTHETIC_OUTPUT_ROOT / args.batch_id / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    write_csv(analysis_dir / "case_results.csv", rows)
    refinement = select_refinement_cases(rows, config)
    with open(analysis_dir / "refinement_cases.json", "w", encoding="utf-8") as handle:
        json.dump(refinement, handle, ensure_ascii=False, indent=2)
    stable = [row for row in rows if row["blind_stability_pass"]]
    summary = {
        "completed_cases": len(rows),
        "blind_stable_cases": len(stable),
        "median_k_relative_error": (
            float(np.median([row["k_relative_error"] for row in rows])) if rows else None
        ),
        "refinement_task_count": len(refinement),
    }
    with open(analysis_dir / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    generate_figures(analysis_dir, rows, config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
