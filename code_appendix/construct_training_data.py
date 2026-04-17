import numpy as np

import os
import json
from glob import glob

# 修改为你解压后的路径
data_dir = "C:/Users/ASUS/Desktop/大物实验比赛/tong"

# 检查meta.json 文件是否存在且不为空
meta_path = os.path.join(data_dir, "meta.json")
if not os.path.exists(meta_path) or os.path.getsize(meta_path) == 0:
    print("⚠️ meta.json 文件不存在或为空，使用默认参数")
    # 手动设置默认参数
    frame_count = 3  # 根据实际文件数量调整
    interval_sec = 1.0
else:
    # 读取元信息
    with open(meta_path, "r") as f:
        meta = json.load(f)
    frame_count = meta["frames"]
    interval_sec = meta["interval_sec"]

# 检查实际的文件数量
actual_files = len([f for f in os.listdir(data_dir) if f.endswith('.npy')])
print(f"📁 发现 {actual_files} 个 .npy 文件")
frame_count = min(frame_count, actual_files)

shape = (62, 80)  # MI48 分辨率 - 修正为实际形状

# 存储列表
inputs = []
targets = []

for i in range(frame_count):
    # 载入温度矩阵
    path = os.path.join(data_dir, f"frame_{i:04d}.npy")
    if not os.path.exists(path):
        print(f"⚠️ 文件不存在: {path}")
        continue

    T = np.load(path)  # shape = (62, 80)
    print(f"📊 帧 {i}: 形状 {T.shape}, 温度范围 [{T.min():.2f}, {T.max():.2f}]°C")

    # 构造 t 值（时间秒数）
    t = i * interval_sec

    for y in range(shape[0]):
        for x in range(shape[1]):
            inputs.append([x, y, t])
            targets.append(T[y, x])

inputs = np.array(inputs, dtype=np.float32)
targets = np.array(targets, dtype=np.float32).reshape(-1, 1)

print("✅ 输入样本 shape:", inputs.shape)   # (N, 3)
print("✅ 目标温度 shape:", targets.shape)  # (N, 1)
print(f"📈 温度统计: 最小值={targets.min():.2f}°C, 最大值={targets.max():.2f}°C, 平均值
={targets.mean():.2f}°C")

np.savez("train_data.npz", inputs=inputs, targets=targets)
print("✅ 数据已保存到 train_data.npz")