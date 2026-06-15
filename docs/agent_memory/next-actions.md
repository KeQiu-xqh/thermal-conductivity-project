# Next Actions

更新：2026-06-04

1. 不再优先追加 `304` 实验；当前两次 `304` 都说明提高热台温度没有根本解决边界失真问题。
2. 若继续做材料测量，优先补一组 `H59@140 C` 的同条件复现实验，确认当前 `~100 W/(m*K)` 量级是否稳定。
3. 若继续做远距离完整入镜实验，先检查右端 `x>70` 是否混入铁架台旋钮，再决定 `x_max`，不要再默认把整段 `x=0~80` 都当成棒身。
4. 对正式总结要明确区分：
   - `6061`：当前主结果仍以此前 `100 C` 近距离批次为准
   - `304`：当前更适合作为装置局限性诊断数据
   - `H59`：当前已比 `304` 更可用，并基本收敛到 `~100 W/(m*K)` 量级
5. 若继续分析 `2026-06-04` 的远距离 `140 C` 批次，不要默认使用 `mm_per_px = 2.0`；优先同时报告：
   - 裁掉右端旋钮后的 ROI
   - `2.0 mm/px` 结果
   - `120 mm + 8 mm` 综合标定结果
6. 若需要正式对比 `6061` 与 `H59` 的绝对热导率，优先回到近距离、较干净视野条件，而不是继续依赖这批远距离完整入镜数据。
7. 若继续追 `6061@140 C`，优先复用 `run04` 这类更近距离构图，并继续手动裁掉右端异物；不要再直接用整段 `x=0~80`。
8. 若要判断 `140 C` 是否本身会改变 `6061` 回测量级，下一步应在 `run04` 这种更近距离条件下再补 1 组复现实验，而不是回到更远距离视野。
9. `run04` 与 `run05` 已表明 `6061@140 C` 的推荐正式处理可暂定为：
   - 右端裁到 `x_max = 68`
   - 左端至少从 `x_min = 12` 开始
   - 高度带优先 `y=30~34`
10. 对 `2026-06-05 16:03:28` 的 `H59@100 C` 支架标定批次，当前不要直接拿来替代 H59 主结果：
   - 主 ROI `x=12~56/58, y=30~34`
   - 按第二支架 `99 mm` 与视频约 `4x` 缩放标定，`mm_per_px = 1.60976`
   - 500 epoch 快速结果曾低到 `58~60 W/(m*K)`，但后续确认训练未充分收敛，不作为正式结论
   - 2000 epoch 长训练后，当前主判断约 `k = 90~96 W/(m*K)`
   - 该值与此前 `H59 ~90~100 W/(m*K)` 基本一致，但该批次仍更适合作为支架标定和二维边界影响诊断数据
11. 若继续测 `H59` 主结果，优先保留这次 `99 mm` 支架标定思路，但正式 ROI 应同时远离两个支架：
   - 左端至少从 `x_min≈12` 后开始
   - 第二支架若在原始热像 `x≈62`，右端建议先裁到 `x_max≈56`
   - 最好再做一组无新增支架或支架更远离 ROI 的复现实验，用来区分材料结果与支架二维影响
12. 后续正式 PINN 反演不要再只跑短 Adam 轮数。当前正式训练入口先用 `--training-preset stable`，它只启用大 data mini-batch，保持 uniform PDE 和未加权 data loss：
   - 稳定版正式命令：
     `python code\train_pinn_1d.py data\derived\20260605_h59_100c_160328_x12_56_calib99mm\2000.0.0.000000--20260605-160328_rod_xt_data.npz --epochs 2000 --training-preset stable --material-preset h59 --diameter-mm 8 --t-inf-c 24.5 --output-stem 20260605_h59_100c_160328_x12_56_stable`
   - 判断是否可采信时先看 summary 的 `quality_checks.recommended_for_reporting`；若为 `false`，不要把最终 `k` 当正式热导率。
   - 若被拒绝，按 warning 类型处理：步数不足就延长训练，末段参数不稳就继续训练/接 LBFGS，材料范围外就优先检查 ROI、标定、材料 preset 和训练目标函数。
13. `--training-preset experimental` 目前只作为诊断选项，不作为正式默认：
   - 它会启用 `--pde-sampling mixed` 和 `--data-weighting delta-initial`。
   - H59@100 C 主 ROI 消融显示 mixed PDE 会把 `k` 拉到约 `79 W/(m*K)`，delta-initial weighting 会拉到约 `75 W/(m*K)`，二者叠加并接 LBFGS 后约 `71 W/(m*K)`。
   - 这些结果的全量未加权 MSE 与旧目标函数几乎相同，说明 MSE 不能单独判断物理反演是否更可信。
14. 下一步若继续提高 PINN 可信度，优先在单次反演入口里继续强化质量守卫和 ROI/标定诊断，而不是先做批量反演；每个单次结果都必须通过 `quality_checks` 后再进入材料结论。

## 2026-06-08 更新

- 正式 PINN 入口已回到单一目标函数：全量观测数据、uniform PDE 配点、无 data weighting。
- 旧的 `--training-preset`、`--data-batch-size`、`--pde-sampling`、`--data-weighting` 已从 `code/train_pinn_1d.py` 删除；后续命令不要再使用这些参数。
- 若重跑 H59@100 C 主 ROI，使用：
  `python code\train_pinn_1d.py data\derived\20260605_h59_100c_160328_x12_56_calib99mm\2000.0.0.000000--20260605-160328_rod_xt_data.npz --epochs 2000 --material-preset h59 --diameter-mm 8 --t-inf-c 24.5 --output-stem 20260605_h59_100c_160328_x12_56_formal`
- 每次反演的输出会集中在：
  `outputs\models\<output_stem>\`

## 2026-06-08 H59@100 C 14:49 batch

- Main prepared dataset:
  `data\derived\20260608_h59_100c_144924_x12_68_start0_calib10590mm\2000.0.0.000000--20260608-144924_rod_xt_data.npz`
- Recommended first formal command:
  `python code\train_pinn_1d.py data\derived\20260608_h59_100c_144924_x12_68_start0_calib10590mm\2000.0.0.000000--20260608-144924_rod_xt_data.npz --epochs 2000 --material-preset h59 --diameter-mm 8 --t-inf-c 24 --output-stem 20260608_h59_100c_144924_x12_68_start0_formal`
- If the main result is unstable or near a decision boundary, rerun the sensitivity datasets `x10_68` and `x12_70`.
- The first `start0` formal run was rejected (`k=21.82`, alpha tail unstable and outside H59 range); do not use it as a material result.
- Next diagnostics:
  1. The default `data-start-frame=250` main dataset was also rejected: `k=22.54 W/(m*K)`.
  2. Current ROI/start sensitivity rejected `x12~56`, `x12~68 start0`, `x6~70`, and `x12~68 start250`, with `k=15.8~22.5 W/(m*K)`.
  3. Treat this batch as unsuitable for a formal H59 conductivity result under the current one-dimensional model.

## 2026-06-08 H59@100 C 15:56 batch

- Main result so far:
  `x=12~76, y=28~32, start0`, `mm_per_px=1.5`, `fps=6.079934747145187`
  - `k = 79.93 W/(m*K)`, `alpha = 2.4745e-5`, `h = 10.09`, `MSE = 0.09994`
  - quality checks still reject it because alpha tail is slightly unstable and k is just below the H59 expected lower bound.
- Right-cropped sensitivity:
  `x=12~70, y=28~32, start0`
  - `k = 74.82 W/(m*K)`, parameters stable, but still below H59 expected range.
- Next diagnostics if this batch is pursued:
  1. Train the already-prepared `start250` dataset for `x=12~76, y=28~32`.
  2. If `start250` is still low, try one additional seed on the main ROI before treating `~80 W/(m*K)` as the batch's stable level.
  3. Do not report this batch as a formal accepted H59 result until `quality_checks.recommended_for_reporting=true` or repeated checks justify overriding the narrow `80 W/(m*K)` threshold.
- Main ROI was continued for another 2000 Adam steps from the 2000-step checkpoint:
  - output: `outputs\models\20260608_h59_100c_155612_x12_76_y28_32_start0_continue4000\`
  - `k = 79.9982 W/(m*K)`, `alpha_tail_rel_range = 0.0121`, `h_tail_rel_range = 0.0347`
  - parameters are now stable; the only remaining warning is the strict H59 lower-bound check, because `79.9982` is just below `80.0`.
  - Next best check is one seed repeat or the already-prepared `start250` dataset, not simply more epochs.

## 2026-06-08 6061@100 C 16:21 batch

- Formal ROI after user correction:
  `x=12~70, y=28~32`, because `x>70` has support interference.
- Full-data formal run on this ROI was rejected:
  - `k = 393.51 W/(m*K)`
  - alpha tail unstable and outside 6061 expected range.
- A separate mini-batch script was added:
  - `code\train_pinn_1d_minibatch.py`
  - keeps the same PDE/model/boundaries/output layout as `train_pinn_1d.py`
  - adds `--data-batch-size`, default `16384`, `0` means full data.
- Mini-batch run on the same ROI was also rejected:
  - output: `outputs\models\20260608_6061_100c_162125_x12_70_y28_32_start0_minibatch16384\`
  - `k = 389.77 W/(m*K)`, `MSE = 0.2637`
  - alpha still climbs upward, so mini-batch data loss did not solve this batch.
- Next diagnostics should focus on model/constraint/ROI-boundary issues, not only optimizer batch size:
  1. compare right boundary mode `none` vs `robin`
  2. inspect whether left boundary after cropping to `x=12` is still too hot/transition-like
  3. consider a constrained/regularized alpha search or a non-PINN forward fit to check identifiability

## 2026-06-16 更新

1. 新到 H59/6061 `.dat` 必须先核实 `fps`、`mm_per_px` 和杆体 ROI，再运行 `extract_rod_profile.py`。
2. 正式热导率入口改用 `code/estimate_conductivity_from_experiment.py`。
3. 先看输出 `recommended_for_reporting`；若为 `false`，直接拒绝该录像，不从候选或 PINN 中挑接近参考值的结果。
4. H59 若出现 `physical_window_candidates_not_stable`，结果只能带警告报告，并优先补无支架污染的复现实验。
5. 6061 2026-06-08 16:21 已确认不可用，不再继续调 PINN epoch、loss weight 或 mini-batch。
6. 若继续改进 PINN，应使用与确定性估计器一致的加热端子域、双实测边界和固定 `h`，并以确定性结果作为盲测对照。
