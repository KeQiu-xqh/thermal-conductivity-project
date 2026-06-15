import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from generate_synthetic_pde_data import generate_case


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "synthetic_pinn"
MODELS_DIR = PROJECT_ROOT / "outputs" / "models"


@dataclass(frozen=True)
class SweepTask:
    material: str
    time_length_s: float
    space_length_mm: float
    noise_sigma_c: float
    data_seed: int
    pinn_seed: int

    @property
    def case_id(self):
        noise = f"{self.noise_sigma_c:g}".replace(".", "p")
        return (
            f"{self.material}_t{self.time_length_s:g}_l{self.space_length_mm:g}"
            f"_n{noise}_data{self.data_seed}"
        )

    @property
    def task_id(self):
        return f"{self.case_id}_pinn{self.pinn_seed}"


def load_config(path):
    with open(Path(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def expand_coarse_tasks(config):
    scan = config["coarse_scan"]
    return [
        SweepTask(material, time_s, length_mm, noise, scan["data_seed"], pinn_seed)
        for material, time_s, length_mm, noise, pinn_seed in itertools.product(
            config["materials"],
            scan["time_lengths_s"],
            scan["space_lengths_mm"],
            scan["noise_sigma_c"],
            scan["pinn_seeds"],
        )
    ]


def stable_config_hash(config):
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def build_pinn_command(task, config, observations_path, output_stem):
    material = config["materials"][task.material]
    physics = config["physics"]
    sampling = config["sampling"]
    pinn = config["pinn"]
    return [
        sys.executable,
        str(PROJECT_ROOT / "code" / "train_pinn_1d.py"),
        str(Path(observations_path)),
        "--epochs",
        str(pinn["epochs"]),
        "--lr",
        str(pinn["lr"]),
        "--hidden-width",
        str(pinn["hidden_width"]),
        "--hidden-depth",
        str(pinn["hidden_depth"]),
        "--collocation-points",
        str(pinn["collocation_points"]),
        "--data-weight",
        str(pinn["data_weight"]),
        "--pde-weight",
        str(pinn["pde_weight"]),
        "--bc-weight",
        str(pinn["bc_weight"]),
        "--ic-weight",
        str(pinn["ic_weight"]),
        "--material-preset",
        "custom",
        "--rho",
        str(material["rho"]),
        "--cp",
        str(material["cp"]),
        "--diameter-mm",
        str(physics["diameter_mm"]),
        "--emissivity",
        str(physics["emissivity"]),
        "--sigma-sb",
        str(physics["sigma_sb"]),
        "--t-inf-c",
        str(physics["t_inf_c"]),
        "--alpha-init",
        str(pinn["alpha_init"]),
        "--h-init",
        str(pinn["h_init"]),
        "--right-bc-mode",
        str(pinn["right_bc_mode"]),
        "--initial-mode",
        str(pinn["initial_mode"]),
        "--measured-initial-frame-count",
        str(pinn["measured_initial_frame_count"]),
        "--calibration-mode",
        "manual",
        "--mm-per-px",
        str(sampling["observation_dx_mm"]),
        "--seed",
        str(task.pinn_seed),
        "--device",
        str(pinn["device"]),
        "--output-stem",
        output_stem,
    ]


def _json_value(value):
    if isinstance(value, Path):
        return str(value.resolve())
    return value


def write_status(task_dir, state, **fields):
    task_dir = Path(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / "status.json"
    temporary = task_dir / "status.json.tmp"
    payload = {
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **{key: _json_value(value) for key, value in fields.items()},
    }
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
    return path


def decide_task_action(task_dir, config_hash):
    status_path = Path(task_dir) / "status.json"
    if not status_path.exists():
        return "run"
    with open(status_path, "r", encoding="utf-8") as handle:
        status = json.load(handle)
    if status.get("config_hash") != config_hash:
        return "new_batch"
    summary_path = status.get("summary_path")
    if status.get("state") == "completed" and summary_path and Path(summary_path).exists():
        return "skip"
    return "run"


def load_refinement_tasks(path):
    with open(Path(path), "r", encoding="utf-8") as handle:
        records = json.load(handle)
    return [
        SweepTask(
            record["material"],
            record["time_length_s"],
            record["space_length_mm"],
            record["noise_sigma_c"],
            record["data_seed"],
            record["pinn_seed"],
        )
        for record in records
    ]


def run_task(task, config, config_path, batch_id):
    config_digest = stable_config_hash(config)
    task_dir = SYNTHETIC_OUTPUT_ROOT / batch_id / "tasks" / task.task_id
    action = decide_task_action(task_dir, config_digest)
    if action == "skip":
        return {"task_id": task.task_id, "state": "skipped"}
    if action == "new_batch":
        raise RuntimeError(
            f"Task {task.task_id} already exists with another config hash; use a new batch id"
        )

    observations_path, truth_path = generate_case(
        config,
        batch_id,
        task.material,
        task.time_length_s,
        task.space_length_mm,
        task.noise_sigma_c,
        task.data_seed,
    )
    output_stem = f"synthetic_{batch_id}_{task.task_id}"
    summary_path = MODELS_DIR / output_stem / f"{output_stem}_summary.json"
    log_path = task_dir / "train.log"
    command = build_pinn_command(task, config, observations_path, output_stem)
    write_status(
        task_dir,
        "running",
        config_hash=config_digest,
        config_path=Path(config_path),
        observations_path=observations_path,
        truth_path=truth_path,
        summary_path=summary_path,
        log_path=log_path,
        command=command,
    )
    task_dir.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log_handle:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    state = "completed" if completed.returncode == 0 and summary_path.exists() else "failed"
    write_status(
        task_dir,
        state,
        config_hash=config_digest,
        config_path=Path(config_path),
        observations_path=observations_path,
        truth_path=truth_path,
        summary_path=summary_path,
        log_path=log_path,
        command=command,
        return_code=completed.returncode,
    )
    return {"task_id": task.task_id, "state": state, "return_code": completed.returncode}


def parse_args():
    parser = argparse.ArgumentParser(description="Run reproducible synthetic PINN sweeps.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--mode", choices=["list", "coarse", "single", "refinement"], required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--refinement-file")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-workers", type=int, default=1)
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    tasks = expand_coarse_tasks(config)
    if args.mode == "refinement":
        if not args.refinement_file:
            raise SystemExit("--refinement-file is required for refinement mode")
        tasks = load_refinement_tasks(args.refinement_file)
    elif args.mode == "single":
        if not args.task_id:
            raise SystemExit("--task-id is required for single mode")
        tasks = [task for task in tasks if task.task_id == args.task_id]
        if not tasks:
            raise SystemExit(f"Unknown task id: {args.task_id}")

    if args.mode == "list":
        for task in tasks:
            print(task.task_id)
        print(f"total_tasks={len(tasks)}")
        return

    if args.limit is not None:
        tasks = tasks[: max(0, args.limit)]
    workers = max(1, int(args.max_workers))
    results = []
    if workers == 1:
        for task in tasks:
            result = run_task(task, config, config_path, args.batch_id)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_task, task, config, config_path, args.batch_id): task
                for task in tasks
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(json.dumps(result, ensure_ascii=False))
    failed = sum(result["state"] == "failed" for result in results)
    print(f"completed_or_skipped={len(results) - failed} failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
