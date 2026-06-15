import argparse
import csv
import json
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert an ROI y-mean CSV into the 1D PINN dataset format."
    )
    parser.add_argument("csv_path")
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--length-mm", type=float, required=True)
    parser.add_argument("--duration-sec", type=float, default=None)
    parser.add_argument("--x-start", type=int, default=1)
    parser.add_argument("--x-end", type=int, default=None)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def load_roi_ymean_csv(csv_path, x_start=1, x_end=None):
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        x_columns = [name for name in fieldnames if name.startswith("x_")]
        x_columns.sort(key=lambda name: int(name.split("_", 1)[1]))
        if not x_columns:
            raise ValueError("CSV does not contain x_1, x_2, ... temperature columns")

        end = len(x_columns) if x_end is None else int(x_end)
        selected = x_columns[int(x_start) - 1 : end]
        if len(selected) < 2:
            raise ValueError("At least two spatial temperature columns are required")

        frames = []
        frame_indices = []
        for row in reader:
            frame_indices.append(float(row["frame_index"]))
            frames.append([float(row[name]) for name in selected])

    return np.asarray(frame_indices, dtype=np.float32), np.asarray(frames, dtype=np.float32), selected


def build_dataset(frame_indices, temperatures, fps, length_mm, duration_sec=None):
    if fps <= 0:
        raise ValueError("--fps must be positive")
    if length_mm <= 0:
        raise ValueError("--length-mm must be positive")

    time_axis_sec = (frame_indices - frame_indices[0]) / float(fps)
    if duration_sec is not None:
        keep = time_axis_sec <= float(duration_sec) + 1.0e-6
        time_axis_sec = time_axis_sec[keep]
        temperatures = temperatures[keep]

    x_count = temperatures.shape[1]
    x_axis_heat_px = np.arange(x_count, dtype=np.float32)
    x_axis_mm = np.linspace(0.0, float(length_mm), x_count, dtype=np.float32)
    return {
        "xt_grid_c": temperatures.astype(np.float32),
        "time_axis_sec": time_axis_sec.astype(np.float32),
        "x_axis_heat_px": x_axis_heat_px,
        "x_axis_global_px": x_axis_heat_px.copy(),
        "x_axis_mm": x_axis_mm,
        "boundary_temperature_c": temperatures[:, 0].astype(np.float32),
        "far_end_temperature_c": temperatures[:, -1].astype(np.float32),
    }


def main():
    args = parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_indices, temperatures, selected_columns = load_roi_ymean_csv(
        csv_path,
        x_start=args.x_start,
        x_end=args.x_end,
    )
    dataset = build_dataset(
        frame_indices,
        temperatures,
        fps=args.fps,
        length_mm=args.length_mm,
        duration_sec=args.duration_sec,
    )

    stem = csv_path.stem.replace("(1)", "")
    npz_path = output_dir / f"{stem}_xt_data.npz"
    meta_path = output_dir / f"{stem}_meta.json"
    np.savez(npz_path, **dataset)

    meta = {
        "source_file": str(csv_path),
        "fps": float(args.fps),
        "frame_count": int(dataset["xt_grid_c"].shape[0]),
        "duration_sec": float(dataset["time_axis_sec"][-1]),
        "xt_grid_shape": list(dataset["xt_grid_c"].shape),
        "x_columns": [selected_columns[0], selected_columns[-1]],
        "length_mm": float(args.length_mm),
        "mm_per_px": float(args.length_mm) / float(len(selected_columns) - 1),
        "temperature_min_c": float(dataset["xt_grid_c"].min()),
        "temperature_max_c": float(dataset["xt_grid_c"].max()),
        "temperature_mean_c": float(dataset["xt_grid_c"].mean()),
    }
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)

    print(npz_path)
    print(meta_path)


if __name__ == "__main__":
    main()
