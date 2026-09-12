# 基于红外热像与 PINN 的金属热导率瞬态反演

本项目使用 **Raspberry Pi 5 + Thermal-90 红外热像仪**记录金属圆棒的瞬态温度场，将热像数据整理为轴向温度场 $T(x,t)$，再结合一维非稳态导热方程，通过 PINN 和确定性前向 PDE 拟合反演材料热导率。

项目重点不仅是得到一个热导率数值，还包括验证反演链路、识别参数不可辨识问题，并分析真实实验中的支架换热、二维热端效应、空间标定和 ROI 选择误差。

## 复试速览

| 问题 | 本项目的回答 |
| --- | --- |
| 测量对象 | 黑体化的 H59 黄铜、6061 铝合金和 304 不锈钢圆棒 |
| 原始观测 | Thermal-90 输出的 $62\times80$ 逐像素摄氏温度帧 |
| 神经网络输入/输出 | 输入归一化坐标 $(x,t)$，输出归一化温度 $\hat T(x,t)$ |
| PINN 学习的物理量 | 学习热扩散率 $\alpha$；由 $k=\rho c_p\alpha$ 换算热导率 |
| 物理约束 | 一维非稳态轴向导热，同时考虑侧面对流和辐射散热 |
| 验证方式 | 独立有限差分正向求解器生成盲测数据，并进行噪声、窗口和多随机种子验证 |
| 真实数据正式估计 | 扫描加热端 $30/40/50/60\,\mathrm{mm}$ 子域，采用双实测边界、固定 $h=10$，只拟合 $k$ |
| 当前结果 | H59 三组平均 $107.02\,\mathrm{W/(m\cdot K)}$；6061 两组可用数据平均 $159.08\,\mathrm{W/(m\cdot K)}$ |
| 最重要的认识 | 温度拟合误差小不等于热导率正确；必须同时检查 PDE 约束、参数稳定性、ROI 和边界模型 |

## 研究问题与整体方法

传统稳态法需要等待系统达到稳定状态，并容易受到环境散热和接触条件影响。本项目采用瞬态红外测温，在加热过程中同时获得多个空间位置的温度随时间变化，再把热传导方程作为反演约束。

完整数据流如下：

```text
Thermal-90 逐像素温度采集
        ↓
原始 .dat：每行一帧 62×80 温度值
        ↓
读取帧序列并检查热像、时间和样品位置
        ↓
截取棒身 ROI，在棒径方向求平均
        ↓
构造轴向温度场 T(x,t) 与实测边界温度
        ↓
空间、时间、温度归一化
        ↓
PINN：Tθ(x,t) + autograd + PDE residual
        ↓
联合最小化数据、PDE、边界和初始条件损失
        ↓
得到 alpha，并计算 k = rho cp alpha
        ↓
使用合成数据和确定性前向 PDE 对反演结果做独立验证
```

对应核心文件：

1. [`code/thermal90_ir_temp.py`](code/thermal90_ir_temp.py)：热像采集与 `.dat` 记录。
2. [`code/view_dat.py`](code/view_dat.py)：读取并预览 $62\times80$ 温度帧。
3. [`code/extract_rod_profile.py`](code/extract_rod_profile.py)：ROI 提取及 $T(x,t)$ 数据构建。
4. [`code/train_pinn_1d.py`](code/train_pinn_1d.py)：PINN 网络、autograd、损失函数和训练循环。
5. [`code/estimate_conductivity_from_experiment.py`](code/estimate_conductivity_from_experiment.py)：真实数据的正式确定性子域估计。

## 物理模型

当前 PINN 和前向求解器使用的一维瞬态模型为：

$$
\frac{\partial T}{\partial t}
=\alpha\frac{\partial^2T}{\partial x^2}
-\frac{4h}{\rho c_pD}(T-T_\infty)
-\frac{4\varepsilon\sigma}{\rho c_pD}(T^4-T_\infty^4),
$$

其中：

- $\alpha$：热扩散率，单位为 $\mathrm{m^2/s}$；
- $k=\rho c_p\alpha$：热导率，单位为 $\mathrm{W/(m\cdot K)}$；
- $h$：侧向对流换热系数；
- $D$：圆棒直径；
- $\varepsilon$：表面发射率；
- $\sigma$：Stefan–Boltzmann 常数；
- $T_\infty$：环境温度。

一维近似来自对棒身 ROI 沿横向求平均。它要求轴向温度梯度占主导，且分析区域尽量远离支架、热端接触区和其他明显的二维换热结构。

当前模型没有显式反演接触热阻，也没有体热源项。左边界使用 ROI 第一列实测温度；PINN 默认不对可见子域右端施加人工自由端条件；初始条件默认取所选数据前 5 帧的平均温度分布。

## PINN 如何反演热导率

### 网络与自动微分

`SimplePINN` 默认使用 2 维输入、4 个宽度为 64 的 `tanh` 隐藏层和 1 维温度输出：

```text
[x_norm, t_norm]
→ Linear(2, 64) + tanh
→ 3 × [Linear(64, 64) + tanh]
→ Linear(64, 1)
→ T_norm
```

`torch.autograd.grad()` 对网络输出关于输入坐标求导，得到 $T_t$、$T_x$ 和 $T_{xx}$。代码随后按照归一化尺度恢复物理单位，再构造 PDE residual。

### 可学习参数

主程序没有把 $k$ 直接写成 `nn.Parameter`，而是定义：

```python
self.alpha_raw = nn.Parameter(...)
alpha = softplus(alpha_raw) + 1e-9
k = rho * cp * alpha
```

`softplus` 保证 $\alpha>0$，因此在 $\rho,c_p>0$ 时也保证 $k>0$。`h` 同样使用正值参数化，但正式合成验证和真实数据估计优先固定 $h=10\,\mathrm{W/(m^2\cdot K)}$，避免 $k/h$ 联合反演不可辨识。

### 损失函数

实际训练目标包含四项，而不只是数据损失和物理损失：

$$
L=\lambda_dL_{data}+\lambda_pL_{PDE}
+\lambda_bL_{BC}+\lambda_iL_{IC}.
$$

- `data_loss`：网络温度与全部实测 $T(x,t)$ 的均方误差；
- `pde_loss`：随机配点上的 PDE residual 平方均值；
- `bc_loss`：实测左边界温度约束，可选右端 Robin 边界；
- `ic_loss`：实测早期温度分布约束。

优化器默认使用 Adam，并可接续 LBFGS。网络权重、`alpha_raw` 以及未固定时的 `h_raw` 会在同一次反向传播中更新。

## 为什么增加确定性前向 PDE 估计

合成数据验证表明：当数据与 PINN 使用相同 PDE、边界和观测机制时，PINN 能恢复已知热导率。但真实热像数据暴露出两个问题：

1. 全长 ROI 会跨过支架、热端二维过渡区和远端异常散热区域；
2. 某些训练中温度 MSE 已很小，但 PDE 项相对过弱，$k$ 仍会随训练或损失权重明显漂移。

因此，真实数据的正式结果采用独立的确定性方法复核：

- 从加热端扫描 $30/40/50/60\,\mathrm{mm}$ 子域；
- 子域左右两端都使用实测 Dirichlet 边界；
- 固定 $h=10\,\mathrm{W/(m^2\cdot K)}$，只拟合 $k$；
- 使用训练时间段拟合、留出时间段验证；
- 检查参数是否撞边界、验证 RMSE 和窗口稳定性；
- 所有候选均不合格时，拒绝该录像，而不是挑选接近参考值的中间结果。

这条路线由 [`fit_thermal_parameters_forward.py`](code/fit_thermal_parameters_forward.py) 和 [`estimate_conductivity_from_experiment.py`](code/estimate_conductivity_from_experiment.py) 实现。它不是 PINN，而是对 PINN 真实数据结论的独立物理校验。

## 主要结果

### 合成数据验证

- 使用独立有限差分正向求解器生成 H59 和 6061 温度场；训练数据中不包含真实 $k$。
- 已完成不同时间长度、空间长度、温度噪声和多随机种子测试。
- 正式配置固定 $h=10$，使用 `64×4` 网络、1024 个 PDE 配点、1500 个训练步和独立的 `alpha_lr=2e-3`。
- 结果表明：时间和空间观测窗口必须与材料扩散尺度匹配；延长观测时间不能弥补过短的空间窗口。

详见 [`docs/10-合成数据PINN验证报告.md`](docs/10-合成数据PINN验证报告.md)。

### 真实实验数据

| 材料与批次 | 确定性子域估计 $k$ | 相对参考值偏差 | 状态 |
| --- | ---: | ---: | --- |
| H59，2026-06-05 16:03 | 102.87 | -6.48% | 接受；存在窗口敏感性警告 |
| H59，2026-06-08 14:49 | 116.55 | +5.95% | 接受；仅一个物理候选 |
| H59，2026-06-08 15:56 | 101.64 | -7.60% | 接受；存在窗口敏感性警告 |
| 6061，2026-05-22 run02 | 165.12 | -1.12% | 接受 |
| 6061，2026-05-28 run01 | 153.04 | -8.36% | 接受 |
| 6061，2026-06-08 16:21 | 无 | 无 | 所有窗口撞上界，拒绝 |

汇总结果：

- H59 三组平均 $107.02\,\mathrm{W/(m\cdot K)}$；
- 6061 两组可用数据平均 $159.08\,\mathrm{W/(m\cdot K)}$；
- 5 份被接受数据的单次绝对相对误差最大为 8.36%；
- 304 在当前装置下受热端和支架二维传热影响明显，暂不作为可信材料测量结果。

详细诊断与结果边界见 [`docs/13-真实实验数据热导率反演修正与验证报告.md`](docs/13-真实实验数据热导率反演修正与验证报告.md)。

## 仓库结构

```text
thermal-conductivity-project/
├── README.md                         # 面向复试老师的项目总览
├── code/                             # 所有可执行源码
│   ├── thermal90_ir_temp.py          # 树莓派端采集、显示和 .dat 记录
│   ├── view_dat.py                   # 原始温度帧读取与可视化
│   ├── extract_rod_profile.py        # 棒身 ROI、轴向平均和 x-t 数据导出
│   ├── construct_training_data.py    # 早期通用 x-y-t ROI 数据构造脚本
│   ├── convert_roi_ymean_csv.py      # 外部 ROI 均值 CSV 转标准 x-t NPZ
│   ├── train_pinn_1d.py              # 正式 PINN 网络、PDE、loss 和训练入口
│   ├── train_pinn_1d_minibatch.py    # mini-batch data loss 对照实验
│   ├── generate_synthetic_pde_data.py # 独立正向求解器与合成温度场生成
│   ├── run_synthetic_pinn_sweep.py   # 合成 PINN 批量盲测与断点续跑
│   ├── analyze_synthetic_sweep.py    # 合成测试误差与适用域汇总
│   ├── tune_synthetic_pinn_hyperparameters.py
│   │                                  # PINN 超参数消融
│   ├── diagnose_real_pde_mismatch.py # 真实温度场与前向 PDE 残差诊断
│   ├── fit_thermal_parameters_forward.py
│   │                                  # 有界确定性 PDE 参数拟合
│   ├── estimate_conductivity_from_experiment.py
│   │                                  # 正式真实数据子域热导率估计器
│   └── run_real_forward_validation.py # 多批次真实数据验证
├── configs/                          # 可复现的扫描与验证配置
│   ├── synthetic_pinn_h59_6061.json
│   ├── synthetic_pinn_304_noise0p1.json
│   └── real_forward_validation_h59_6061.json
├── tests/                            # PINN、正向求解、拟合和批处理单元测试
├── data/
│   ├── raw/                          # 原始 Thermal-90 .dat，本地保存、不进 Git
│   └── derived/                      # ROI、CSV、NPZ，本地生成、不进 Git
├── outputs/                          # 模型、曲线、诊断图和批量结果，不进 Git
├── docs/
│   ├── 01-树莓派使用笔记.md
│   ├── 02-linux常用命令.md
│   ├── 03-理论建模问题.md
│   ├── 04-当前建模分析.md
│   ├── 05-实验复现操作手册.md
│   ├── 06-实验进度.md
│   ├── 07-数据记录日志.md
│   ├── 08-视频数据参数.md
│   ├── 09-新数据参数记录.md
│   ├── 10-成功反演结果清单.md
│   ├── 10-合成数据PINN验证报告.md
│   ├── 11-旧实验数据最终PINN配置复验.md
│   ├── 12-真实实验数据PDE残差诊断.md
│   ├── 13-真实实验数据热导率反演修正与验证报告.md
│   ├── 14-结课presentation初稿.md
│   ├── agent_memory/                 # 项目状态、决策和下一步记录
│   └── superpowers/                  # 设计与执行计划
└── .vscode/                          # 编辑器设置
```

### 如何理解这些文件

- `code/` 是“程序做了什么”的唯一依据；文档与代码不一致时，以代码为准。
- `configs/` 保存批量实验的物理参数和训练参数，避免只靠口头记录。
- `tests/` 验证数值求解、参数恢复、边界条件和批处理逻辑。
- `data/` 和 `outputs/` 体积较大且可由本地实验或脚本生成，因此不上传 GitHub。
- `docs/` 保留建模演变、失败分析和实验记录，便于解释“为什么最终采用当前方案”。

## 最短复现流程

### 1. 检查原始热像数据

```powershell
python code\view_dat.py data\raw\<file>.dat
```

### 2. 提取棒身温度场

必须替换为该录像真实的帧率、ROI 和空间标定：

```powershell
python code\extract_rod_profile.py data\raw\<file>.dat `
  --fps <measured_fps> `
  --x-min <x_min> --x-max <x_max> `
  --y-min <y_min> --y-max <y_max> `
  --heat-side left `
  --mm-per-px <measured_mm_per_px> `
  --data-start-frame 0 `
  --output-dir data\derived\<case>
```

### 3. 运行 PINN

下面以 H59 的合成验证配置思想为例：

```powershell
python code\train_pinn_1d.py data\derived\<case>\<stem>_rod_xt_data.npz `
  --epochs 1500 `
  --material-preset h59 `
  --fixed-h 10 `
  --alpha-lr 0.002 `
  --collocation-points 1024 `
  --data-weight 20 `
  --right-bc-mode none `
  --initial-mode measured `
  --output-stem <run_name>
```

训练后重点检查 summary 中的：

```text
thermal_conductivity_w_mk
quality_checks.recommended_for_reporting
recommended_result_source
alpha_m2_s / h_w_m2k
full_temperature_mse_c2
```

### 4. 运行真实数据正式估计器

```powershell
python code\estimate_conductivity_from_experiment.py `
  data\derived\<case>\<stem>_rod_xt_data.npz `
  --output-json outputs\experimental_estimator_v1\<case>.json `
  --material h59 `
  --t-inf-c <ambient_c>
```

若输出 `recommended_for_reporting=false`，应拒绝该录像，不能从中间窗口或中间训练步骤挑选一个接近参考值的结果。

## 面试阅读顺序

如果只准备复试中的项目介绍与连续追问，建议按下面顺序阅读：

1. 本 README：建立完整项目地图。
2. [`code/extract_rod_profile.py`](code/extract_rod_profile.py)：回答红外数据如何变成 $T(x,t)$。
3. [`code/train_pinn_1d.py`](code/train_pinn_1d.py)：掌握 `forward()`、autograd、loss、optimizer 和 $k$ 的反演。
4. [`docs/10-合成数据PINN验证报告.md`](docs/10-合成数据PINN验证报告.md)：回答“你怎么证明 PINN 反演链路有效”。
5. [`docs/13-真实实验数据热导率反演修正与验证报告.md`](docs/13-真实实验数据热导率反演修正与验证报告.md)：回答“为什么真实数据不能只看 PINN loss”。
6. [`docs/14-结课presentation初稿.md`](docs/14-结课presentation初稿.md)：串联口头展示、结果图和高概率提问。

## 局限与下一步

- 当前一维模型无法完全描述支架、根部接触和局部二维温度场。
- 真实数据中 $k$ 与侧向散热参数存在可辨识性问题，因此需要固定或独立测量 $h$。
- 空间标定 `mm_per_px`、真实帧率和 ROI 边界会直接影响二阶空间导数与最终热导率。
- 304 低导热样品更容易受到热端结构和支架影响，当前结果只作为装置局限性诊断。
- 下一步应改进热端边界和支撑结构，引入外部长度标定，并在相同条件下完成多次重复实验。

## 环境说明

数据处理与反演主要依赖 Python、NumPy、SciPy、PyTorch、Matplotlib 和 Pillow。树莓派端采集还需要 Thermal-90 对应的 `senxor`、SPI、I2C 和 GPIO 依赖。

仓库不上传原始热像、派生温度数据、模型权重和批量输出；这些文件由本地实验数据和上述脚本生成。
