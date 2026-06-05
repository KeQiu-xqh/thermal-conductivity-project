# Session Handoff

更新：2026-06-04

## 下次对话先看

1. [current-state.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/current-state.md)
2. [next-actions.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/next-actions.md)
3. [05-数据记录日志.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/05-%E6%95%B0%E6%8D%AE%E8%AE%B0%E5%BD%95%E6%97%A5%E5%BF%97.md)
4. [07-实验复现操作手册.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/07-%E5%AE%9E%E9%AA%8C%E5%A4%8D%E7%8E%B0%E6%93%8D%E4%BD%9C%E6%89%8B%E5%86%8C.md)

## 当前主结果

- `6061` 铝棒正式主结果仍以两次黑体化实验为准：
  - `2026-05-22 run02`：`k = 169.82 W/(m*K)`
  - `2026-05-28 run01`：`k = 159.84 W/(m*K)`

## 304：两次都仍是诊断级

- `2026-05-28 run02@100 C`：`k = 47.53 W/(m*K)`
- `2026-06-04 run01@140 C`：`k = 49.29 W/(m*K)`
- 当前判断：
  - 提高热台温度没有从根本上解决 `304` 的边界失真问题

## H59：当前主判断约 100 W/(m*K)

- `2026-05-28 run03@100 C`：`k = 84.36 W/(m*K)`
- `2026-06-04 run02@140 C` 原始全长 ROI：`k = 100.88 W/(m*K)`
- 发现右端 `x>70` 混入铁架台旋钮后，裁成 `x=0~68`：
  - 修正结果：`k = 100.75 W/(m*K)`
- 当前判断：
  - `H59` 在现有装置下已经基本收敛到约 `100 W/(m*K)` 的量级

## 6061@140 C：当前不宜替代旧主结果

- `2026-06-04 run03@140 C` 原始全长 ROI：`k = 92.27 W/(m*K)`
- 发现右端 `x>70` 混入铁架台旋钮后，裁成 `x=0~68`：
  - 修正结果：`k = 96.40 W/(m*K)`
- 当前判断：
  - 这组 `6061@140 C` 受远距离完整入镜和右端异物污染影响明显
  - 即使修正后，仍明显低于此前 `6061@100 C` 的 `160~170 W/(m*K)`，不宜拿来替代旧主结果

## 下次最值得做的事

1. 不再优先追加 `304`
2. 若继续测量，优先补一组 `H59@140 C` 复现实验
3. 若继续做远距离完整入镜，先检查右端 `x>70` 是否混入铁架台旋钮，再定 `x_max`
## 2026-06-04 远距离批次补充说明

- 用户补充的几何信息：从棒身起始位置到右端旋钮处约 `120 mm`。
- 对裁掉右端旋钮后的远距离 `140 C` 批次，新增了一版综合标定：
  - 长度标定 `120/68 = 1.7647 mm/px`
  - 直径标定 `8/4 = 2.0 mm/px`
  - 综合标定 `mm_per_px = 1.88235`
- 该标定下：
  - `H59@140 C`：`k = 89.40 W/(m*K)`
  - `6061@140 C`：`k = 88.62 W/(m*K)`
- 说明这批远距离数据对 `mm_per_px` 很敏感，不能再把 `2.0 mm/px` 当作稳定标定。
## 2026-06-04 run04 补充

- 新增 `6061@140 C` 更近距离数据：
  - `thermal90-20260604-run04.dat`
  - 手动 ROI：`x=0~68, y=30~34`
  - `T_inf = 23 C`
  - `k = 113.25 W/(m*K)`
- 该结果明显高于上一组远距离 `run03` 的 `96.40`，说明相机距离和右端异物确实会压低 `6061@140 C` 的结果。
- 但它仍低于 `6061@100 C` 的两组主结果 `159.84~169.82`，所以当前还不能用 `140 C` 批次替代原主结果。

## 2026-06-05 H59@100 C 支架标定批次

- 数据：`data/raw/2000.0.0.000000--20260605-160328.dat`
- 热台：`100 C`
- 视频时间：`16:03:28` 到 `16:12:20`
- 总帧数：`3205`，按首尾时间换算 `fps = 6.02256`
- 用户新增第二金属支架，距初始加热端支架约 `99 mm`。
- 视频显示第一支架右端 `x=4`、第二支架左端 `x=250`；结合诊断图中第二支架在原始热像 `x≈62`，按约 `4x` 显示缩放标定：
  - `mm_per_px = 1.60976`
- 主 ROI：`x=12~56, y=30~34`
- 反演结果：
  - `x=8~56`: `k = 73.60 W/(m*K)`
  - `x=10~56`: `k = 66.54 W/(m*K)`
  - `x=12~56`: `k = 60.09 W/(m*K)`
  - `x=12~58`: `k = 58.10 W/(m*K)`
- 上面 500 epoch 结果后续确认未充分收敛，只能作为快速诊断。
- 2000 epoch 长训练结果：
  - `x=12~56`: `k = 95.55 W/(m*K)`, `MSE = 0.097 C^2`
  - `x=12~58`: `k = 90.34 W/(m*K)`, `MSE = 0.098 C^2`
- 当前判断：
  - 主判断应采用 2000 epoch 结果，约 `90~96 W/(m*K)`。
  - 该批次与此前 `H59 ~90~100 W/(m*K)` 基本一致，但仍更适合作为长度标定和支架二维影响诊断数据。

## 2026-06-05 PINN 训练代码状态

- `code/train_pinn_1d.py` 已支持训练控制优化：
  - `--lr-scheduler plateau`
  - `--resume-checkpoint`
  - `--lbfgs-steps`
  - `--early-stop-window`
- history 现在记录 `step/stage/lr`，loss 图横轴改为 `Optimizer Step`。
- summary 现在记录 `completed_steps`、`stage_counts`、optimizer 配置和 `resume_checkpoint`。
- 可以直接从已有 2000-step checkpoint 做第二阶段 LBFGS：
  `python code\train_pinn_1d.py data\derived\20260605_h59_100c_160328_x12_56_calib99mm\2000.0.0.000000--20260605-160328_rod_xt_data.npz --epochs 0 --resume-checkpoint outputs\models\20260605_h59_100c_160328_x12_56_calib99mm_e2000_pinn.pt --lbfgs-steps 300 --lbfgs-lr 0.5 --rho 8500 --cp 380 --diameter-mm 8 --t-inf-c 24.5 --output-stem 20260605_h59_100c_160328_x12_56_lbfgs_from_e2000`
