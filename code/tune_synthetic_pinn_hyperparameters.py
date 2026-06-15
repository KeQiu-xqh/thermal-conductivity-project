import argparse
import copy
import csv
import json
import math
from pathlib import Path

import numpy as np

from analyze_synthetic_sweep import analyze_batch
from run_synthetic_pinn_sweep import (
    SYNTHETIC_OUTPUT_ROOT,
    SweepTask,
    load_config,
    run_task,
)


VARIANTS = {
    "baseline": {},
    "width_32": {"hidden_width": 32},
    "width_96": {"hidden_width": 96},
    "depth_3": {"hidden_depth": 3},
    "depth_5": {"hidden_depth": 5},
    "collocation_512": {"collocation_points": 512},
    "collocation_2048": {"collocation_points": 2048},
    "data_weight_5": {"data_weight": 5.0},
    "data_weight_20": {"data_weight": 20.0},
    "data_weight_20_epochs_1500": {"data_weight": 20.0, "epochs": 1500},
    "epochs_1500": {"epochs": 1500},
}


def representative_tasks(config, pinn_seeds=None):
    data_seed = int(config["coarse_scan"]["data_seed"])
    seeds = [42] if pinn_seeds is None else [int(seed) for seed in pinn_seeds]
    cases = [
        ("h59", 120.0, 70.0, 0.0),
        ("6061", 120.0, 70.0, 0.0),
        ("h59", 60.0, 50.0, 1.0),
        ("6061", 60.0, 70.0, 1.0),
    ]
    return [
        {
            "material": material,
            "time_length_s": time_s,
            "space_length_mm": length_mm,
            "noise_sigma_c": noise,
            "data_seed": data_seed,
            "pinn_seed": pinn_seed,
        }
        for material, time_s, length_mm, noise in cases
        for pinn_seed in seeds
    ]


def build_variant_config(base_config, variant_name, overrides):
    config = copy.deepcopy(base_config)
    config["pinn"].update(overrides)
    config["tuning"] = {
        "variant_name": variant_name,
        "pinn_overrides": copy.deepcopy(overrides),
    }
    return config


def estimated_cost(config):
    pinn = config["pinn"]
    width = int(pinn["hidden_width"])
    depth = int(pinn["hidden_depth"])
    return (
        int(pinn["epochs"])
        * int(pinn["collocation_points"])
        * depth
        * width
        * width
    )


def summarize_variant(variant_name, rows, config, expected_cases=None):
    errors = [float(row["k_relative_error"]) for row in rows]
    stable_cases = sum(bool(row["blind_stability_pass"]) for row in rows)
    return {
        "variant": variant_name,
        "completed_cases": len(rows),
        "expected_cases": (
            len(representative_tasks(config)) if expected_cases is None else int(expected_cases)
        ),
        "stable_cases": stable_cases,
        "stable_rate": stable_cases / len(rows) if rows else 0.0,
        "median_k_relative_error": float(np.median(errors)) if errors else math.inf,
        "max_k_relative_error": max(errors) if errors else math.inf,
        "estimated_cost": estimated_cost(config),
    }


def rank_variants(summaries):
    ranked_rows = []
    for summary in summaries:
        row = dict(summary)
        expected_cases = int(row.get("expected_cases", row["completed_cases"]))
        row["meets_accuracy_gate"] = (
            int(row["completed_cases"]) == expected_cases
            and int(row["stable_cases"]) == expected_cases
            and float(row["median_k_relative_error"]) <= 0.01
            and float(row["max_k_relative_error"]) <= 0.02
        )
        ranked_rows.append(row)
    return sorted(
        ranked_rows,
        key=lambda row: (
            int(row["completed_cases"]) != int(row.get("expected_cases", row["completed_cases"])),
            not bool(row["meets_accuracy_gate"]),
            -float(row["stable_cases"]) / max(1, int(row["completed_cases"])),
            float(row["estimated_cost"]),
            float(row["max_k_relative_error"]),
            float(row["median_k_relative_error"]),
            str(row["variant"]),
        ),
    )


def write_summary(output_dir, ranked):
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "ranking.json", "w", encoding="utf-8") as handle:
        json.dump(ranked, handle, ensure_ascii=False, indent=2)
    if ranked:
        with open(output_dir / "ranking.csv", "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(ranked[0].keys()))
            writer.writeheader()
            writer.writerows(ranked)


def parse_args():
    parser = argparse.ArgumentParser(description="Tune synthetic PINN hyperparameters.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--batch-prefix", default="hyperparam_v1")
    parser.add_argument("--variants", nargs="*", choices=sorted(VARIANTS), default=sorted(VARIANTS))
    parser.add_argument("--pinn-seeds", nargs="+", type=int, default=[42])
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    base_config = load_config(config_path)
    task_records = representative_tasks(base_config, pinn_seeds=args.pinn_seeds)
    summaries = []
    tuning_root = SYNTHETIC_OUTPUT_ROOT / args.batch_prefix
    tuning_root.mkdir(parents=True, exist_ok=True)

    for variant_name in args.variants:
        variant_config = build_variant_config(base_config, variant_name, VARIANTS[variant_name])
        variant_config_path = tuning_root / f"{variant_name}.json"
        with open(variant_config_path, "w", encoding="utf-8") as handle:
            json.dump(variant_config, handle, ensure_ascii=False, indent=2)
        batch_id = f"{args.batch_prefix}_{variant_name}"
        for record in task_records:
            task = SweepTask(**record)
            result = run_task(task, variant_config, variant_config_path, batch_id)
            print(json.dumps({"variant": variant_name, **result}, ensure_ascii=False))
        rows = analyze_batch(batch_id, variant_config)
        summaries.append(
            summarize_variant(
                variant_name,
                rows,
                variant_config,
                expected_cases=len(task_records),
            )
        )

    ranked = rank_variants(summaries)
    write_summary(tuning_root, ranked)
    print(json.dumps(ranked, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
