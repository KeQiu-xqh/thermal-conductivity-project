import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


DEFAULT_FILENAME = "2000.0.0.000000--20260403-165346.dat"
FRAME_HEIGHT = 62
FRAME_WIDTH = 80
DEFAULT_GIF_FPS = 12
DEFAULT_GIF_STRIDE = 5
DEFAULT_GIF_SCALE = 6


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read a Thermal-90 .dat file and generate basic plots."
    )
    parser.add_argument(
        "dat_path",
        nargs="?",
        help="Path to the .dat file. If omitted, falls back to the legacy desktop file.",
    )
    parser.add_argument("--gif-fps", type=int, default=DEFAULT_GIF_FPS)
    parser.add_argument("--gif-stride", type=int, default=DEFAULT_GIF_STRIDE)
    parser.add_argument("--gif-scale", type=int, default=DEFAULT_GIF_SCALE)
    return parser.parse_args()


def resolve_file_path(dat_path):
    if dat_path:
        return Path(dat_path).expanduser().resolve()
    return (Path.home() / "Desktop" / DEFAULT_FILENAME).resolve()


def load_frames(file_path):
    with open(file_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    frames = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        values = [float(x) for x in line.split()]
        frames.append(values)

    frames = np.array(frames)
    print("原始数组形状:", frames.shape)

    num_pixels = frames.shape[1]
    if num_pixels != FRAME_HEIGHT * FRAME_WIDTH:
        raise ValueError(f"每帧像素数不对: {num_pixels}")

    frames_3d = frames.reshape(-1, FRAME_HEIGHT, FRAME_WIDTH)
    print("重塑后形状:", frames_3d.shape)
    print("总帧数:", frames_3d.shape[0])
    return frames_3d


def save_frames_compare(frames_3d):
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
    plt.savefig("frames_compare.png", dpi=200, bbox_inches="tight")
    print("已保存 frames_compare.png")
    plt.close()


def save_center_plots(frames_3d):
    center_y, center_x = 31, 40
    center_temp = frames_3d[:, center_y, center_x]

    plt.figure(figsize=(8, 5))
    plt.plot(center_temp, marker="o")
    plt.title(f"Center Pixel Temperature vs Frame ({center_y}, {center_x})")
    plt.xlabel("Frame Index")
    plt.ylabel("Temperature (C)")
    plt.grid(True)
    plt.savefig("center_temp_curve.png", dpi=200, bbox_inches="tight")
    print("已保存 center_temp_curve.png")
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
    plt.savefig("center_roi_curve.png", dpi=200, bbox_inches="tight")
    print("已保存 center_roi_curve.png")
    plt.close()

    print("中心 5x5 ROI 前 5 帧温度:", roi_temp[:5])
    print("中心 5x5 ROI 后 5 帧温度:", roi_temp[-5:])
    print("中心 5x5 ROI 最低温:", np.min(roi_temp))
    print("中心 5x5 ROI 最高温:", np.max(roi_temp))


def save_hot_roi_plot(frames_3d):
    first_frame = frames_3d[0]
    last_frame = frames_3d[-1]

    first_max_idx = np.unravel_index(np.argmax(first_frame), first_frame.shape)
    last_max_idx = np.unravel_index(np.argmax(last_frame), last_frame.shape)

    print("第一帧最高温位置(y, x):", first_max_idx, "温度:", first_frame[first_max_idx])
    print("最后一帧最高温位置(y, x):", last_max_idx, "温度:", last_frame[last_max_idx])

    hot_y, hot_x = first_max_idx
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
    plt.savefig("hot_roi_curve.png", dpi=200, bbox_inches="tight")
    print("已保存 hot_roi_curve.png")
    plt.close()

    print("热区 ROI 前 5 帧温度:", hot_roi_temp[:5])
    print("热区 ROI 后 5 帧温度:", hot_roi_temp[-5:])
    print("热区 ROI 最低温:", np.min(hot_roi_temp))
    print("热区 ROI 最高温:", np.max(hot_roi_temp))


def save_preview_gif(frames_3d, file_path, fps, stride, scale):
    fps = max(1, fps)
    stride = max(1, stride)
    scale = max(1, scale)
    sampled_frames = frames_3d[::stride]

    vmin = float(np.min(frames_3d))
    vmax = float(np.max(frames_3d))
    if np.isclose(vmin, vmax):
        vmax = vmin + 1e-6

    cmap = plt.get_cmap("inferno")
    images = []
    for frame in sampled_frames:
        normalized = np.clip((frame - vmin) / (vmax - vmin), 0.0, 1.0)
        rgb = (cmap(normalized)[..., :3] * 255).astype(np.uint8)
        image = Image.fromarray(rgb)
        if scale != 1:
            image = image.resize(
                (FRAME_WIDTH * scale, FRAME_HEIGHT * scale),
                resample=Image.Resampling.NEAREST,
            )
        images.append(image)

    output_path = Path(f"{file_path.stem}_preview.gif")
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=int(1000 / fps),
        loop=0,
    )
    print(f"宸蹭繚瀛?{output_path}")


def main():
    args = parse_args()
    file_path = resolve_file_path(args.dat_path)
    if not file_path.exists():
        raise FileNotFoundError(f"未找到 .dat 文件: {file_path}")

    frames_3d = load_frames(file_path)
    save_frames_compare(frames_3d)
    save_center_plots(frames_3d)
    save_hot_roi_plot(frames_3d)
    save_preview_gif(
        frames_3d,
        file_path,
        fps=args.gif_fps,
        stride=args.gif_stride,
        scale=args.gif_scale,
    )


if __name__ == "__main__":
    main()
