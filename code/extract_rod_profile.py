import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from view_dat import PROJECT_ROOT, load_frames, resolve_file_path


"""extract_rod_profile.py

工具脚本：从 Thermal-90 的原始帧数据中自动或手工检测金属圆棒的 ROI（感兴趣区），
并将该 ROI 内的数据整理成两类用于 PINN（物理信息神经网络）训练的数据集：

- x,y,t 三元组（空间 x、跨径 y、时间 t）对应的温度值（用于二维或局部模型）
- x,t 网格（沿轴方向平均后的温度随时间变化）用于一维传导建模和训练数据

脚本功能包括：
- 自动检测棒身的横向范围（x_min/x_max）与中心行（y_center），可用阈值与前后帧差
- 将选定帧范围内的 ROI 重塑并导出为 .npz（numpy 压缩）与 .csv（文本）格式
- 生成可视化图像：ROI 覆盖图、x-t 热图、边界温度曲线，便于人工质检

主要输出目录：
 - data/derived/        : 导出的训练数据（.npz/.csv）和元信息（.json）
 - outputs/figures/     : 可视化图片（PNG）

使用示例：
python code/extract_rod_profile.py data/raw/yourfile.dat --fps 7 --data-start-frame 250

此脚本侧重数据提取与导出，不包含训练逻辑。
"""


DERIVED_DATA_DIR = PROJECT_ROOT / "data" / "derived"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
# 默认参数：帧率与各类帧计数/阈值，用于自动检测与导出
DEFAULT_FPS = 7.0
DEFAULT_DATA_START_FRAME = 250
DEFAULT_COLD_FRAME_COUNT = 30
DEFAULT_HOT_FRAME_COUNT = 100
DEFAULT_BAND_HALF_HEIGHT = 2
DEFAULT_MIN_DELTA_C = 3.0


def parse_args():
    """解析命令行参数并返回解析结果。

    支持的参数包括输入文件路径、帧率、数据导出起止帧、用于自动检测的阈值参数、
    以及可选的手动 ROI 覆盖范围和输出目录。
    """
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
    """对一维信号做简单滑动平均平滑。

    - values: 一维 numpy 数组或等价序列
    - window: 平滑窗口大小（整数），小于等于 1 时返回原始序列的拷贝
    返回平滑后的 numpy 数组。
    """
    window = max(1, int(window))
    if window == 1 or len(values) < window:
        return values.copy()
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(values, kernel, mode="same")


def close_small_gaps(mask, max_gap=2):
    """将布尔掩码中长度小于等于 `max_gap` 的 False 间隙合并为 True。

    用于在沿 X 方向查找连续真值区间时，填充极短的空洞，避免被噪声分割成多个区间。
    """
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
    """在布尔掩码中查找最长的连续 True 子段，返回 (start, end) 索引范围（end 为 exclusive）。

    用于确定沿 X 方向的主要连通段，例如棒身的左右边界。
    """
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
    """基于热平均图判断加热边（左/右）。

    简单策略：比较左右边缘若干列的平均温度，较高的一侧认为是受热侧。
    """
    width = hot_mean.shape[1]
    edge_width = max(4, width // 6)
    left_score = float(hot_mean[:, :edge_width].mean())
    right_score = float(hot_mean[:, -edge_width:].mean())
    return "left" if left_score >= right_score else "right"


def validate_roi(roi, frame_shape):
    """检查 ROI 字典中的 x/y 范围是否合法（位于图像范围内且非空）。

    frame_shape: (height, width)
    roi: 包含 x_min, x_max, y_min, y_max 的字典
    若不合法，则抛出异常。
    """
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
    """自动检测棒身的 ROI（x_min/x_max/y_min/y_max）。

    算法要点：
    - 使用早期若干帧估计冷态平均图 `cold_mean`，使用末端若干帧估计热态平均图 `hot_mean`。
    - 计算 `delta = hot_mean - cold_mean`，在图像上寻找沿 y（行）方向的最大响应行（y_center）。
    - 在围绕 y_center 的若干行内（band）计算沿 x 的平均增量 `band_delta`，并结合上方背景对比度过滤噪声。
    - 将满足阈值的 x 列用 `close_small_gaps` 填小孔，再用 `longest_true_run` 选取最长连续段作为棒身横向范围。

    返回包含 roi 字段的字典和一些检测元信息（如热/冷帧范围与热侧）。
    """
    frame_count, height, width = frames_3d.shape
    if frame_count < 2:
        raise ValueError("至少需要两帧数据才能自动检测 ROI")
    if start_frame < 0 or start_frame >= frame_count:
        raise ValueError(f"start_frame 超出范围: {start_frame}")

    # 计算冷态和热态的平均图像
    cold_end = min(frame_count, start_frame + max(1, cold_frame_count))
    hot_start = max(cold_end, frame_count - max(1, hot_frame_count))
    cold_mean = frames_3d[start_frame:cold_end].mean(axis=0)
    hot_mean = frames_3d[hot_start:frame_count].mean(axis=0)
    delta = hot_mean - cold_mean

    # 限制搜索的行范围（默认上部 65%），避免误把底部支架识别为棒身
    if search_y_max is None:
        search_y_max = max(1, int(height * 0.65))
    search_y_max = min(height, max(1, search_y_max))

    # 按行统计响应，并平滑以得到稳定的 y_center
    row_scores = delta[:search_y_max].mean(axis=1)
    row_scores_smooth = smooth_signal(row_scores, window=5)
    y_center = int(np.argmax(row_scores_smooth))

    band_half_height = max(1, int(band_half_height))
    y_min = max(0, y_center - band_half_height)
    y_max = min(height, y_center + band_half_height)

    # 在选定的行带上计算沿 x 的平均增量和上方背景对比度
    band_delta = delta[y_min:y_max].mean(axis=0)
    band_hot = hot_mean[y_min:y_max].mean(axis=0)
    upper_bg_y_min = max(0, y_min - 6)
    upper_bg_y_max = max(upper_bg_y_min + 1, y_min)
    upper_background = hot_mean[upper_bg_y_min:upper_bg_y_max].mean(axis=0)

    # 基于差值与对比度进行阈值过滤，填充小孔并取最长连续段
    contrast_mask = (band_hot - upper_background) > float(min_delta_c)
    candidate_mask = close_small_gaps((band_delta > float(min_delta_c)) & contrast_mask, max_gap=2)
    x_min, x_max = longest_true_run(candidate_mask)
    if x_max - x_min < 8:
        # 若太窄，放宽条件，不再要求对比度
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
    """规范化并验证 ROI 字段。

    - 将 roi 转为字典副本，校验坐标合法性；
    - 可通过 heat_side_override 强制设置加热侧（left/right）。
    返回经验证的 roi 字典。
    """
    roi = dict(roi)
    validate_roi(roi, frame_shape)
    if heat_side_override != "auto":
        roi["heat_side"] = heat_side_override
    if roi.get("heat_side") not in {"left", "right"}:
        raise ValueError("heat_side 必须为 left 或 right")
    return roi


def build_rod_datasets(frames_3d, fps, roi, start_frame=0, end_frame=None, mm_per_px=None):
    """根据 ROI 与帧范围构建训练所需的数据集。

    返回字典，包含：
    - roi_frames: 截取的 (帧, y, x) 子序列
    - xyt_inputs/targets: 每个像素（x_heat_px, y_global_px, t_sec）对应的温度目标
    - xt_inputs/targets: 沿 x（轴向）平均后的 x-t 网格数据
    - 以及若干辅助数组（时间轴、像素坐标、边界温度曲线等）

    参数 mm_per_px 可选，用来将像素坐标转换为物理毫米坐标（导出 meta 时使用）。
    """
    if fps <= 0:
        raise ValueError("fps 必须大于 0")
    frame_count = frames_3d.shape[0]
    if start_frame < 0 or start_frame >= frame_count:
        raise ValueError(f"start_frame 超出范围: {start_frame}")
    if end_frame is None:
        end_frame = frame_count
    if end_frame <= start_frame or end_frame > frame_count:
        raise ValueError(f"end_frame 超出范围: {end_frame}")

    # 规范化并验证 ROI
    roi = normalize_roi(roi, frames_3d.shape[1:], heat_side_override=roi["heat_side"])

    # 截取 ROI 内的帧序列
    roi_frames = frames_3d[start_frame:end_frame, roi["y_min"] : roi["y_max"], roi["x_min"] : roi["x_max"]]
    global_x = np.arange(roi["x_min"], roi["x_max"], dtype=np.float32)
    global_y = np.arange(roi["y_min"], roi["y_max"], dtype=np.float32)

    # 如果热端在右侧，为了后续处理方便，按轴向将数据翻转，使得热端总在数组的左侧
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

    # 构建 x,y,t -> 温度 的逐像素数据（用于更高维模型）
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

    # 构建沿 y 平均后的 x-t 网格（常用于一维传热建模）
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
    """将构建好的数据集保存到磁盘（.npz, .csv, .json）。

    - 保存 x,y,t 数据为压缩 numpy 文件和 CSV 文本以便后续加载或查看；
    - 保存 x,t 网格数据（numpy）和 CSV；
    - 生成包含元信息（ROI、帧范围、温度统计等）的 JSON 文件。
    返回保存的路径字典，便于上层脚本打印或记录。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = dat_path.stem

    xyt_npz_path = output_dir / f"{stem}_rod_xyt_data.npz"
    xyt_csv_path = output_dir / f"{stem}_rod_xyt_data.csv"
    xt_npz_path = output_dir / f"{stem}_rod_xt_data.npz"
    xt_csv_path = output_dir / f"{stem}_rod_xt_data.csv"
    meta_path = output_dir / f"{stem}_rod_meta.json"

    # 保存 numpy 压缩文件，便于后续快速载入训练脚本
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

    # 保存 CSV 以便人工查看（体积可能较大）
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

    # 组织并保存 metadata，包含 ROI、帧范围、温度统计等
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
    """绘制并保存若干便于检查的图像：

    - ROI 覆盖图（冷帧与热帧）
    - x-t 热图（沿 y 平均得到 xt_grid_c）
    - 边界温度随时间曲线（加热端与远端）

    返回保存的文件路径字典。
    """
    figure_dir.mkdir(parents=True, exist_ok=True)
    stem = dat_path.stem

    # ROI 覆盖：展示第一帧与导出序列最后一帧，并用矩形标记 ROI
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

    # x-t 热图：extent 用于翻转纵轴，使时间从上到下或从早到晚按预期显示
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

    # 边界温度曲线：用于检查加热端与远端的温度随时间的变化趋势
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
    """脚本主流程：

    - 解析参数并定位输入 `.dat` 文件
    - 读取并重塑帧数据
    - 如果用户提供完整手工 ROI（x_min/x_max/y_min/y_max），使用手工 ROI；否则尝试自动检测
    - 构建导出数据集，保存为 .npz/.csv，并生成检查图像
    - 在控制台打印结果路径与关键统计信息
    """
    args = parse_args()
    dat_path = resolve_file_path(args.dat_path)
    if not dat_path.exists():
        raise FileNotFoundError(f"未找到输入文件: {dat_path}")

    # 加载原始帧并重塑为 (帧, H, W)
    frames_3d = load_frames(dat_path)

    # 手工 ROI 优先；否则自动检测 ROI
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

    # 构建用于导出的数据结构
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

    # 控制台输出便于人工确认
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
