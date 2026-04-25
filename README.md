# Thermal-90 金属导热实验项目

本仓库用于记录和维护一个基于 **Raspberry Pi 5 + Thermal-90 红外热像 + 原始热像数据分析 + 后续 PINN / 反演** 的实验项目。

当前仓库的重点不是重新搭环境，而是把已经跑通的热像采集链路收敛成一套可重复、可分析、可继续扩展到导热参数反演的实验工作流。

## 当前状态

截至 **2026-04-25**，项目已经确认以下能力可用：

- 官方 `stream_spi.py` 可运行
- [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py) 可运行，并可在 VNC 下显示实时热像
- Thermal-90 原始 `.dat` 数据可以稳定录制和回传
- [`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py) 可生成 GIF 预览与基础分析图
- [`code/construct_training_data.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/construct_training_data.py) 可基于固定 ROI 构建训练数据

当前主线已经从“基础连接是否成功”转移到：

1. 固定正式样品 ROI
2. 统一原始数据命名与实验记录
3. 收敛训练数据格式
4. 为后续 PINN / 反演做准备

## 仓库结构

- [`code/`](/C:/Users/28146/Desktop/thermal-conductivity-project/code)
  - 当前正式使用的采集、回看与训练数据构建脚本
- [`code_appendix/`](/C:/Users/28146/Desktop/thermal-conductivity-project/code_appendix)
  - 附录、参考脚本或历史版本
- [`docs/`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs)
  - 项目说明、实验进度、操作手册、待办事项等
- [`docs/agent_memory/`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory)
  - 当前状态、决策、问题修复和下一步动作
- [`docs/references/`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/references)
  - 参考资料与论文
- [`data/raw/`](/C:/Users/28146/Desktop/thermal-conductivity-project/data/raw)
  - 原始热像数据 `.dat`
- [`data/derived/`](/C:/Users/28146/Desktop/thermal-conductivity-project/data/derived)
  - 训练数据与中间派生结果
- [`outputs/preview/`](/C:/Users/28146/Desktop/thermal-conductivity-project/outputs/preview)
  - GIF 等动态预览结果
- [`outputs/figures/`](/C:/Users/28146/Desktop/thermal-conductivity-project/outputs/figures)
  - 静态分析图

## 核心脚本

### 1. 实时热像采集

- [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py)
  - 在树莓派端运行，用于实时热像显示和录制

常见运行方式：

```bash
cd ~/experiment/code
sudo python3 thermal90_ir_temp.py
sudo python3 thermal90_ir_temp.py -r
```

说明：

- 需要在 **VNC 桌面环境** 下查看实时热像
- 如果在纯 SSH 终端中直接运行图形显示流程，容易遇到显示相关报错

### 2. 原始数据回看与基础分析

- [`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py)
  - 从 `.dat` 原始热像数据生成预览与基础分析结果

Windows 本地示例：

```powershell
python code\view_dat.py data\raw\<your-file>.dat
```

典型输出包括：

- `outputs/preview/<stem>_preview.gif`
- `outputs/figures/<stem>_frames_compare.png`
- `outputs/figures/<stem>_center_temp_curve.png`
- `outputs/figures/<stem>_center_roi_curve.png`
- `outputs/figures/<stem>_hot_roi_curve.png`

### 3. 构建训练数据

- [`code/construct_training_data.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/construct_training_data.py)
  - 基于固定矩形 ROI 将热像数据整理为训练输入

Windows 本地示例：

```powershell
python code\construct_training_data.py data\raw\<your-file>.dat
```

典型输出包括：

- `data/derived/<stem>_train_data.npz`
- `data/derived/<stem>_train_data.csv`
- `data/derived/<stem>_train_meta.json`

## 推荐工作流

### 1. 树莓派侧采集

1. 连接 Raspberry Pi 5 和 Thermal-90
2. 通过 SSH 做基础检查
3. 通过 VNC 查看实时热像
4. 录制 `.dat` 原始热像数据

### 2. Windows 侧回传与分析

1. 将 `.dat` 文件放入 [`data/raw/`](/C:/Users/28146/Desktop/thermal-conductivity-project/data/raw)
2. 运行 [`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py) 检查采集质量
3. 确认样品位置、热点区域和温度变化合理
4. 运行 [`code/construct_training_data.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/construct_training_data.py) 生成训练数据

## 当前文档入口

- 项目计划：[docs/01-project-plan.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/01-project-plan.md)
- 实验进度：[docs/06-实验进度.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/06-实验进度.md)
- 实验流程操作手册：[docs/07-实验流程操作手册.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/07-实验流程操作手册.md)
- 实验待办：[docs/08-实验待办.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/08-实验待办.md)
- 当前状态：[docs/agent_memory/current-state.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/current-state.md)
- 问题与修复：[docs/agent_memory/bugs-and-fixes.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/bugs-and-fixes.md)
- 决策记录：[docs/agent_memory/decisions.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/decisions.md)
- 下一步动作：[docs/agent_memory/next-actions.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/next-actions.md)

## 数据管理规则

- 原始热像数据、GIF、PNG 和训练输出默认只保留在本地，不直接纳入 Git 跟踪
- 仓库主要跟踪代码、说明文档、规则和必要元信息
- 新实验数据统一放在 `data/raw/`
- 派生数据统一放在 `data/derived/`、`outputs/preview/`、`outputs/figures/`

## 当前提醒

- 当前 ROI 仍处于收敛阶段，候选 ROI 不能直接视为最终正式样品 ROI
- 当前项目已经具备做数据闭环验证的条件，但还没有完成正式导热率测量闭环
- 后续若进入 PINN / 反演，前提是样品、视角、加热方式和 ROI 都已经固定
