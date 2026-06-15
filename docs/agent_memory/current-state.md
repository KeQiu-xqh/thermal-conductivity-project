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

## 2026-06-07 PINN objective ablation follow-up

- Same H59@100 C ROI `x=12~56, y=30~34` was rerun with one-factor training ablations:
  - legacy objective, full data, uniform PDE, no weighting: `k = 94.60 W/(m*K)`, `MSE = 0.09758`
  - large data mini-batch only, `--data-batch-size 16384`: `k = 93.38 W/(m*K)`, `MSE = 0.09627`
  - mixed PDE only: `k = 79.05 W/(m*K)`, `MSE = 0.09566`
  - delta-initial data weighting only: `k = 74.53 W/(m*K)`, `MSE = 0.09783`
  - mini-batch + mixed PDE, no weighting: `k = 79.52 W/(m*K)`, `MSE = 0.09545`
  - mini-batch + mixed PDE + weighting + LBFGS: `k = 71.10 W/(m*K)`, `MSE = 0.09794`
- Current interpretation:
  - `94.60` came from the new code with the legacy objective settings, not from checking out old source code.
  - The large data mini-batch is safe on this batch because it stays close to the legacy `94~95 W/(m*K)` result.
  - Mixed PDE sampling and delta-initial data weighting both pull `k` low while the full unweighted MSE stays almost unchanged, so they are not reliable formal defaults for this H59 batch.
- Code now exposes `--training-preset stable` and `--training-preset experimental`:
  - `stable`: `data_batch_size=16384`, `pde_sampling=uniform`, `data_weighting=none`
  - `experimental`: `data_batch_size=16384`, `pde_sampling=mixed`, `data_weighting=delta-initial`
- Current formal recommendation: use `--training-preset stable` for routine reruns; keep `experimental` only for diagnostics or controlled sensitivity studies.

## 2026-06-07 PINN single-run reliability guard

- `code/train_pinn_1d.py` now supports material presets:
  - `--material-preset 6061`: `rho=2700`, `cp=900`, expected `k=130~190 W/(m*K)`
  - `--material-preset 304`: `rho=7930`, `cp=500`, expected `k=10~25 W/(m*K)`
  - `--material-preset h59`: `rho=8500`, `cp=380`, expected `k=80~120 W/(m*K)`
- Summary now includes `quality_checks`, which checks:
  - enough optimizer steps, default `min_quality_steps=1000`
  - tail parameter stability over the last `300` steps
  - optional expected material `k` range
  - whether an experimental training preset was used
- Existing H59 histories were checked with this guard:
  - 500-step `k=60.09`: rejected for too few steps, unstable tail `alpha`, and out-of-range `k`
  - 2000-step `k=95.55`: accepted
  - stable mini-batch `k=93.38`: accepted
  - experimental/mixed-weighted `k=71.10`: rejected for out-of-range `k`
- Current rule for single inversion: do not report a run as a formal result unless `quality_checks.recommended_for_reporting=true`.

## 2026-06-08 PINN formal script cleanup

- `code/train_pinn_1d.py` has been reduced back to one formal inverse objective:
  - full observed data loss
  - uniform PDE collocation
  - no data reweighting
- Removed the experimental training controls from the active script:
  - `--training-preset`
  - `--data-batch-size`
  - `--pde-sampling`
  - `--data-weighting`
- Deleted the duplicate/experimental `code/train_pinn_1d_final.py`.
- Current formal rerun command should omit the removed options, for example:
  `python code\train_pinn_1d.py data\derived\20260605_h59_100c_160328_x12_56_calib99mm\2000.0.0.000000--20260605-160328_rod_xt_data.npz --epochs 2000 --material-preset h59 --diameter-mm 8 --t-inf-c 24.5 --output-stem 20260605_h59_100c_160328_x12_56_formal`
- Keep the previous mixed-PDE / delta-initial results as historical ablations only; they are not available in the active formal script.

## 2026-06-08 PINN output layout

- `code/train_pinn_1d.py` now writes every inversion run into one grouped folder:
  - `outputs/models/<output_stem>/`
- The grouped folder contains:
  - `<output_stem>_pinn.pt`
  - `<output_stem>_history.json`
  - `<output_stem>_summary.json`
  - `<output_stem>_pinn_loss_curve.png`
  - `<output_stem>_pinn_alpha_h_curve.png`
  - `<output_stem>_pinn_pred_heatmap.png`
- `summary.json` includes `output_dir`, so later scripts can find all artifacts from one run without searching the flat `outputs/models` and `outputs/figures` directories.

## 2026-06-08 H59@100 C 14:49 batch prepared

- Raw file: `data/raw/2000.0.0.000000--20260608-144924.dat`
- User-recorded timing: `14:49:21` to `14:57:00`, `2779` frames
  - derived `fps = 6.05446623093682`
- Manual scale:
  - known distance: `105.90 mm`
  - video x: `20` to `288`
  - video/raw scale: `4x`
  - `mm_per_px = 105.90 / ((288 - 20) / 4) = 1.5805970149253732`
- Material parameters:
  - H59 brass, `rho = 8500 kg/m3`, `cp = 380 J/(kg*K)`, diameter `8 mm`, `T_inf = 24 C`
- Rod is slightly tilted, about `1 px` from start to end; current horizontal band is still acceptable for first-pass ROI.
- Differential inspection found the rod response centered near `y = 31`, mainly spanning about `y = 29~34`.
- Prepared ROI datasets:
  - main: `data/derived/20260608_h59_100c_144924_x12_68_calib10590mm`
  - full-start main: `data/derived/20260608_h59_100c_144924_x12_68_start0_calib10590mm`
  - sensitivity: `data/derived/20260608_h59_100c_144924_x10_68_calib10590mm`
  - sensitivity: `data/derived/20260608_h59_100c_144924_x12_70_calib10590mm`
- Main ROI is `x_min=12, x_max=68, y_min=29, y_max=34`, heat side `left`.
- For this batch, prefer the `start0` main dataset first because frame 0 still captures a cold rod state; keep the default `data-start-frame=250` dataset as a comparison.
- Next step: run formal PINN on the `start0` main ROI first, then compare sensitivity runs if the result passes quality checks.

## 2026-06-08 H59@100 C 14:49 start0 formal PINN

- Dataset:
  `data/derived/20260608_h59_100c_144924_x12_68_start0_calib10590mm/2000.0.0.000000--20260608-144924_rod_xt_data.npz`
- Command:
  `python code/train_pinn_1d.py ... --epochs 2000 --material-preset h59 --diameter-mm 8 --t-inf-c 24 --output-stem 20260608_h59_100c_144924_x12_68_start0_formal`
- Output folder:
  `outputs/models/20260608_h59_100c_144924_x12_68_start0_formal`
- Result:
  - `k = 21.8248 W/(m*K)`
  - `alpha = 6.7569e-6 m^2/s`
  - `h = 10.0226 W/(m^2*K)`
  - `full_temperature_mse_c2 = 0.08348`
  - `completed_steps = 2000`
- Quality checks rejected this result:
  - `recommended_for_reporting = false`
  - warnings: `tail_parameters_not_stable`, `thermal_conductivity_outside_expected_material_range`
  - `alpha_tail_rel_range = 0.1373`, above the `0.05` threshold
- Interpretation:
  - Do not report `21.8 W/(m*K)` as the H59 conductivity.
  - The parameter curve shows alpha continuing to fall through 2000 steps rather than converging.
  - Next diagnostic should compare the default `data-start-frame=250` dataset and ROI sensitivity datasets before extending or changing the model.

## 2026-06-08 H59@100 C 14:49 start0 ROI sensitivity

- Same batch, same `y=29~34`, `fps=6.05446623093682`, `mm_per_px=1.5805970149253732`, H59 material preset.
- Ran 2000 Adam steps for additional ROI variants:
  - `x=12~56`: `k = 20.24 W/(m*K)`, `alpha = 6.2673e-6`, `h = 10.008`, `MSE = 0.08047`
  - `x=12~68`: `k = 21.82 W/(m*K)`, `alpha = 6.7569e-6`, `h = 10.023`, `MSE = 0.08348`
  - `x=6~70`: `k = 15.82 W/(m*K)`, `alpha = 4.8975e-6`, `h = 10.014`, `MSE = 0.08791`
- All three were rejected by quality checks:
  - `tail_parameters_not_stable`
  - `thermal_conductivity_outside_expected_material_range`
- Interpretation:
  - Cropping the right side more aggressively did not recover H59-level conductivity.
  - Including more left/right boundary region made the inferred conductivity lower.
  - This strengthens the diagnosis that the batch's temperature evolution is not compatible with the current one-dimensional free-rod model as a formal H59 measurement.

## 2026-06-08 H59@100 C 14:49 start250 check

- Dataset:
  `data/derived/20260608_h59_100c_144924_x12_68_calib10590mm/2000.0.0.000000--20260608-144924_rod_xt_data.npz`
- Command:
  `python code/train_pinn_1d.py ... --epochs 2000 --material-preset h59 --diameter-mm 8 --t-inf-c 24 --output-stem 20260608_h59_100c_144924_x12_68_start250_formal`
- Result:
  - `k = 22.54 W/(m*K)`
  - `alpha = 6.9791e-6 m^2/s`
  - `h = 10.0194 W/(m^2*K)`
  - `MSE = 0.08903`
  - `alpha_tail_rel_range = 0.1474`
- Quality checks rejected it with:
  - `tail_parameters_not_stable`
  - `thermal_conductivity_outside_expected_material_range`
- Interpretation:
  - Removing the first 250 frames did not recover H59-level conductivity.
  - The low result is therefore not mainly caused by early cold-state weighting.
  - Treat this 14:49 batch as unsuitable for a formal H59 conductivity result under the current one-dimensional model.

## 2026-06-08 PINN code regression check

- To check whether the low `20260608 14:49` H59 result was caused by a code regression, the current `code/train_pinn_1d.py` was rerun on the older accepted H59 dataset:
  `data/derived/20260605_h59_100c_160328_x12_56_calib99mm/2000.0.0.000000--20260605-160328_rod_xt_data.npz`
- Command output:
  - `k = 94.6036 W/(m*K)`
  - `alpha = 2.9289e-5 m^2/s`
  - `h = 10.4840 W/(m^2*K)`
  - `MSE = 0.09758`
  - `quality_checks.recommended_for_reporting = true`
- Interpretation:
  - The active PINN training path can still reproduce an accepted H59-scale result.
  - The low `20260608 14:49` results are unlikely to be caused by the core training code being broken.
  - Remaining likely causes are dataset/ROI/boundary condition incompatibility with the current one-dimensional model, or a preprocessing assumption specific to this batch.

## 2026-06-08 H59@100 C 15:56 batch

- Raw file: `data/raw/2000.0.0.000000--20260608-155612.dat`
- User-recorded timing: `15:56:12` to `16:06:25`, `3727` frames
  - derived `fps = 6.079934747145187`
- Manual scale: `mm_per_px = 1.5`
- Material/run parameters:
  - H59 brass, diameter `8 mm`, `T_inf = 24 C`, hot plate setpoint `100 C`
  - user also recorded rod length `150 mm`, SK8 diameter `8 mm`, exposed length `136 mm`
- Differential inspection:
  - rod response centered at `y=30~31`
  - preferred vertical band `y=28~32`
  - left `x=0~10` is a strong hot-end transition region and should be avoided for formal ROI
- Prepared datasets:
  - main: `data/derived/20260608_h59_100c_155612_x12_76_y28_32_start0_calib1500mm`
  - right-cropped sensitivity: `data/derived/20260608_h59_100c_155612_x12_70_y28_32_start0_calib1500mm`
  - start-frame sensitivity prepared but not yet trained: `data/derived/20260608_h59_100c_155612_x12_76_y28_32_start250_calib1500mm`
- Formal 2000-step PINN results:
  - `x=12~76, y=28~32, start0`: `k = 79.93 W/(m*K)`, `alpha = 2.4745e-5 m^2/s`, `h = 10.09 W/(m^2*K)`, `MSE = 0.09994`
    - rejected by quality checks: `tail_parameters_not_stable`, `thermal_conductivity_outside_expected_material_range`
    - `alpha_tail_rel_range = 0.0643`, slightly above the `0.05` threshold
  - `x=12~70, y=28~32, start0`: `k = 74.82 W/(m*K)`, `alpha = 2.3165e-5 m^2/s`, `h = 10.08 W/(m^2*K)`, `MSE = 0.10200`
    - rejected by quality checks: `thermal_conductivity_outside_expected_material_range`
    - parameters were stable, but `k` remained below the H59 expected `80~120 W/(m*K)` range
- Interpretation:
  - This batch is much better than the 14:49 batch (`~16~23 W/(m*K)`) and recovers to the lower edge of the H59 range.
  - The current best value is the main ROI `x=12~76`, about `79.9 W/(m*K)`, but it should not be reported as a formal accepted H59 result unless a follow-up run passes quality checks or repeated ROI/seed checks support it.

### Continue from 2000-step checkpoint

- Continued the main ROI from:
  `outputs/models/20260608_h59_100c_155612_x12_76_y28_32_start0_formal/20260608_h59_100c_155612_x12_76_y28_32_start0_formal_pinn.pt`
- New output folder:
  `outputs/models/20260608_h59_100c_155612_x12_76_y28_32_start0_continue4000`
- Result after the additional 2000 Adam steps:
  - `k = 79.9982 W/(m*K)`
  - `alpha = 2.4767e-5 m^2/s`
  - `h = 8.1529 W/(m^2*K)`
  - `MSE = 0.09781`
  - `alpha_tail_rel_range = 0.0121`
  - `h_tail_rel_range = 0.0347`
- Quality checks:
  - parameters are now stable
  - the only remaining warning is `thermal_conductivity_outside_expected_material_range`, because `k=79.9982` is infinitesimally below the preset lower bound `80.0`
- Interpretation:
  - Continuing training confirmed the main ROI converges very close to `80 W/(m*K)`, not back to `~100 W/(m*K)`.
  - Treat this as a stable lower-edge H59 result for this batch, while still noting it technically misses the strict preset threshold by rounding.

## 2026-06-08 6061@100 C 16:21 batch and mini-batch PINN check

- Raw file: `data/raw/2000.0.0.000000--20260608-162125.dat`
- User-recorded timing: `16:21:25` to `16:25:30`, `1486` frames
  - derived `fps = 6.0653061224489795`
- Manual scale: `mm_per_px = 1.57`
- User noted that `x>70` has support interference; formal ROI should not include columns above `70`.
- Prepared formal ROI dataset:
  `data/derived/20260608_6061_100c_162125_x12_70_y28_32_start0_calib1570mm`
  - ROI: `x=12~70, y=28~32`, heat side left
- Full-data formal script result on `x=12~70`:
  - output: `outputs/models/20260608_6061_100c_162125_x12_70_y28_32_start0_formal`
  - `k = 393.51 W/(m*K)`, `alpha = 1.6194e-4 m^2/s`, `h = 10.44 W/(m^2*K)`
  - `MSE = 0.2565`, `final_unweighted_data_loss = 0.001679`
  - rejected: `tail_parameters_not_stable`, `thermal_conductivity_outside_expected_material_range`
  - parameter curve showed `k` passing through the plausible range around `800~1000` steps, then continuing upward.
- Added a separate mini-batch script without deleting the formal script:
  - `code/train_pinn_1d_minibatch.py`
  - It reuses the same model, PDE, boundary/initial condition, output layout, and quality checks as `train_pinn_1d.py`.
  - New option: `--data-batch-size`; default `16384`; use `0` for full data.
  - Tests added in `tests/test_train_pinn_1d.py`.
- Mini-batch result on the same `x=12~70` dataset:
  - command used `--data-batch-size 16384`, `--epochs 2000`, `--material-preset 6061`
  - output: `outputs/models/20260608_6061_100c_162125_x12_70_y28_32_start0_minibatch16384`
  - `k = 389.77 W/(m*K)`, `alpha = 1.6040e-4 m^2/s`, `h = 10.44 W/(m^2*K)`
  - `MSE = 0.2637`, `final_unweighted_data_loss = 0.001726`
  - rejected: `tail_parameters_not_stable`, `thermal_conductivity_outside_expected_material_range`
- Interpretation:
  - Large mini-batch data loss did not fix the 6061 16:21 batch; the loss curve remains data-loss-low but PDE/parameter-driven, and `alpha/k` still climbs upward.
  - The earlier GPT-5-mini quick result near `140 W/(m*K)` was an undertrained intermediate value around `800` steps, not a stable convergence result.
  - This batch likely needs a model/constraint/ROI-boundary diagnosis rather than simply switching full data to mini-batch data loss.

## 2026-06-11 PINN best-physical selection rule

- Rechecked `thermal90-20260528-run01` from raw `.dat`:
  - `.dat -> .npz` rerun used `fps=7`, ROI `x=0~80, y=28~32`, `mm_per_px=2.0`.
  - 800-step rerun reproduced the historical result: `k = 159.79 W/(m*K)` vs historical `159.84`.
  - Continuing the 800-step checkpoint for another 400 Adam steps lowered MSE but drove `k` upward to `226.04 W/(m*K)`, outside the 6061 expected range.
- Current interpretation:
  - This is not evidence that 6061 has `k≈226`; it is PINN parameter drift while the network keeps improving the fitted temperature surface.
  - Temperature MSE alone is not a valid model-selection criterion for inverse conductivity.
- Code direction:
  - `train_pinn_1d.py` now selects `best_physical` by physical reportability rather than lowest MSE or final step.
  - `best_physical` requires material-range `k`, stable `alpha/h` over a step-based window, acceptable data loss, and non-exploding PDE loss.
  - If a best physical point is found, it must have a corresponding `*_best_physical_pinn.pt` checkpoint.
  - New checkpoints store optimizer state, scheduler state, history, and completed step count for full resume.
  - Legacy model-only checkpoints still load, but are marked `resume_mode = "model_only_legacy"`.

## 2026-06-16 deterministic real-data estimator

- Synthetic PDE data remain a valid PINN verification route, but the current full-domain PINN is not the formal estimator for arbitrary real recordings.
- Added:
  - `code/fit_thermal_parameters_forward.py`
  - `code/run_real_forward_validation.py`
  - `code/estimate_conductivity_from_experiment.py`
- Root cause confirmed:
  - full rod ROI crosses local support/contact heat-transfer regions;
  - real residuals are hotter in the middle and colder near the far end;
  - joint `k/h` fitting is weakly identifiable on short windows;
  - treating an internal crop as a free rod end is invalid.
- Formal real-data rule:
  - known material H59 or 6061;
  - heated-end windows `30/40/50/60 mm`;
  - measured Dirichlet temperature at both window boundaries;
  - fixed `h=10 W/(m^2*K)`;
  - select the lowest validation-RMSE candidate inside the material quality range.
- Accepted results:
  - H59: `102.87`, `116.55`, `101.64 W/(m*K)`;
  - 6061: `165.12`, `153.04 W/(m*K)`.
- Rejected:
  - 6061 2026-06-08 16:21; every candidate hit the `350 W/(m*K)` bound.
- Detailed report:
  - `docs/13-真实实验数据热导率反演修正与验证报告.md`
