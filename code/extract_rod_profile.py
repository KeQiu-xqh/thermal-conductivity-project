import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from view_dat import PROJECT_ROOT, load_frames, resolve_file_path


DERIVED_DATA_DIR = PROJECT_ROOT / "data" / "derived"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
DEFAULT_FPS = 7.0
DEFAULT_DATA_START_FRAME = 250
DEFAULT_COLD_FRAME_COUNT = 30
DEFAULT_HOT_FRAME_COUNT = 100
DEFAULT_BAND_HALF_HEIGHT = 2
DEFAULT_MIN_DELTA_C = 3.0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract rod-focused x,y,t and x,t data for PINN preparation."
    )
    parser.add_argument(
        "dat_path",
        nargs="?",
        help="Path to the raw thermal data file. If omitted, use the newest file in data/raw/.",
    )
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument(
        "--data-start-frame",
        type=int,
        default=DEFAULT_DATA_START_FRAME,
        help="First frame kept in the exported PINN dataset.",
    )
    parser.add_argument(
        "--data-end-frame",
        type=int,
        default=None,
        help="Exclusive end frame kept in the exported PINN dataset. Defaults to the last frame.",
    )
    parser.add_argument(
        "--cold-frame-count",
        type=int,
        default=DEFAULT_COLD_FRAME_COUNT,
        help="Number of early frames used to estimate the cold baseline when auto-detecting the rod ROI.",
    )
    parser.add_argument(
        "--hot-frame-count",
        type=int,
        default=DEFAULT_HOT_FRAME_COUNT,
        help="Number of late frames used to estimate the warmed state when auto-detecting the rod ROI.",
    )
    parser.add_argument(
        "--search-y-max",
        type=int,
        default=None,
        help="Only search rod center rows above this y index. Defaults to the upper 65%% of the frame.",
    )
    parser.add_argument("--band-half-height", type=int, default=DEFAULT_BAND_HALF_HEIGHT)
    parser.add_argument("--min-delta-c", type=float, default=DEFAULT_MIN_DELTA_C)
    parser.add_argument("--x-min", type=int, default=None, help="Optional manual ROI x start.")
    parser.add_argument("--x-max", type=int, default=None, help="Optional manual ROI x end (exclusive).")
    parser.add_argument("--y-min", type=int, default=None, help="Optional manual ROI y start.")
    parser.add_argument("--y-max", type=int, default=None, help="Optional manual ROI y end (exclusive).")
    parser.add_argument(
        "--heat-side",
        choices=["auto", "left", "right"],
        default="auto",
        help="Heated boundary side. Auto compares left and right edge temperatures.",
    )
    parser.add_argument(
        "--mm-per-px",
        type=float,
        default=None,
        help="Optional physical scale used to convert the axial coordinate from pixels to millimetres.",
    )
    parser.add_argument("--output-dir", default=str(DERIVED_DATA_DIR))
    parser.add_argument("--figure-dir", default=str(FIGURES_DIR))
    return parser.parse_args()


def smooth_signal(values, window):
    window = max(1, int(window))
    if window == 1 or len(values) < window:
        return values.copy()
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(values, kernel, mode="same")


def close_small_gaps(mask, max_gap=2):
    mask = np.array(mask, dtype=bool)
    gap_start = None
    for idx, value in enumerate(mask):
        if value:
            if gap_start is not None and idx - gap_start <= max_gap:
                mask[gap_start:idx] = True
            gap_start = None
        elif gap_start is None:
            gap_start = idx
    return mask


def longest_true_run(mask):
    best_start = 0
    best_end = 0
    run_start = None
    for idx, value in enumerate(mask):
        if value and run_start is None:
            run_start = idx
        elif not value and run_start is not None:
            if idx - run_start > best_end - best_start:
                best_start, best_end = run_start, idx
            run_start = None
    if run_start is not None and len(mask) - run_start > best_end - best_start:
        best_start, best_end = run_start, len(mask)
    return best_start, best_end


def infer_heat_side(hot_mean):
    width = hot_mean.shape[1]
    edge_width = max(4, width // 6)
    left_score = float(hot_mean[:, :edge_width].mean())
    right_score = float(hot_mean[:, -edge_width:].mean())
    return "left" if left_score >= right_score else "right"


def validate_roi(roi, frame_shape):
    height, width = frame_shape
    x_min = roi["x_min"]
    x_max = roi["x_max"]
    y_min = roi["y_min"]
    y_max = roi["y_max"]
    if not (0 <= x_min < x_max <= width):
        raise ValueError(f"非法 ROI x 范围: [{x_min}, {x_max})，图像宽度为 {width}")
    if not (0 <= y_min < y_max <= height):
        raise ValueError(f"非法 ROI y 范围: [{y_min}, {y_max})，图像高度为 {height}")


def auto_detect_rod_roi(
    frames_3d,
    start_frame=0,
    cold_frame_count=DEFAULT_COLD_FRAME_COUNT,
    hot_frame_count=DEFAULT_HOT_FRAME_COUNT,
    search_y_max=None,
    band_half_height=DEFAULT_BAND_HALF_HEIGHT,
    min_delta_c=DEFAULT_MIN_DELTA_C,
):
    frame_count, height, width = frames_3d.shape
    if frame_count < 2:
        raise ValueError("至少需要两帧数据才能自动检测 ROI")
    if start_frame < 0 or start_frame >= frame_count:
        raise ValueError(f"start_frame 超出范围: {start_frame}")

    cold_end = min(frame_count, start_frame + max(1, cold_frame_count))
    hot_start = max(cold_end, frame_count - max(1, hot_frame_count))
    cold_mean = frames_3d[start_frame:cold_end].mean(axis=0)
    hot_mean = frames_3d[hot_start:frame_count].mean(axis=0)
    delta = hot_mean - cold_mean

    if search_y_max is None:
        search_y_max = max(1, int(height * 0.65))
    search_y_max = min(height, max(1, search_y_max))

    row_scores = delta[:search_y_max].mean(axis=1)
    row_scores_smooth = smooth_signal(row_scores, window=5)
    y_center = int(np.argmax(row_scores_smooth))
    band_half_height = max(1, int(band_half_height))
    y_min = max(0, y_center - band_half_height)
    y_max = min(height, y_center + band_half_height)

    band_delta = delta[y_min:y_max].mean(axis=0)
    band_hot = hot_mean[y_min:y_max].mean(axis=0)
    upper_bg_y_min = max(0, y_min - 6)
    upper_bg_y_max = max(upper_bg_y_min + 1, y_min)
    upper_background = hot_mean[upper_bg_y_min:upper_bg_y_max].mean(axis=0)

    contrast_mask = (band_hot - upper_background) > float(min_delta_c)
    candidate_mask = close_small_gaps((band_delta > float(min_delta_c)) & contrast_mask, max_gap=2)
    x_min, x_max = longest_true_run(candidate_mask)
    if x_max - x_min < 8:
        candidate_mask = close_small_gaps(band_delta > float(min_delta_c), max_gap=2)
        x_min, x_max = longest_true_run(candidate_mask)
    if x_max - x_min < 8:
        raise ValueError("自动检测到的棒身 ROI 过窄，请手动指定 ROI 或调整阈值")

    return {
        "x_min": int(x_min),
        "x_max": int(x_max),
        "y_min": int(y_min),
        "y_max": int(y_max),
        "y_center": int(y_center),
        "heat_side": infer_heat_side(hot_mean),
        "cold_frame_range": [int(start_frame), int(cold_end)],
        "hot_frame_range": [int(hot_start), int(frame_count)],
        "min_delta_c": float(min_delta_c),
    }


def normalize_roi(roi, frame_shape, heat_side_override="auto"):
    roi = dict(roi)
    validate_roi(roi, frame_shape)
    if heat_side_override != "auto":
        roi["heat_side"] = heat_side_override
    if roi.get("heat_side") not in {"left", "right"}:
        raise ValueError("heat_side 必须为 left 或 right")
    return roi


def build_rod_datasets(frames_3d, fps, roi, start_frame=0, end_frame=None, mm_per_px=None):
    if fps <= 0:
        raise ValueError("fps 必须大于 0")
    frame_count = frames_3d.shape[0]
    if start_frame < 0 or start_frame >= frame_count:
        raise ValueError(f"start_frame 超出范围: {start_frame}")
    if end_frame is None:
        end_frame = frame_count
    if end_frame <= start_frame or end_frame > frame_count:
        raise ValueError(f"end_frame 超出范围: {end_frame}")

    roi = normalize_roi(roi, frames_3d.shape[1:], heat_side_override=roi["heat_side"])
    roi_frames = frames_3d[start_frame:end_frame, roi["y_min"] : roi["y_max"], roi["x_min"] : roi["x_max"]]
    global_x = np.arange(roi["x_min"], roi["x_max"], dtype=np.float32)
    global_y = np.arange(roi["y_min"], roi["y_max"], dtype=np.float32)

    if roi["heat_side"] == "right":
        roi_frames = roi_frames[:, :, ::-1]
        global_x_oriented = global_x[::-1]
    else:
        global_x_oriented = global_x.copy()

    local_frame_count, roi_height, roi_width = roi_frames.shape
    time_axis_sec = np.arange(local_frame_count, dtype=np.float32) / float(fps)
    frame_indices = np.arange(start_frame, end_frame, dtype=np.int32)
    x_axis_heat_px = np.arange(roi_width, dtype=np.float32)
    x_axis_mm = None if mm_per_px is None else x_axis_heat_px * float(mm_per_px)

    xyt_inputs = []
    xyt_targets = []
    xyt_rows = []
    for frame_idx, source_frame_idx in enumerate(frame_indices):
        t_sec = float(time_axis_sec[frame_idx])
        for local_y, y_global in enumerate(global_y):
            for local_x, x_global in enumerate(global_x_oriented):
                temperature = float(roi_frames[frame_idx, local_y, local_x])
                x_heat_px = float(x_axis_heat_px[local_x])
                xyt_inputs.append([x_heat_px, float(y_global), t_sec])
                xyt_targets.append(temperature)
                xyt_rows.append(
                    [
                        int(source_frame_idx),
                        t_sec,
                        x_heat_px,
                        float(x_global),
                        float(y_global),
                        int(local_x),
                        int(local_y),
                        temperature,
                    ]
                )

    xyt_inputs = np.array(xyt_inputs, dtype=np.float32)
    xyt_targets = np.array(xyt_targets, dtype=np.float32).reshape(-1, 1)

    xt_grid_c = roi_frames.mean(axis=1)
    xt_inputs = []
    xt_targets = []
    xt_rows = []
    for frame_idx, source_frame_idx in enumerate(frame_indices):
        t_sec = float(time_axis_sec[frame_idx])
        for local_x, x_global in enumerate(global_x_oriented):
            temperature = float(xt_grid_c[frame_idx, local_x])
            x_heat_px = float(x_axis_heat_px[local_x])
            xt_inputs.append([x_heat_px, t_sec])
            xt_targets.append(temperature)
            xt_rows.append([int(source_frame_idx), t_sec, x_heat_px, float(x_global), int(local_x), temperature])

    xt_inputs = np.array(xt_inputs, dtype=np.float32)
    xt_targets = np.array(xt_targets, dtype=np.float32).reshape(-1, 1)

    return {
        "roi_frames": roi_frames,
        "frame_indices": frame_indices,
        "time_axis_sec": time_axis_sec,
        "x_axis_heat_px": x_axis_heat_px,
        "x_axis_mm": x_axis_mm,
        "x_axis_global_px": global_x_oriented,
        "y_axis_global_px": global_y,
        "xyt_inputs": xyt_inputs,
        "xyt_targets": xyt_targets,
        "xyt_rows": xyt_rows,
        "xt_grid_c": xt_grid_c,
        "xt_inputs": xt_inputs,
        "xt_targets": xt_targets,
        "xt_rows": xt_rows,
        "boundary_temperature_c": xt_grid_c[:, 0],
        "far_end_temperature_c": xt_grid_c[:, -1],
    }


def save_outputs(output_dir, dat_path, fps, roi, datasets, metadata_extra=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = dat_path.stem

    xyt_npz_path = output_dir / f"{stem}_rod_xyt_data.npz"
    xyt_csv_path = output_dir / f"{stem}_rod_xyt_data.csv"
    xt_npz_path = output_dir / f"{stem}_rod_xt_data.npz"
    xt_csv_path = output_dir / f"{stem}_rod_xt_data.csv"
    meta_path = output_dir / f"{stem}_rod_meta.json"

    np.savez(
        xyt_npz_path,
        inputs=datasets["xyt_inputs"],
        targets=datasets["xyt_targets"],
        frame_indices=datasets["frame_indices"],
    )
    np.savez(
        xt_npz_path,
        inputs=datasets["xt_inputs"],
        targets=datasets["xt_targets"],
        xt_grid_c=datasets["xt_grid_c"],
        time_axis_sec=datasets["time_axis_sec"],
        x_axis_heat_px=datasets["x_axis_heat_px"],
        x_axis_global_px=datasets["x_axis_global_px"],
        x_axis_mm=np.array([], dtype=np.float32) if datasets["x_axis_mm"] is None else datasets["x_axis_mm"],
        boundary_temperature_c=datasets["boundary_temperature_c"],
        far_end_temperature_c=datasets["far_end_temperature_c"],
    )

    with open(xyt_csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["frame_idx", "time_sec", "x_heat_px", "x_global_px", "y_global_px", "roi_x", "roi_y", "temperature_c"]
        )
        writer.writerows(datasets["xyt_rows"])

    with open(xt_csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame_idx", "time_sec", "x_heat_px", "x_global_px", "roi_x", "temperature_c"])
        writer.writerows(datasets["xt_rows"])

    meta = {
        "source_file": str(dat_path),
        "fps": float(fps),
        "frame_count": int(datasets["roi_frames"].shape[0]),
        "source_frame_range": [int(datasets["frame_indices"][0]), int(datasets["frame_indices"][-1])],
        "roi": {
            "x_min": int(roi["x_min"]),
            "x_max": int(roi["x_max"]),
            "y_min": int(roi["y_min"]),
            "y_max": int(roi["y_max"]),
            "width": int(roi["x_max"] - roi["x_min"]),
            "height": int(roi["y_max"] - roi["y_min"]),
            "heat_side": roi["heat_side"],
            "y_center": int(roi.get("y_center", (roi["y_min"] + roi["y_max"]) // 2)),
        },
        "xyt_inputs_shape": list(datasets["xyt_inputs"].shape),
        "xt_grid_shape": list(datasets["xt_grid_c"].shape),
        "temperature_min_c": float(datasets["xyt_targets"].min()),
        "temperature_max_c": float(datasets["xyt_targets"].max()),
        "temperature_mean_c": float(datasets["xyt_targets"].mean()),
        "boundary_temperature_min_c": float(datasets["boundary_temperature_c"].min()),
        "boundary_temperature_max_c": float(datasets["boundary_temperature_c"].max()),
        "far_end_temperature_min_c": float(datasets["far_end_temperature_c"].min()),
        "far_end_temperature_max_c": float(datasets["far_end_temperature_c"].max()),
    }
    if datasets["x_axis_mm"] is not None:
        meta["x_axis_mm_range"] = [float(datasets["x_axis_mm"][0]), float(datasets["x_axis_mm"][-1])]
        meta["mm_per_px"] = float(datasets["x_axis_mm"][1] - datasets["x_axis_mm"][0]) if len(datasets["x_axis_mm"]) > 1 else 0.0
    if metadata_extra:
        meta.update(metadata_extra)

    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)

    return {
        "xyt_npz": xyt_npz_path,
        "xyt_csv": xyt_csv_path,
        "xt_npz": xt_npz_path,
        "xt_csv": xt_csv_path,
        "meta": meta_path,
    }


def save_figures(figure_dir, dat_path, frames_3d, roi, datasets):
    figure_dir.mkdir(parents=True, exist_ok=True)
    stem = dat_path.stem

    cold_frame = frames_3d[0]
    warm_frame = frames_3d[datasets["frame_indices"][-1]]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, frame, title in zip(axes, [cold_frame, warm_frame], ["Frame 0", f"Frame {datasets['frame_indices'][-1]}"]):
        im = ax.imshow(frame, cmap="inferno")
        rect = Rectangle(
            (roi["x_min"], roi["y_min"]),
            roi["x_max"] - roi["x_min"],
            roi["y_max"] - roi["y_min"],
            linewidth=1.5,
            edgecolor="cyan",
            facecolor="none",
        )
        ax.add_patch(rect)
        ax.set_title(title)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
    fig.colorbar(im, ax=axes, shrink=0.85, label="Temperature (C)")
    roi_path = figure_dir / f"{stem}_rod_roi_overlay.png"
    plt.savefig(roi_path, dpi=200, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(9, 5))
    extent = [
        float(datasets["x_axis_heat_px"][0]),
        float(datasets["x_axis_heat_px"][-1]),
        float(datasets["time_axis_sec"][-1]),
        float(datasets["time_axis_sec"][0]),
    ]
    plt.imshow(datasets["xt_grid_c"], aspect="auto", cmap="inferno", extent=extent)
    plt.colorbar(label="Temperature (C)")
    plt.xlabel("Distance From Heated End (px)")
    plt.ylabel("Time (s)")
    plt.title("Rod x-t Temperature Map")
    xt_path = figure_dir / f"{stem}_rod_xt_heatmap.png"
    plt.savefig(xt_path, dpi=200, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(9, 5))
    plt.plot(datasets["time_axis_sec"], datasets["boundary_temperature_c"], label="Heated-end boundary")
    plt.plot(datasets["time_axis_sec"], datasets["far_end_temperature_c"], label="Far-end boundary")
    plt.xlabel("Time (s)")
    plt.ylabel("Temperature (C)")
    plt.title("Boundary Temperature Curves")
    plt.grid(True)
    plt.legend()
    boundary_path = figure_dir / f"{stem}_rod_boundary_curves.png"
    plt.savefig(boundary_path, dpi=200, bbox_inches="tight")
    plt.close()

    return {
        "roi_overlay": roi_path,
        "xt_heatmap": xt_path,
        "boundary_curves": boundary_path,
    }


def main():
    args = parse_args()
    dat_path = resolve_file_path(args.dat_path)
    if not dat_path.exists():
        raise FileNotFoundError(f"未找到输入文件: {dat_path}")

    frames_3d = load_frames(dat_path)

    if all(value is not None for value in (args.x_min, args.x_max, args.y_min, args.y_max)):
        heat_side = args.heat_side
        if heat_side == "auto":
            heat_side = infer_heat_side(frames_3d[-max(1, args.hot_frame_count) :].mean(axis=0))
        roi = {
            "x_min": int(args.x_min),
            "x_max": int(args.x_max),
            "y_min": int(args.y_min),
            "y_max": int(args.y_max),
            "heat_side": heat_side,
        }
    else:
        roi = auto_detect_rod_roi(
            frames_3d,
            start_frame=0,
            cold_frame_count=args.cold_frame_count,
            hot_frame_count=args.hot_frame_count,
            search_y_max=args.search_y_max,
            band_half_height=args.band_half_height,
            min_delta_c=args.min_delta_c,
        )
        if args.heat_side != "auto":
            roi["heat_side"] = args.heat_side

    roi = normalize_roi(roi, frames_3d.shape[1:], heat_side_override=roi["heat_side"])

    datasets = build_rod_datasets(
        frames_3d,
        fps=args.fps,
        roi=roi,
        start_frame=args.data_start_frame,
        end_frame=args.data_end_frame,
        mm_per_px=args.mm_per_px,
    )

    output_dir = Path(args.output_dir).expanduser().resolve()
    figure_dir = Path(args.figure_dir).expanduser().resolve()
    output_paths = save_outputs(
        output_dir=output_dir,
        dat_path=dat_path,
        fps=args.fps,
        roi=roi,
        datasets=datasets,
        metadata_extra={"data_start_frame": int(args.data_start_frame), "data_end_frame": int(datasets["frame_indices"][-1] + 1)},
    )
    figure_paths = save_figures(figure_dir=figure_dir, dat_path=dat_path, frames_3d=frames_3d, roi=roi, datasets=datasets)

    print("已选 ROI:", roi)
    print("导出帧数:", datasets["roi_frames"].shape[0])
    print("导出一维网格 shape:", datasets["xt_grid_c"].shape)
    print("x,y,t 数据 shape:", datasets["xyt_inputs"].shape, datasets["xyt_targets"].shape)
    for label, path in output_paths.items():
        print(f"{label}: {path}")
    for label, path in figure_paths.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
