import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ===== 只改这里 =====
filename = "2000.0.0.000000--20260403-165346.dat"
# ===================

file_path = Path.home() / "Desktop" / filename

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

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
if num_pixels != 62 * 80:
    raise ValueError(f"每帧像素数不对：{num_pixels}")

frames_3d = frames.reshape(-1, 62, 80)

print("重塑后形状:", frames_3d.shape)
print("总帧数:", frames_3d.shape[0])

# 1) 多帧热图对比
frame_indices = [0, min(10, frames_3d.shape[0]-1), min(20, frames_3d.shape[0]-1)]
valid_indices = sorted(set(frame_indices))

fig, axes = plt.subplots(1, len(valid_indices), figsize=(5 * len(valid_indices), 4))
if len(valid_indices) == 1:
    axes = [axes]

for ax, idx in zip(axes, valid_indices):
    im = ax.imshow(frames_3d[idx], cmap="inferno")
    ax.set_title(f"Frame {idx}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")

fig.colorbar(im, ax=axes, shrink=0.8, label="Temperature (°C)")
plt.savefig("frames_compare.png", dpi=200, bbox_inches="tight")
print("已保存 frames_compare.png")
plt.close()

# 2) 中心点温度曲线
center_y, center_x = 31, 40
center_temp = frames_3d[:, center_y, center_x]

plt.figure(figsize=(8, 5))
plt.plot(center_temp, marker="o")
plt.title(f"Center Pixel Temperature vs Frame ({center_y}, {center_x})")
plt.xlabel("Frame Index")
plt.ylabel("Temperature (°C)")
plt.grid(True)
plt.savefig("center_temp_curve.png", dpi=200, bbox_inches="tight")
print("已保存 center_temp_curve.png")
plt.close()

# 3) 第一帧和最后一帧最热点
first_frame = frames_3d[0]
last_frame = frames_3d[-1]

first_max_idx = np.unravel_index(np.argmax(first_frame), first_frame.shape)
last_max_idx = np.unravel_index(np.argmax(last_frame), last_frame.shape)

print("第一帧最高温位置(y, x):", first_max_idx, "温度:", first_frame[first_max_idx])
print("最后一帧最高温位置(y, x):", last_max_idx, "温度:", last_frame[last_max_idx])

# 4) 中心 5x5 区域平均温度曲线
cy, cx = 31, 40
roi = frames_3d[:, cy-2:cy+3, cx-2:cx+3]
roi_temp = roi.mean(axis=(1, 2))

plt.figure(figsize=(8, 5))
plt.plot(roi_temp, marker="o")
plt.title("Center 5x5 ROI Mean Temperature vs Frame")
plt.xlabel("Frame Index")
plt.ylabel("Temperature (°C)")
plt.grid(True)
plt.savefig("center_roi_curve.png", dpi=200, bbox_inches="tight")
print("已保存 center_roi_curve.png")
plt.close()

print("中心5x5区域前5帧温度:", roi_temp[:5])
print("中心5x5区域最后5帧温度:", roi_temp[-5:])
print("中心5x5区域最低温:", np.min(roi_temp))
print("中心5x5区域最高温:", np.max(roi_temp))

# 5) 以第一帧最热点为中心，取 5x5 热区 ROI
hot_y, hot_x = first_max_idx
y1 = max(hot_y - 2, 0)
y2 = min(hot_y + 3, 62)
x1 = max(hot_x - 2, 0)
x2 = min(hot_x + 3, 80)

hot_roi = frames_3d[:, y1:y2, x1:x2]
hot_roi_temp = hot_roi.mean(axis=(1, 2))

plt.figure(figsize=(8, 5))
plt.plot(hot_roi_temp, marker="o")
plt.title(f"Hot ROI Mean Temperature vs Frame (center≈{first_max_idx})")
plt.xlabel("Frame Index")
plt.ylabel("Temperature (°C)")
plt.grid(True)
plt.savefig("hot_roi_curve.png", dpi=200, bbox_inches="tight")
print("已保存 hot_roi_curve.png")

print("热区ROI前5帧温度:", hot_roi_temp[:5])
print("热区ROI最后5帧温度:", hot_roi_temp[-5:])
print("热区ROI最低温:", np.min(hot_roi_temp))
print("热区ROI最高温:", np.max(hot_roi_temp))