import argparse
import csv
import json
from pathlib import Path

import numpy as np

from view_dat import PROJECT_ROOT, RAW_DATA_DIR, load_frames, resolve_file_path


DERIVED_DATA_DIR = PROJECT_ROOT / "data" / "derived"
DEFAULT_FPS = 6.375
DEFAULT_X_MIN = 44
DEFAULT_X_MAX = 50
DEFAULT_Y_MIN = 12
DEFAULT_Y_MAX = 38


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build ROI-based training data from a Thermal-90 raw data file."
    )
    parser.add_argument(
        "dat_path",
        nargs="?",
        help="Path to the raw thermal data file. If omitted, use the newest file in data/raw/.",
    )
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, help="Frame rate used to build the time axis.")
    parser.add_argument("--x-min", type=int, default=DEFAULT_X_MIN, help="Inclusive ROI x start.")
    parser.add_argument("--x-max", type=int, default=DEFAULT_X_MAX, help="Exclusive ROI x end.")
    parser.add_argument("--y-min", type=int, default=DEFAULT_Y_MIN, help="Inclusive ROI y start.")
    parser.add_argument("--y-max", type=int, default=DEFAULT_Y_MAX, help="Exclusive ROI y end.")
    parser.add_argument(
        "--output-dir",
        default=str(DERIVED_DATA_DIR),
        help="Directory where npz/csv/meta files will be written.",
    )
    return parser.parse_args()


def validate_roi(x_min, x_max, y_min, y_max, frame_shape):
    height, width = frame_shape
    if not (0 <= x_min < x_max <= width):
        raise ValueError(f"非法 ROI x 范围: [{x_min}, {x_max})，图像宽度为 {width}")
    if not (0 <= y_min < y_max <= height):
        raise ValueError(f"非法 ROI y 范围: [{y_min}, {y_max})，图像高度为 {height}")


def build_roi_training_data(frames_3d, fps, x_min, x_max, y_min, y_max):
    validate_roi(x_min, x_max, y_min, y_max, frames_3d.shape[1:])
    interval_sec = 1.0 / fps

    roi_frames = frames_3d[:, y_min:y_max, x_min:x_max]
    frame_count, roi_height, roi_width = roi_frames.shape

    inputs = []
    targets = []
    rows = []
    for frame_idx in range(frame_count):
        t = frame_idx * interval_sec
        frame = roi_frames[frame_idx]
        for local_y in range(roi_height):
            global_y = y_min + local_y
            for local_x in range(roi_width):
                global_x = x_min + local_x
                temperature = float(frame[local_y, local_x])
                inputs.append([global_x, global_y, t])
                targets.append(temperature)
                rows.append([frame_idx, t, global_x, global_y, local_x, local_y, temperature])

    inputs = np.array(inputs, dtype=np.float32)
    targets = np.array(targets, dtype=np.float32).reshape(-1, 1)
    return inputs, targets, rows, roi_frames


def save_outputs(output_dir, dat_path, fps, x_min, x_max, y_min, y_max, inputs, targets, rows, roi_frames):
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = dat_path.stem

    npz_path = output_dir / f"{stem}_train_data.npz"
    csv_path = output_dir / f"{stem}_train_data.csv"
    meta_path = output_dir / f"{stem}_train_meta.json"

    np.savez(npz_path, inputs=inputs, targets=targets)

    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame_idx", "time_sec", "x", "y", "roi_x", "roi_y", "temperature_c"])
        writer.writerows(rows)

    meta = {
        "source_file": str(dat_path),
        "source_parent": str(dat_path.parent),
        "fps": fps,
        "interval_sec": 1.0 / fps,
        "frame_count": int(roi_frames.shape[0]),
        "roi_shape": [int(v) for v in roi_frames.shape[1:]],
        "roi": {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "width": x_max - x_min,
            "height": y_max - y_min,
        },
        "inputs_shape": list(inputs.shape),
        "targets_shape": list(targets.shape),
        "temperature_min_c": float(targets.min()),
        "temperature_max_c": float(targets.max()),
        "temperature_mean_c": float(targets.mean()),
    }
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)

    print("已保存", npz_path)
    print("已保存", csv_path)
    print("已保存", meta_path)


def main():
    args = parse_args()
    dat_path = resolve_file_path(args.dat_path)
    if not dat_path.exists():
        raise FileNotFoundError(f"未找到输入文件: {dat_path}")
    if args.fps <= 0:
        raise ValueError("--fps 必须大于 0")

    frames_3d = load_frames(dat_path)
    inputs, targets, rows, roi_frames = build_roi_training_data(
        frames_3d,
        fps=args.fps,
        x_min=args.x_min,
        x_max=args.x_max,
        y_min=args.y_min,
        y_max=args.y_max,
    )

    print("ROI 帧形状:", roi_frames.shape)
    print("输入 shape:", inputs.shape)
    print("目标 shape:", targets.shape)
    print(f"温度范围: [{targets.min():.2f}, {targets.max():.2f}] C")

    output_dir = Path(args.output_dir).expanduser().resolve()
    save_outputs(
        output_dir,
        dat_path,
        args.fps,
        args.x_min,
        args.x_max,
        args.y_min,
        args.y_max,
        inputs,
        targets,
        rows,
        roi_frames,
    )


if __name__ == "__main__":
    main()
