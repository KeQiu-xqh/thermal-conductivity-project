# Thermal-90 金属导热系数实验项目

本仓库用于记录和维护基于 **Raspberry Pi 5 + Thermal-90 + 红外热像 + 后续 PINN/反演** 的实验代码与文档。

## 当前状态

截至 `2026-04-17`，项目已经完成以下闭环：

- 官方 `stream_spi.py` 采集链路可运行
- [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py) 可运行并在 VNC 下正常显示热像
- 原始热像数据已成功采集
- [`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py) 可生成静态分析图和 GIF 回看
- [`code/construct_training_data.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/construct_training_data.py) 可从固定 ROI 构建训练数据

当前主线不是“搭环境”，而是：

1. 固定金属丝 ROI
2. 规范原始数据命名和实验记录
3. 把训练数据进一步收敛到更适合 1D 导热反演的格式

## 目录说明

- [`code/`](/C:/Users/28146/Desktop/thermal-conductivity-project/code)
  - 当前正式使用的采集与分析脚本
- [`code_appendix/`](/C:/Users/28146/Desktop/thermal-conductivity-project/code_appendix)
  - 讲义附录、参考版、历史副本
- [`docs/`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs)
  - 实验日志、项目说明、agent 协作记忆、参考资料
- [`docs/references/`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/references)
  - 讲义原稿和 PDF
- [`data/raw/`](/C:/Users/28146/Desktop/thermal-conductivity-project/data/raw)
  - 本地原始热像数据
- [`data/derived/`](/C:/Users/28146/Desktop/thermal-conductivity-project/data/derived)
  - 本地派生训练数据和中间结果
- [`outputs/preview/`](/C:/Users/28146/Desktop/thermal-conductivity-project/outputs/preview)
  - GIF 等回看结果
- [`outputs/figures/`](/C:/Users/28146/Desktop/thermal-conductivity-project/outputs/figures)
  - 静态分析图

## 常用入口

### 1. 采集热像

树莓派上运行：

```bash
cd ~/experiment/code
sudo python3 thermal90_ir_temp.py
sudo python3 thermal90_ir_temp.py -r
```

项目内对应脚本：

- [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py)

### 2. 回看与静态分析

Windows 本地运行：

```powershell
C:\Users\28146\anaconda3\python.exe code\view_dat.py "C:\Users\28146\Desktop\thermal-conductivity-project\data\raw\<your-file>.dat"
```

### 3. 构建 ROI 训练数据

```powershell
C:\Users\28146\anaconda3\python.exe code\construct_training_data.py "C:\Users\28146\Desktop\thermal-conductivity-project\data\raw\<your-file>.dat"
```

## 文档入口

- 实验日志：[`docs/06-experiment-log.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/06-experiment-log.md)
- 当前状态：[`docs/agent_memory/current-state.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/current-state.md)
- 问题与修复：[`docs/agent_memory/bugs-and-fixes.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/bugs-and-fixes.md)
- 决策记录：[`docs/agent_memory/decisions.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/decisions.md)
- 下一步动作：[`docs/agent_memory/next-actions.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/next-actions.md)
- 讲义参考：[`docs/references/结合红外热像与AI的金属导热系数测量.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/references/结合红外热像与AI的金属导热系数测量.md)

## 数据管理规则

- 原始热像数据、GIF、PNG、训练输出默认只保留在本地，不纳入 git
- 仓库只跟踪：代码、文档、规则、少量必要元信息
- 新实验数据统一放在 `data/raw/`
- 由脚本生成的结果统一落到 `data/derived/`、`outputs/preview/`、`outputs/figures/`
