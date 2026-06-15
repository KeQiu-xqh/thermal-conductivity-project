import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

"""
view_dat.py

工具脚本，用于读取 Thermal-90 设备导出的原始 `.dat` 文本文件，
将每一帧的像素温度数据重构为 (H, W) 图像序列，并生成若干用于
人工检查的可视化产物：关键帧对比图、中心像素/中心 ROI 的温度曲线、
热区（hot ROI）温度曲线以及合成的 GIF 预览。

期望的输入格式：每一行为一帧，行内有 FRAME_HEIGHT * FRAME_WIDTH 个
以空格分隔的浮点数（表示温度，单位摄氏度）。脚本不会修改原文件，
只在 `outputs/figures/` 与 `outputs/preview/` 下写入图片文件。
"""


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # 项目根目录（仓库根）
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"  # 原始 .dat 文件默认存放目录
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"  # PNG 输出目录
PREVIEW_DIR = PROJECT_ROOT / "outputs" / "preview"  # GIF 预览输出目录


# 热像帧的固定尺寸（Thermal-90 硬件分辨率）: 高度 x 宽度
FRAME_HEIGHT = 62
FRAME_WIDTH = 80

# GIF 生成默认参数：帧率、采样步长（跳帧）与放大倍数
DEFAULT_GIF_FPS = 12
DEFAULT_GIF_STRIDE = 5
DEFAULT_GIF_SCALE = 6


def parse_args():
    """解析命令行参数。

    返回包含以下可选参数的命名空间：
    - dat_path: 待处理的原始 `.dat` 文件路径，若省略则使用 `data/raw/` 中最新文件。
    - --gif-fps: 生成 GIF 的帧率（默认 12）。
    - --gif-stride: 采样步长（跳帧）以加速预览（默认 5）。
    - --gif-scale: GIF 图像缩放倍数（默认 6）。
    """
    parser = argparse.ArgumentParser(
        description="Read a Thermal-90 raw data file and generate preview figures."
    )
    parser.add_argument(
        "dat_path",
        nargs="?",
        help="Path to the raw thermal data file. If omitted, use the newest file in data/raw/.",
    )
    parser.add_argument("--gif-fps", type=int, default=DEFAULT_GIF_FPS)
    parser.add_argument("--gif-stride", type=int, default=DEFAULT_GIF_STRIDE)
    parser.add_argument("--gif-scale", type=int, default=DEFAULT_GIF_SCALE)
    return parser.parse_args()


def find_latest_raw_data():
    """返回 `data/raw/` 中按修改时间排序的最新文件路径。如果不存在则返回
    代码中定义的 `LEGACY_DESKTOP_FILE`（便于开发/测试）。
    """
    if RAW_DATA_DIR.exists():
        candidates = sorted(
            [p for p in RAW_DATA_DIR.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]
    raise FileNotFoundError(f"未在 {RAW_DATA_DIR} 中找到原始 .dat 文件")


def resolve_file_path(dat_path):
    """将传入的 `dat_path` 解析为绝对 `Path`；若为空则使用最新原始文件。
    返回一个 `Path` 对象。
    """
    if dat_path:
        return Path(dat_path).expanduser().resolve()
    return find_latest_raw_data().resolve()


def load_frames(file_path):
    """从文本文件中读取并解析成三维数组 (num_frames, FRAME_HEIGHT, FRAME_WIDTH)。

    期望每一行是一帧：包含 FRAME_HEIGHT * FRAME_WIDTH 个空格分隔的浮点数。
    函数会忽略空行，并把所有帧转换为 `np.float32`，最后按 (帧, 高, 宽)
    重塑数组并返回。
    """
    with open(file_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    frames = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 将每行的字符串数字转换为浮点数列表
        values = [float(x) for x in line.split()]
        frames.append(values)

    frames = np.array(frames, dtype=np.float32)
    print("原始数组形状:", frames.shape)

    # 校验每帧像素数是否符合预期
    num_pixels = frames.shape[1]
    if num_pixels != FRAME_HEIGHT * FRAME_WIDTH:
        raise ValueError(f"每帧像素数不对: {num_pixels}")

    # 重塑为 (帧数, 高, 宽)
    frames_3d = frames.reshape(-1, FRAME_HEIGHT, FRAME_WIDTH)
    print("重塑后形状:", frames_3d.shape)
    print("总帧数:", frames_3d.shape[0])
    return frames_3d


def ensure_output_dirs():
    """确保用于保存图像的输出目录存在。"""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def save_frames_compare(frames_3d, stem):
    """保存若干关键帧的并排对比图，方便人工检查帧间差异与样品位置。

    默认挑选第 0 帧，第 10 帧和第 20 帧（若视频总帧数不足则使用最后一帧）。
    """
    frame_indices = [0, min(10, frames_3d.shape[0] - 1), min(20, frames_3d.shape[0] - 1)]
    valid_indices = sorted(set(frame_indices))

    fig, axes = plt.subplots(1, len(valid_indices), figsize=(5 * len(valid_indices), 4))
    if len(valid_indices) == 1:
        axes = [axes]

    for ax, idx in zip(axes, valid_indices):
        im = ax.imshow(frames_3d[idx], cmap="inferno")
        ax.set_title(f"Frame {idx}")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

    fig.colorbar(im, ax=axes, shrink=0.8, label="Temperature (C)")
    output_path = FIGURES_DIR / f"{stem}_frames_compare.png"
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    print("已保存", output_path)
    plt.close()


def save_center_plots(frames_3d, stem):
    """绘制中心像素及其 5x5 小 ROI 的温度随帧索引变化曲线。

    - `center_y, center_x` 为脚本定义的图像中心（行, 列）。
    - 第一张图是单像素曲线，有助于检测逐帧的离散跳变。
    - 第二张图是中心 5x5 区域的平均温度曲线，更鲁棒，常用于判断加热趋势。
    """
    center_y, center_x = 31, 40
    center_temp = frames_3d[:, center_y, center_x]

    plt.figure(figsize=(8, 5))
    plt.plot(center_temp, marker="o")
    plt.title(f"Center Pixel Temperature vs Frame ({center_y}, {center_x})")
    plt.xlabel("Frame Index")
    plt.ylabel("Temperature (C)")
    plt.grid(True)
    center_temp_path = FIGURES_DIR / f"{stem}_center_temp_curve.png"
    plt.savefig(center_temp_path, dpi=200, bbox_inches="tight")
    print("已保存", center_temp_path)
    plt.close()

    cy, cx = center_y, center_x
    roi = frames_3d[:, cy - 2 : cy + 3, cx - 2 : cx + 3]
    roi_temp = roi.mean(axis=(1, 2))

    plt.figure(figsize=(8, 5))
    plt.plot(roi_temp, marker="o")
    plt.title("Center 5x5 ROI Mean Temperature vs Frame")
    plt.xlabel("Frame Index")
    plt.ylabel("Temperature (C)")
    plt.grid(True)
    center_roi_path = FIGURES_DIR / f"{stem}_center_roi_curve.png"
    plt.savefig(center_roi_path, dpi=200, bbox_inches="tight")
    print("已保存", center_roi_path)
    plt.close()

    # 额外输出部分统计数值，便于在控制台快速检查
    print("中心 5x5 ROI 前 5 帧温度:", roi_temp[:5])
    print("中心 5x5 ROI 后 5 帧温度:", roi_temp[-5:])
    print("中心 5x5 ROI 最低温:", np.min(roi_temp))
    print("中心 5x5 ROI 最高温:", np.max(roi_temp))


def save_hot_roi_plot(frames_3d, stem):
    """定位首帧中的最高温点作为热区中心，提取该热区随时间的平均温度并绘图。

    说明：使用首帧的最大值作为热区中心是为了在热源固定的情况下稳定定位；若样品
    在采集过程中移动或热源位置变化，此方法可能需要调整。
    """
    first_frame = frames_3d[0]
    last_frame = frames_3d[-1]

    first_max_idx = np.unravel_index(np.argmax(first_frame), first_frame.shape)
    last_max_idx = np.unravel_index(np.argmax(last_frame), last_frame.shape)

    print("第一帧最高温位置(y, x):", first_max_idx, "温度:", first_frame[first_max_idx])
    print("最后一帧最高温位置(y, x):", last_max_idx, "温度:", last_frame[last_max_idx])

    hot_y, hot_x = first_max_idx
    # 选择一个最多 5x5 的局部窗口（边界条件被夹住）
    y1 = max(hot_y - 2, 0)
    y2 = min(hot_y + 3, FRAME_HEIGHT)
    x1 = max(hot_x - 2, 0)
    x2 = min(hot_x + 3, FRAME_WIDTH)

    hot_roi = frames_3d[:, y1:y2, x1:x2]
    hot_roi_temp = hot_roi.mean(axis=(1, 2))

    plt.figure(figsize=(8, 5))
    plt.plot(hot_roi_temp, marker="o")
    plt.title(f"Hot ROI Mean Temperature vs Frame (center={first_max_idx})")
    plt.xlabel("Frame Index")
    plt.ylabel("Temperature (C)")
    plt.grid(True)
    hot_roi_path = FIGURES_DIR / f"{stem}_hot_roi_curve.png"
    plt.savefig(hot_roi_path, dpi=200, bbox_inches="tight")
    print("已保存", hot_roi_path)
    plt.close()

    print("热区 ROI 前 5 帧温度:", hot_roi_temp[:5])
    print("热区 ROI 后 5 帧温度:", hot_roi_temp[-5:])
    print("热区 ROI 最低温:", np.min(hot_roi_temp))
    print("热区 ROI 最高温:", np.max(hot_roi_temp))


def save_preview_gif(frames_3d, stem, fps, stride, scale):
    """将帧序列以指定的步长和速率合成 GIF。说明：

    - `stride` 用来跳帧，减少生成帧数以加快预览（例如 5 表示每 5 帧取一帧）。
    - 先基于所有帧计算 `vmin`/`vmax`，并按该范围归一化映射到 `inferno` 颜色表，得到 RGB 图像。
    - `scale` 放大每帧像素以便查看（Nearest 最近邻插值保留像素块感）。
    """
    fps = max(1, fps)
    stride = max(1, stride)
    scale = max(1, scale)
    sampled_frames = frames_3d[::stride]

    # 使用全序列的最小/最大值来保证不同帧之间颜色映射一致
    vmin = float(np.min(frames_3d))
    vmax = float(np.max(frames_3d))
    if np.isclose(vmin, vmax):
        vmax = vmin + 1e-6

    cmap = plt.get_cmap("inferno")
    images = []
    for frame in sampled_frames:
        # 归一化到 [0,1]，再映射为 RGB
        normalized = np.clip((frame - vmin) / (vmax - vmin), 0.0, 1.0)
        rgb = (cmap(normalized)[..., :3] * 255).astype(np.uint8)
        image = Image.fromarray(rgb)
        if scale != 1:
            image = image.resize(
                (FRAME_WIDTH * scale, FRAME_HEIGHT * scale),
                resample=Image.Resampling.NEAREST,
            )
        images.append(image)

    output_path = PREVIEW_DIR / f"{stem}_preview.gif"
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=int(1000 / fps),
        loop=0,
    )
    print("已保存", output_path)


def main():
    """脚本入口：解析参数、寻找文件、生成各类输出并保存到磁盘。"""
    args = parse_args()
    file_path = resolve_file_path(args.dat_path)
    if not file_path.exists():
        raise FileNotFoundError(f"未找到原始数据文件: {file_path}")

    ensure_output_dirs()
    frames_3d = load_frames(file_path)
    stem = file_path.stem
    save_frames_compare(frames_3d, stem)
    save_center_plots(frames_3d, stem)
    save_hot_roi_plot(frames_3d, stem)
    save_preview_gif(
        frames_3d,
        stem,
        fps=args.gif_fps,
        stride=args.gif_stride,
        scale=args.gif_scale,
    )


if __name__ == "__main__":
    main()
