# Current State

更新：2026-06-04

## 当前主线

项目当前已经完成：

- `6061` 铝棒黑体化数据的正式 PDE 版 PINN 回测
- 一组同条件铝棒复现实验，结果已表现出初步重复性
- `304` 不锈钢两组测量与回测诊断
- `H59` 黄铜两组测量与回测
- `140 C` 远距离拍摄批次的右端旋钮污染修正

当前最清楚的结论是：

- 这套装置和处理流程对 `6061` 铝棒在此前近距离、较干净视野条件下，已经能给出相对稳定的回测结果
- 对 `304` 这类低导热材料，当前 `铝制支架 + 热台` 的热端结构更容易引入二维传热影响，导致一维回测偏高
- `140 C` 远距离拍摄时，若把整段 `x=0~80` 都当成棒身，右端会混入铁架台旋钮，必须做空间裁剪
- 对 `H59` 这类中高导热材料，`140 C` 条件下在裁掉右端旋钮后，结果已基本收敛到 `~100 W/(m*K)` 量级

## 当前正式模型

- 脚本：`code/train_pinn_1d.py`
- 方程：
  - `T_t = alpha*T_xx - 4h/(rho*cp*D)*(T-T_inf) - 4*epsilon*sigma/(rho*cp*D)*(T^4-T_inf^4)`
- 左边界：
  - 第一列可见棒身像素温度曲线，Dirichlet
- 右边界：
  - `none`
- 初始条件：
  - 前 `5` 帧实测平均温度分布
- 默认帧率：
  - `7 fps`

## 当前最可信结果：6061 铝棒

### 2026-05-22 run02

- 数据：`data/raw/thermal90-20260522-run02.dat`
- ROI：`x=10~80, y=30~34`
- 结果：
  - `k = 169.82 W/(m*K)`

### 2026-05-28 run01

- 数据：`data/raw/thermal90-20260528-run01.dat`
- ROI：`x=0~80, y=28~32`
- 结果：
  - `k = 159.84 W/(m*K)`

### 当前判断

- 两次 `6061` 结果都落在 `160~170 W/(m*K)` 量级
- 当前流程对 `6061` 已表现出初步重复性

## 304：当前仍是诊断级

### 2026-05-28 run02（100 C）

- `k = 47.53 W/(m*K)`

### 2026-06-04 run01（140 C）

- `k = 49.29 W/(m*K)`

### 对 304 的当前判断

- 两次 `304` 主结果都只有约 `48~49 W/(m*K)`
- 提高热台温度没有从根本上解决结果失真问题
- `304` 当前仍应归类为：
  - 低导热材料在当前装置下的局限性诊断数据

## H59：当前约收敛到 100 W/(m*K) 量级

### 2026-05-28 run03（100 C）

- `k = 84.36 W/(m*K)`
- 左端右移 2 列后：`k = 99.93 W/(m*K)`

### 2026-06-04 run02（140 C，原始全长 ROI）

- `k = 100.88 W/(m*K)`

### 2026-06-04 run02（140 C，裁掉右端旋钮后）

- ROI：`x=0~68, y=30~34`
- `k = 100.75 W/(m*K)`
- 当前修正版更可信

### 对 H59 的当前判断

- `H59@140 C` 在裁掉右端旋钮后仍稳定在 `~100 W/(m*K)` 附近
- 这说明 `H59` 当前已经比 `304` 明显更可用
- 当前更稳妥的表述是：
  - `H59` 在现有装置下已经基本收敛到约 `100 W/(m*K)` 的量级

## 6061@140 C：当前不宜替代旧主结果

### 2026-06-04 run03（原始全长 ROI）

- `k = 92.27 W/(m*K)`

### 2026-06-04 run03（裁掉右端旋钮后）

- ROI：`x=0~68, y=30~34`
- `k = 96.40 W/(m*K)`

### 对 6061@140 C 的当前判断

- 裁掉右端污染后，结果确实从 `92.27` 修正到 `96.40 W/(m*K)`
- 但它仍明显低于此前 `6061@100 C` 的 `160~170 W/(m*K)` 量级
- 因此这组 `6061@140 C` 当前更像是“远距离拍摄批次的受污染/受视野影响数据”，不宜直接拿来替代既有 `6061` 主结果

## 当前风险

- `mm_per_px = 2.0` 仍是图像几何标定，不是外部标尺校准
- 当前对 `304` 的问题主要不是训练不收敛，而是实验边界对低导热材料不够理想
- 远距离完整入镜时，右端异物会污染 ROI，后续必须先检查 `x>70` 是否混入铁架台旋钮或其他支撑结构
## 2026-06-04 远距离批次补充标定

- 用户补充了一个新的几何约束：从棒身起始位置到右端旋钮处约为 `120 mm`。
- 对裁掉右端旋钮后的远距离 `140 C` 批次，采用综合标定：
  - 长度标定：`120 / 68 = 1.7647 mm/px`
  - 直径标定：`8 / 4 = 2.0 mm/px`
  - 当前综合值：`mm_per_px = 1.88235`

### H59@140 C（综合标定）

- `k = 89.40 W/(m*K)`
- `alpha = 2.77e-5 m^2/s`
- `h = 11.63 W/m^2/K`

### 6061@140 C（综合标定）

- `k = 88.62 W/(m*K)`
- `alpha = 3.65e-5 m^2/s`
- `h = 11.56 W/m^2/K`

### 当前判断补充

- `mm_per_px` 确实是远距离 `140 C` 批次的主要误差源之一。
- 一旦不再使用默认的 `2.0 mm/px`，`H59` 与 `6061` 的远距离结果都会明显下调。
- 因此这批远距离 `140 C` 数据当前更适合作为“标定敏感性与视野污染诊断数据”，而不宜拿来推翻此前近距离 `6061@100 C` 的主结果。
## 2026-06-04 run04 补充

- 新增一组更近距离的 `6061@140 C` 数据：
  - 数据：`data/raw/thermal90-20260604-run04.dat`
  - 手动 ROI：`x=0~68, y=30~34`
  - `T_inf = 23 C`
  - `k = 113.25 W/(m*K)`
  - `alpha = 4.66e-5 m^2/s`
  - `h = 11.46 W/m^2/K`

### 补充判断

- 这组 `run04` 明显比上一组远距离 `6061@140 C` 更接近合理量级：
  - `run03` 裁剪后：`96.40`
  - `run04`：`113.25`
- 说明相机拉近与手动裁掉右端异物后，`6061@140 C` 的结果会明显回升。
- 但它仍未回到此前近距离 `100 C` 两组 `159.84~169.82 W/(m*K)` 的主结果量级。
- 因此当前更稳妥的结论仍然是：
  - `run04` 证明此前远距离批次确实受视野/标定影响；
  - `6061` 的正式主结果仍优先采用两组 `100 C` 数据。

### run04 左端敏感性补充

- 在 `run04` 中固定 `x_max=68, y=30~34`，只改变左端起点时：
  - `x=0~68`：`k = 113.25`
  - `x=8~68`：`k = 116.07`
  - `x=10~68`：`k = 128.01`
  - `x=12~68`：`k = 149.53`
- 这说明 `run04` 的主要误差源之一，是左端前若干列仍处于热端二维过渡区。
- 对 `140 C` 批次，不能再默认把第一列可见棒身直接当成正式边界；至少要做 `x=8/10/12` 级别的左端敏感性检查。

## 2026-06-04 run05 补充

- 新增一组 `6061@140 C`：
  - 数据：`data/raw/thermal90-20260604-run05.dat`
  - 处理：`x=12~68, y=30~34`
  - `k = 152.73 W/(m*K)`
  - `alpha = 6.28e-5 m^2/s`
  - `h = 11.40 W/m^2/K`
  - `MSE = 0.579`

### 补充判断

- `run05` 与 `run04` 的 `x=12~68` 结果已经非常接近：
  - `run04`：`149.53`
  - `run05`：`152.73`
- 这说明在 `6061@140 C` 条件下，只要：
  - 右端异物裁掉
  - 左端从约 `x=12` 后开始取
  - 构图不要太远
  结果就能重新回到合理量级附近。

## 2026-06-05 H59@100 C 支架标定批次

- 新数据：`data/raw/2000.0.0.000000--20260605-160328.dat`
- 用户新增第二金属支架：距初始加热端支架约 `99 mm`。
- 视频显示坐标：第一支架右端 `x=4`，第二支架左端 `x=250`。
- 诊断图显示第二支架在 Thermal-90 原始热像中约从 `x≈62` 开始，因此按约 `4x` 显示缩放换算：
  - `mm_per_px = 99 / ((250 - 4) / 4) = 1.60976`
- 帧率按视频首尾时间重算：
  - `16:03:28` 到 `16:12:20`，`3205` 帧，`fps = 6.02256`
- 主 ROI：
  - `x=12~56, y=30~34`
  - 避开左端支架过渡区，并在第二支架 `x≈62` 前提前裁断
- PINN 结果：
  - `x=8~56`: `k = 73.60 W/(m*K)`
  - `x=10~56`: `k = 66.54 W/(m*K)`
  - `x=12~56`: `k = 60.09 W/(m*K)`
  - `x=12~58`: `k = 58.10 W/(m*K)`
- 这些 500 epoch 结果后续确认未充分收敛，只能作为快速诊断。
- 2000 epoch 长训练结果：
  - `x=12~56`: `k = 95.55 W/(m*K)`, `MSE = 0.097 C^2`
  - `x=12~58`: `k = 90.34 W/(m*K)`, `MSE = 0.098 C^2`
- 当前判断：
  - 本次标定几何比单纯直径标定更可靠，但新增支架本身引入明显二维边界影响。
  - 主判断应采用 2000 epoch 结果，约 `90~96 W/(m*K)`。
  - 该批次与此前 `H59 ~90~100 W/(m*K)` 主判断基本一致，但仍更适合作为“长度标定与支架二维影响诊断”数据；若要强化材料主结果，建议补避开支架的复现实验。

## 2026-06-05 PINN 训练控制优化

- `code/train_pinn_1d.py` 已从单阶段 Adam 扩展为可复用的两阶段训练入口：
  - Adam 阶段支持 `--lr-scheduler plateau`、`--lr-factor`、`--lr-patience`、`--min-lr`
  - 支持 `--resume-checkpoint` 从已有 `.pt` 模型继续训练
  - 支持 Adam 后接 `--lbfgs-steps` 的 LBFGS 微调
  - 支持可选 early stop：`--early-stop-window`
- 训练 history 现在显式记录：
  - `step`
  - `stage`（`adam` / `lbfgs`）
  - `lr`
  - loss 分项和物理参数
- 输出 summary 现在记录：
  - `completed_steps`
  - `stage_counts`
  - optimizer/scheduler/LBFGS 参数
  - `resume_checkpoint`
- LBFGS 阶段每个外层 step 会固定同一批 collocation/boundary 点，避免线搜索 closure 内随机重采样造成二阶优化不稳定。
- 已验证：
  - 单元测试：`python -m unittest tests.test_train_pinn_1d.TrainingControlTests`
  - 真实 smoke：从 `20260605_h59_100c_160328_x12_56_calib99mm_e2000_pinn.pt` 以 `--epochs 0 --resume-checkpoint ... --lbfgs-steps 1` 启动，summary 正确记录 `stage_counts={"lbfgs":1}`。

## 2026-06-07 PINN 采样与损失优化

- `code/train_pinn_1d.py` 已新增第一轮低风险训练优化入口：
  - `--data-batch-size`：观测数据项可用较大 mini-batch；默认 `0` 保持旧的全量 data loss。
  - `--pde-sampling mixed`：PDE 配点按 `70%` 全域、`20%` 热端附近、`10%` 早期时间采样。
  - `--data-weighting delta-initial`：按相对初始温度变化提高升温前沿权重。
- summary 现在额外记录 `data_batch_size`、`pde_sampling`、`data_weighting`、`data_weighting_config`、`full_temperature_mse_c2`、`final_unweighted_data_loss`。
- 已完成验证：
  - `python -m unittest discover -s tests`
  - H59 真实 `.npz` smoke：`--epochs 2 --data-batch-size 1024 --pde-sampling mixed --data-weighting delta-initial --lbfgs-steps 1`
- 当前判断：
  - 这次只改变训练采样和 data loss 权重，不改变 PDE、边界条件或反演参数。
  - 正式结果仍需用同一 ROI 做旧/新训练对照，并优先看 `alpha/h/k` 稳定性和全量未加权 MSE。

## 2026-06-07 H59@100 C new PINN rerun

- Dataset: `data/derived/20260605_h59_100c_160328_x12_56_calib99mm/2000.0.0.000000--20260605-160328_rod_xt_data.npz`
- Calibration: `mm_per_px = 1.6097561120986938`
- Main ROI: `x=12~56, y=30~34`
- Optimized new-PINN config: `--epochs 2000 --lr-scheduler plateau --lbfgs-steps 300 --data-batch-size 16384 --pde-sampling mixed --data-weighting delta-initial`
  - `k = 71.10 W/(m*K)`
  - `alpha = 2.20116e-5 m^2/s`
  - `h = 10.56 W/m^2/K`
  - `full_temperature_mse_c2 = 0.09794`
  - `stage_counts = {"adam": 2000, "lbfgs": 300}`
- Same new code with legacy objective, full data, uniform PDE, no data weighting, 2000 Adam, no LBFGS:
  - `k = 94.60 W/(m*K)`
  - `alpha = 2.92891e-5 m^2/s`
  - `h = 10.48 W/m^2/K`
  - `full_temperature_mse_c2 = 0.09758`
- Current interpretation: optimized new-PINN training pulls this H59 batch down to about `71 W/(m*K)`, while full MSE is almost unchanged. Legacy objective still reproduces about `95 W/(m*K)`. Treat `71 W/(m*K)` as a sampling/weighting-objective result, not a replacement H59 main conclusion, until multi-seed and ROI sensitivity checks are done.
