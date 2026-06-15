import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import RegularGridInterpolator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DATA_ROOT = PROJECT_ROOT / "data" / "derived" / "synthetic_pinn"


@dataclass(frozen=True)
class MaterialConfig:
    name: str
    rho: float
    cp: float
    true_k: float

    @property
    def alpha(self):
        return self.true_k / (self.rho * self.cp)


@dataclass(frozen=True)
class PhysicsConfig:
    true_h: float
    diameter_mm: float
    emissivity: float
    sigma_sb: float
    t_inf_c: float
    left_delta_t_c: float
    left_tau_s: float
    domain_length_mm: float


@dataclass(frozen=True)
class SamplingConfig:
    internal_dx_mm: float
    observation_dx_mm: float
    observation_fps: float
    rtol: float
    atol: float


@dataclass(frozen=True)
class ForwardSolution:
    time_s: np.ndarray
    x_m: np.ndarray
    temperature_c: np.ndarray


def left_boundary_c(time_s, physics):
    time_s = np.asarray(time_s, dtype=np.float64)
    return physics.t_inf_c + physics.left_delta_t_c * (
        1.0 - np.exp(-time_s / physics.left_tau_s)
    )


def solve_forward_field(material, physics, sampling, duration_s):
    node_count = int(round(physics.domain_length_mm / sampling.internal_dx_mm)) + 1
    x_m = np.linspace(0.0, physics.domain_length_mm * 1e-3, node_count)
    dx_m = float(x_m[1] - x_m[0])
    diameter_m = physics.diameter_mm * 1e-3
    ambient_k = physics.t_inf_c + 273.15
    time_s = np.arange(
        0.0,
        duration_s + 0.5 / sampling.observation_fps,
        1.0 / sampling.observation_fps,
        dtype=np.float64,
    )
    initial_state = np.full(node_count - 1, physics.t_inf_c, dtype=np.float64)

    conv_coeff = 4.0 * physics.true_h / (material.rho * material.cp * diameter_m)
    rad_coeff = (
        4.0
        * physics.emissivity
        * physics.sigma_sb
        / (material.rho * material.cp * diameter_m)
    )

    def rhs(time_value, state):
        full_t = np.empty(node_count, dtype=np.float64)
        full_t[0] = float(left_boundary_c(time_value, physics))
        full_t[1:] = state
        derivative = np.empty_like(state)

        interior = full_t[1:-1]
        laplacian = (full_t[:-2] - 2.0 * interior + full_t[2:]) / dx_m**2
        side_loss = conv_coeff * (interior - physics.t_inf_c) + rad_coeff * (
            (interior + 273.15) ** 4 - ambient_k**4
        )
        derivative[:-1] = material.alpha * laplacian - side_loss

        t_before = full_t[-2]
        t_right = full_t[-1]
        end_flux = physics.true_h * (t_right - physics.t_inf_c) + (
            physics.emissivity
            * physics.sigma_sb
            * ((t_right + 273.15) ** 4 - ambient_k**4)
        )
        ghost_right = t_before - 2.0 * dx_m * end_flux / material.true_k
        laplacian_right = (t_before - 2.0 * t_right + ghost_right) / dx_m**2
        side_loss_right = conv_coeff * (t_right - physics.t_inf_c) + rad_coeff * (
            (t_right + 273.15) ** 4 - ambient_k**4
        )
        derivative[-1] = material.alpha * laplacian_right - side_loss_right
        return derivative

    result = solve_ivp(
        rhs,
        (0.0, float(duration_s)),
        initial_state,
        t_eval=time_s,
        method="BDF",
        rtol=sampling.rtol,
        atol=sampling.atol,
    )
    if not result.success:
        raise RuntimeError(f"Forward PDE solve failed: {result.message}")

    temperature_c = np.empty((time_s.size, node_count), dtype=np.float64)
    temperature_c[:, 0] = left_boundary_c(time_s, physics)
    temperature_c[:, 1:] = result.y.T
    if not np.isfinite(temperature_c).all():
        raise RuntimeError("Forward PDE solve produced non-finite temperatures")
    lower = physics.t_inf_c - 1e-6
    upper = physics.t_inf_c + physics.left_delta_t_c + 1e-3
    if temperature_c.min() < lower or temperature_c.max() > upper:
        raise RuntimeError("Forward PDE solve produced temperatures outside physical bounds")
    return ForwardSolution(time_s=time_s, x_m=x_m, temperature_c=temperature_c)


def build_observation_dataset(
    solution,
    duration_s,
    length_mm,
    noise_sigma_c,
    seed,
    observation_dx_mm,
    fps,
):
    if duration_s > solution.time_s[-1] + 1e-9:
        raise ValueError("Requested duration exceeds cached forward solution")
    if length_mm > solution.x_m[-1] * 1000.0 + 1e-9:
        raise ValueError("Requested length exceeds cached forward solution")
    time_axis = np.arange(0.0, duration_s + 0.5 / fps, 1.0 / fps)
    x_axis_mm = np.arange(0.0, length_mm + 0.5 * observation_dx_mm, observation_dx_mm)
    time_mesh, x_mesh = np.meshgrid(time_axis, x_axis_mm, indexing="ij")
    query = np.column_stack([time_mesh.ravel(), x_mesh.ravel()])
    interpolator = RegularGridInterpolator(
        (solution.time_s, solution.x_m * 1000.0),
        solution.temperature_c,
        bounds_error=True,
    )
    clean = interpolator(query).reshape(time_axis.size, x_axis_mm.size)
    rng = np.random.default_rng(int(seed))
    noisy = clean + rng.normal(0.0, float(noise_sigma_c), clean.shape)
    noisy[:, 0] = clean[:, 0]
    return {
        "xt_grid_c": noisy.astype(np.float32),
        "clean_xt_grid_c": clean.astype(np.float32),
        "time_axis_sec": time_axis.astype(np.float32),
        "x_axis_heat_px": np.arange(x_axis_mm.size, dtype=np.float32),
        "x_axis_mm": x_axis_mm.astype(np.float32),
        "boundary_temperature_c": clean[:, 0].astype(np.float32),
        "far_end_temperature_c": noisy[:, -1].astype(np.float32),
    }


def write_synthetic_case(case_root, dataset, truth):
    case_root = Path(case_root)
    case_root.mkdir(parents=True, exist_ok=True)
    observation_path = case_root / "observations.npz"
    truth_path = case_root / "truth.json"
    clean_path = case_root / "clean_observations.npz"
    np.savez_compressed(
        observation_path,
        xt_grid_c=dataset["xt_grid_c"],
        time_axis_sec=dataset["time_axis_sec"],
        x_axis_heat_px=dataset["x_axis_heat_px"],
        x_axis_mm=dataset["x_axis_mm"],
        boundary_temperature_c=dataset["boundary_temperature_c"],
        far_end_temperature_c=dataset["far_end_temperature_c"],
    )
    np.savez_compressed(clean_path, clean_xt_grid_c=dataset["clean_xt_grid_c"])
    with open(truth_path, "w", encoding="utf-8") as handle:
        json.dump(truth, handle, ensure_ascii=False, indent=2)
    return observation_path, truth_path


def load_benchmark_config(path):
    with open(Path(path), "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def config_hash(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def configs_from_dict(config, material_name):
    material_data = config["materials"][material_name]
    material = MaterialConfig(material_name, **material_data)
    physics = PhysicsConfig(**config["physics"])
    sampling = SamplingConfig(**config["sampling"])
    return material, physics, sampling


def generate_case(config, batch_id, material_name, duration_s, length_mm, noise_sigma_c, seed):
    material, physics, sampling = configs_from_dict(config, material_name)
    forward_payload = {
        "material": asdict(material),
        "physics": asdict(physics),
        "sampling": asdict(sampling),
        "duration_s": max(config["coarse_scan"]["time_lengths_s"]),
    }
    forward_hash = config_hash(forward_payload)
    batch_root = SYNTHETIC_DATA_ROOT / batch_id
    cache_dir = batch_root / "forward_fields"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{material_name}_{forward_hash}.npz"
    if cache_path.exists():
        with np.load(cache_path) as cached:
            solution = ForwardSolution(
                time_s=cached["time_s"],
                x_m=cached["x_m"],
                temperature_c=cached["temperature_c"],
            )
    else:
        solution = solve_forward_field(
            material,
            physics,
            sampling,
            max(config["coarse_scan"]["time_lengths_s"]),
        )
        np.savez_compressed(
            cache_path,
            time_s=solution.time_s,
            x_m=solution.x_m,
            temperature_c=solution.temperature_c,
        )

    dataset = build_observation_dataset(
        solution,
        float(duration_s),
        float(length_mm),
        float(noise_sigma_c),
        int(seed),
        sampling.observation_dx_mm,
        sampling.observation_fps,
    )
    noise_label = f"{float(noise_sigma_c):g}".replace(".", "p")
    case_id = (
        f"{material_name}_t{float(duration_s):g}_l{float(length_mm):g}"
        f"_n{noise_label}_data{int(seed)}"
    )
    truth = {
        "case_id": case_id,
        "material": material_name,
        "true_k": material.true_k,
        "true_alpha": material.alpha,
        "true_h": physics.true_h,
        "rho": material.rho,
        "cp": material.cp,
        "time_length_s": float(duration_s),
        "space_length_mm": float(length_mm),
        "noise_sigma_c": float(noise_sigma_c),
        "data_seed": int(seed),
        "forward_config_hash": forward_hash,
    }
    case_root = batch_root / "datasets" / case_id
    observation_path, _ = write_synthetic_case(case_root, dataset, truth)
    truth_dir = batch_root / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    truth_path = truth_dir / f"{case_id}.json"
    clean_path = truth_dir / f"{case_id}_clean.npz"
    with open(truth_path, "w", encoding="utf-8") as handle:
        json.dump(truth, handle, ensure_ascii=False, indent=2)
    np.savez_compressed(clean_path, clean_xt_grid_c=dataset["clean_xt_grid_c"])
    return observation_path, truth_path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a synthetic 1D heat-conduction observation dataset.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--material", required=True, choices=["h59", "6061"])
    parser.add_argument("--duration-s", required=True, type=float)
    parser.add_argument("--length-mm", required=True, type=float)
    parser.add_argument("--noise-sigma-c", required=True, type=float)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--batch-id", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_benchmark_config(args.config)
    observation_path, truth_path = generate_case(
        config,
        args.batch_id,
        args.material,
        args.duration_s,
        args.length_mm,
        args.noise_sigma_c,
        args.seed,
    )
    print("observations:", observation_path.resolve())
    print("truth:", truth_path.resolve())


if __name__ == "__main__":
    main()
