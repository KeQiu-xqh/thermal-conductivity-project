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
    parser.add_argument("--diameter-mm", type=float, default=DEFAULT_DIAMETER_MM)
    parser.add_argument("--visible-length-mm", type=float, default=DEFAULT_VISIBLE_LENGTH_MM)
    parser.add_argument("--emissivity", type=float, default=DEFAULT_EMISSIVITY)
    parser.add_argument("--sigma-sb", type=float, default=DEFAULT_SIGMA_SB)
    parser.add_argument("--t-inf-c", type=float, default=DEFAULT_T_INF_C)
    parser.add_argument("--alpha-init", type=float, default=DEFAULT_ALPHA_INIT)
    parser.add_argument("--h-init", type=float, default=DEFAULT_H_INIT)
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
    return parser.parse_args()


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


def compute_right_boundary_loss(model, sample_count, dataset, args, device):
    if getattr(args, "right_bc_mode", DEFAULT_RIGHT_BC_MODE) == "none":
        return torch.zeros((), dtype=torch.float32, device=device)

    t = torch.rand(sample_count, 1, device=device)
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


def train_model(model, dataset, args, device):
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    coords = torch.tensor(np.column_stack([dataset["x_norm"], dataset["t_norm"]]), dtype=torch.float32, device=device)
    targets = torch.tensor(dataset["u_norm"].reshape(-1, 1), dtype=torch.float32, device=device)
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

    history = []
    for epoch in range(args.epochs):
        optimizer.zero_grad()

        pred = model(coords)
        data_loss = torch.mean((pred - targets).pow(2))

        collocation = sample_collocation_points(
            count=args.collocation_points,
            time_min=0.0,
            time_max=1.0,
            x_min=0.0,
            x_max=1.0,
            device=device,
        )
        pde_loss = compute_pde_loss(model, collocation, dataset, args)

        t_left = torch.rand(max(64, args.collocation_points // 4), 1, device=device)
        x_left = torch.zeros_like(t_left)
        left_target = torch.tensor(
            boundary_interp(t_left.detach().cpu().numpy().reshape(-1)),
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
        )
        bc_loss = bc_left_loss + bc_right_loss

        ic_pred = model(torch.cat([x_initial, t_zero], dim=1))
        ic_loss = torch.mean((ic_pred - initial_target).pow(2))

        loss = (
            args.data_weight * data_loss
            + args.pde_weight * pde_loss
            + args.bc_weight * bc_loss
            + args.ic_weight * ic_loss
        )
        loss.backward()
        optimizer.step()

        history.append(
            {
                "epoch": epoch,
                "loss": float(loss.item()),
                "data_loss": float(data_loss.item()),
                "pde_loss": float(pde_loss.item()),
                "bc_loss": float(bc_loss.item()),
                "ic_loss": float(ic_loss.item()),
                "alpha_m2_s": float(model.alpha.item()),
                "h_w_m2k": float(model.h.item()),
            }
        )

    return history


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

    alpha_m2_s = float(model.alpha.item())
    h_w_m2k = float(model.h.item())
    conductivity = convert_alpha_to_conductivity(alpha_m2_s, args.rho, args.cp)

    torch.save({"model_state": model.state_dict(), "args": vars(args)}, model_path)
    with open(history_path, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)

    summary = {
        "dataset_path": str(Path(args.dataset_path).resolve()),
        "epochs": args.epochs,
        "temperature_mse_c2": mse_c,
        "output_stem": output_stem,
        "mm_per_px": dataset["mm_per_px"],
        "calibration": dataset["calibration"],
        "alpha_m2_s": alpha_m2_s,
        "h_w_m2k": h_w_m2k,
        "thermal_conductivity_w_mk": conductivity,
        "rho_kg_m3": float(args.rho),
        "cp_j_kgk": float(args.cp),
        "diameter_m": float(args.diameter_mm * 1e-3),
        "emissivity": float(args.emissivity),
        "sigma_sb": float(args.sigma_sb),
        "t_inf_k": float(args.t_inf_c + 273.15),
        "initial_mode": args.initial_mode,
        "measured_initial_frame_count": int(args.measured_initial_frame_count),
        "right_bc_mode": args.right_bc_mode,
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
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    plt.figure(figsize=(8, 5))
    plt.plot([row["loss"] for row in history], label="total loss")
    plt.plot([row["data_loss"] for row in history], label="data")
    plt.plot([row["pde_loss"] for row in history], label="pde")
    plt.yscale("log")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("PINN Loss Curves")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(loss_curve_path, dpi=200)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot([row["alpha_m2_s"] for row in history], label="alpha (m^2/s)")
    plt.plot([row["h_w_m2k"] for row in history], label="h (W/m^2/K)")
    plt.xlabel("Epoch")
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
