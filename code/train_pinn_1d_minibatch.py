"""Mini-batch data-loss variant of train_pinn_1d.py.

This script intentionally keeps the same PDE, boundary, initial condition,
model, output layout, and quality checks as train_pinn_1d.py. The only training
objective change is that the observed-data loss may use a random mini-batch per
optimizer step.
"""

import argparse
import json
from pathlib import Path
import sys

import torch

import train_pinn_1d as base


DEFAULT_DATA_BATCH_SIZE = 16384
_BASE_SAMPLE_TRAINING_LOSS_POINTS = base.sample_training_loss_points


def parse_args():
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print(
            "Mini-batch-specific option:\n"
            "  --data-batch-size DATA_BATCH_SIZE\n"
            "      Number of observed x-t samples used for data loss per step. Use 0 for full data.\n"
        )

    mini_parser = argparse.ArgumentParser(add_help=False)
    mini_parser.add_argument(
        "--data-batch-size",
        type=int,
        default=DEFAULT_DATA_BATCH_SIZE,
        help="Number of observed x-t samples used for data loss per step. Use 0 for full data.",
    )
    mini_args, remaining = mini_parser.parse_known_args()

    original_argv = sys.argv
    try:
        sys.argv = [original_argv[0], *remaining]
        args = base.parse_args()
    finally:
        sys.argv = original_argv

    args.data_batch_size = max(0, int(mini_args.data_batch_size))
    return args


def sample_training_loss_points_minibatch(args, device, context=None):
    loss_points = _BASE_SAMPLE_TRAINING_LOSS_POINTS(args, device, context)
    batch_size = max(0, int(getattr(args, "data_batch_size", 0)))
    if batch_size > 0 and context is not None:
        data_count = int(context["coords"].shape[0])
        sample_count = min(batch_size, data_count)
        loss_points["data_indices"] = torch.randint(data_count, (sample_count,), device=device)
    return loss_points


def compute_training_losses_minibatch(model, dataset, args, device, context, loss_points=None):
    if loss_points is None:
        loss_points = sample_training_loss_points_minibatch(args, device, context)

    data_indices = loss_points.get("data_indices") if loss_points is not None else None
    if data_indices is None:
        pred = model(context["coords"])
        targets = context["targets"]
    else:
        pred = model(context["coords"][data_indices])
        targets = context["targets"][data_indices]
    data_loss = torch.mean((pred - targets).pow(2))

    pde_loss = base.compute_pde_loss(model, loss_points["collocation"], dataset, args)

    t_left = loss_points["t_left"]
    x_left = torch.zeros_like(t_left)
    left_target = torch.tensor(
        context["boundary_interp"](t_left.detach().cpu().numpy().reshape(-1)),
        dtype=torch.float32,
        device=device,
    ).view(-1, 1)
    bc_left_loss = torch.mean((model(torch.cat([x_left, t_left], dim=1)) - left_target).pow(2))
    bc_right_loss = base.compute_right_boundary_loss(
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


def train_model_minibatch(model, dataset, args, device):
    original_sampler = base.sample_training_loss_points
    original_loss = base.compute_training_losses
    try:
        base.sample_training_loss_points = sample_training_loss_points_minibatch
        base.compute_training_losses = compute_training_losses_minibatch
        return base.train_model(model, dataset, args, device)
    finally:
        base.sample_training_loss_points = original_sampler
        base.compute_training_losses = original_loss


def save_training_outputs_minibatch(model, dataset, history, args, output_stem, device):
    paths = base.save_training_outputs(model, dataset, history, args, output_stem, device)
    summary_path = paths["summary"]
    with open(summary_path, "r", encoding="utf-8") as handle:
        summary = json.load(handle)

    summary["objective_mode"] = "minibatch_data_uniform_pde_unweighted"
    summary["data_batch_size"] = int(getattr(args, "data_batch_size", 0))
    summary["training_data_loss_note"] = (
        "Per-step data_loss uses a random observed-data mini-batch when data_batch_size > 0; "
        "final_unweighted_data_loss and full_temperature_mse_c2 are evaluated on the full observed grid."
    )

    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return paths


def main():
    args = parse_args()
    base.set_seed(args.seed)
    device = base.choose_device(args.device)
    dataset_path = Path(args.dataset_path).expanduser().resolve()
    dataset = base.normalize_dataset(base.load_xt_dataset(dataset_path), args)

    output_stem = args.output_stem or f"{dataset_path.stem}_minibatch"
    model = base.SimplePINN(
        hidden_width=args.hidden_width,
        hidden_depth=args.hidden_depth,
        alpha_init=args.alpha_init,
        h_init=args.h_init,
    )
    if args.resume_checkpoint:
        checkpoint_metadata = base.load_checkpoint_into_model(model, args.resume_checkpoint, device)
        print("loaded checkpoint:", Path(args.resume_checkpoint).expanduser().resolve())
        if checkpoint_metadata.get("model_config"):
            print("checkpoint model_config:", checkpoint_metadata["model_config"])

    if args.skip_train:
        print("skip_train=True, only loaded dataset and initialized model.")
        print("dataset:", dataset_path)
        print("xt_grid shape:", dataset["xt_grid_c"].shape)
        print("mm_per_px:", dataset["mm_per_px"])
        print("data_batch_size:", int(getattr(args, "data_batch_size", 0)))
        return

    history = train_model_minibatch(model, dataset, args, device)
    output_paths = save_training_outputs_minibatch(model, dataset, history, args, output_stem, device)

    print("训练完成。")
    print("最终 alpha_m2_s:", float(model.alpha.item()))
    print("最终 h_w_m2k:", float(model.h.item()))
    for label, path in output_paths.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
