# Thermal-90 金属导热实验项目

本仓库用于维护一套基于 **Raspberry Pi 5 + Thermal-90 红外热像 + 金属圆棒样品 + PINN 反演** 的导热系数实验流程。

当前主线不是采集链路验证，而是围绕已采集的 `.dat` 热像数据，完成 ROI 提取、`x,t -> T` 数据构建、非稳态一维导热 PINN 回测和结果可信度判断。

## 仓库结构

```text
thermal-conductivity-project/
├── .codex/                              # Codex 项目级技能配置
│   └── skills/
│       └── thermal-conductivity-lab/    # 本项目专用工作流和项目记忆入口
├── .vscode/                             # VS Code 项目设置
├── code/                                # 当前正式使用的代码
│   ├── construct_training_data.py       # 从 Thermal-90 原始数据构建训练数据
│   ├── extract_rod_profile.py           # 提取金属棒 ROI / 轴向温度分布
│   ├── thermal90_ir_temp.py             # Thermal-90 采集、温度解析、实时显示和录制
│   ├── train_pinn_1d.py                 # 当前正式 PINN 反演训练脚本
│   └── view_dat.py                      # 查看和预览 .dat 热像数据
├── data/
│   ├── raw/                             # Thermal-90 原始 .dat 数据
│   └── derived/                         # ROI、xt/xyt 训练数据和 meta
├── docs/
│   ├── agent_memory/                    # 项目状态、决策和下一步动作
│   ├── 02-树莓派使用笔记.md             # Raspberry Pi / VNC / Thermal-90 基础笔记
│   ├── 04-linux常用命令.md              # Linux 命令行备忘
│   ├── 05-数据记录日志.md               # 实验数据和分析结果详细日志
│   ├── 06-实验进度.md                   # 当前阶段、主结果、风险和下一步
│   ├── 07-实验复现操作手册.md           # 从连接树莓派到录制、拷回、回看的完整流程
│   ├── 08-当前建模分析.md               # 当前 PDE、ROI、训练数据和 PINN 反演说明
│   └── 理论建模问题.md                  # 理论质疑、建模边界和不可行路线记录
├── outputs/
│   ├── figures/                         # 曲线图、热图、ROI 图、诊断图
│   ├── models/                          # PINN 模型权重、history、summary
│   └── preview/                         # 原始热像数据 GIF 预览
├── tests/                               # 自动测试
├── .gitignore
└── README.md
```

## 核心脚本

### 1. Thermal-90 实时采集

脚本：[`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py)

在 Raspberry Pi 端运行，用于实时热像显示和录制：

```bash
cd ~/experiment/code
sudo python3 thermal90_ir_temp.py
sudo python3 thermal90_ir_temp.py -r
```

说明：

- 实时热像窗口需要在 **VNC 桌面终端** 中运行。
- 纯 SSH 终端适合检查状态和拷文件，不适合直接运行图形显示。

### 2. 原始数据回看

脚本：[`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py)

Windows 本地示例：

```powershell
python code\view_dat.py data\raw\<your-file>.dat
```

典型输出：

- `outputs/preview/<stem>_preview.gif`
- `outputs/figures/<stem>_frames_compare.png`
- `outputs/figures/<stem>_center_temp_curve.png`
- `outputs/figures/<stem>_hot_roi_curve.png`

### 3. ROI 与训练数据构建

脚本：[`code/extract_rod_profile.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/extract_rod_profile.py)

作用：

- 从 `.dat` 中提取金属棒 ROI。
- 生成一维 `x,t -> T` 训练数据。
- 输出 ROI 叠加图、`x-t` 热图和 meta。

### 4. PINN 反演

脚本：[`code/train_pinn_1d.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/train_pinn_1d.py)

当前物理模型：

```text
T_t = alpha*T_xx
      - 4h/(rho*cp*D)*(T-T_inf)
      - 4*epsilon*sigma/(rho*cp*D)*(T^4-T_inf^4)
```

当前训练控制已支持：

- `--lr-scheduler plateau`
- `--resume-checkpoint`
- `--lbfgs-steps`
- `--early-stop-window`

## 当前文档入口

- 实验复现流程：[`docs/07-实验复现操作手册.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/07-%E5%AE%9E%E9%AA%8C%E5%A4%8D%E7%8E%B0%E6%93%8D%E4%BD%9C%E6%89%8B%E5%86%8C.md)
- 数据记录日志：[`docs/05-数据记录日志.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/05-%E6%95%B0%E6%8D%AE%E8%AE%B0%E5%BD%95%E6%97%A5%E5%BF%97.md)
- 实验进度汇总：[`docs/06-实验进度.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/06-%E5%AE%9E%E9%AA%8C%E8%BF%9B%E5%BA%A6.md)
- 当前建模分析：[`docs/08-当前建模分析.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/08-%E5%BD%93%E5%89%8D%E5%BB%BA%E6%A8%A1%E5%88%86%E6%9E%90.md)
- 理论建模问题：[`docs/理论建模问题.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/%E7%90%86%E8%AE%BA%E5%BB%BA%E6%A8%A1%E9%97%AE%E9%A2%98.md)
- 树莓派使用笔记：[`docs/02-树莓派使用笔记.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/02-%E6%A0%91%E8%8E%93%E6%B4%BE%E4%BD%BF%E7%94%A8%E7%AC%94%E8%AE%B0.md)
- Linux 命令备忘：[`docs/04-linux常用命令.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/04-linux%E5%B8%B8%E7%94%A8%E5%91%BD%E4%BB%A4.md)
- 当前状态：[`docs/agent_memory/current-state.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/current-state.md)
- 下一步动作：[`docs/agent_memory/next-actions.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/next-actions.md)

## 数据管理规则

- 原始 `.dat` 数据是本地实验资产，默认放在 `data/raw/`。
- 派生训练数据放在 `data/derived/`。
- 图像、模型、history 和 summary 放在 `outputs/`。
- 不把普通录屏视频当作正式训练源数据。
- 写正式结论时必须同时报告 ROI、帧率、`mm_per_px`、材料参数和训练 summary。

## 当前提醒

- `6061` 当前主结果仍优先采用两组近距离 `100 C` 黑体化数据。
- `304` 当前更适合作为装置局限性诊断数据。
- `H59` 当前结果大致收敛到 `90~100 W/(m*K)` 量级。
- 远距离完整入镜时，右端 `x>70` 可能混入铁架台旋钮，不能默认把整段 `x=0~80` 都当成棒身。

## 合成数据 PINN 验证

项目提供独立有限差分正向求解器，用 H59 和 6061 的已知参数生成温度场，再盲测 PINN：

```powershell
# 查看全部 300 个粗筛任务
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode list

# 先跑两个任务检查环境
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode coarse --limit 2 --max-workers 1

# 断点续跑完整粗筛
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode coarse --max-workers 1

# 汇总误差和适用域
python code\analyze_synthetic_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1
```

正式推荐配置固定 `h=10 W/(m^2*K)`，使用 `1500 epochs`、`alpha_lr=2e-3`、
`64x4` 网络、`1024` 个 PDE 配点和 `data_weight=20`。联合反演 `h` 仅作诊断，
必须经过多初值验证后才能报告。

完整验证已经运行 `300/300` 个粗筛任务及 `60/60` 个五种子复筛任务：

```powershell
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id final_v2 --mode coarse --max-workers 2
python code\analyze_synthetic_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id final_v2

python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id final_v2_refinement --mode refinement --refinement-file outputs\synthetic_pinn\final_v2\analysis\refinement_cases.json --max-workers 2
python code\analyze_synthetic_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id final_v2_refinement
```

超参数消融入口为 `code/tune_synthetic_pinn_hyperparameters.py`，详细结论见
`docs/10-合成数据PINN验证报告.md`。
