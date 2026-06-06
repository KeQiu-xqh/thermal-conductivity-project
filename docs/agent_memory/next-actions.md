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
12. 后续正式 PINN 反演不要再只跑短 Adam 轮数。推荐先用 Adam 长训练并记录 scheduler，再接 LBFGS 微调：
   - Adam + scheduler + LBFGS：
     `python code\train_pinn_1d.py data\derived\20260605_h59_100c_160328_x12_56_calib99mm\2000.0.0.000000--20260605-160328_rod_xt_data.npz --epochs 2000 --lr-scheduler plateau --lr-patience 200 --lr-factor 0.5 --min-lr 1e-5 --lbfgs-steps 300 --lbfgs-lr 0.5 --rho 8500 --cp 380 --diameter-mm 8 --t-inf-c 24.5 --output-stem 20260605_h59_100c_160328_x12_56_optimized`
   - 从已有 2000-step checkpoint 只做第二阶段：
     `python code\train_pinn_1d.py data\derived\20260605_h59_100c_160328_x12_56_calib99mm\2000.0.0.000000--20260605-160328_rod_xt_data.npz --epochs 0 --resume-checkpoint outputs\models\20260605_h59_100c_160328_x12_56_calib99mm_e2000_pinn.pt --lbfgs-steps 300 --lbfgs-lr 0.5 --rho 8500 --cp 380 --diameter-mm 8 --t-inf-c 24.5 --output-stem 20260605_h59_100c_160328_x12_56_lbfgs_from_e2000`
   - 判断是否收敛时优先看 `_history.json` 的 `stage/lr/loss/alpha_m2_s/h_w_m2k`，不要只看最终热导率。
13. 下一步正式评估 PINN 优化版时，优先在同一 ROI 上做旧/新训练对照：
   - 旧基线：保留默认 `--data-batch-size 0 --pde-sampling uniform --data-weighting none`
   - 新方案：加入 `--data-batch-size 16384 --pde-sampling mixed --data-weighting delta-initial`
   - 两边都记录 `alpha/h/k`、`full_temperature_mse_c2`、`final_unweighted_data_loss` 和 `_history.json` 中参数收敛情况。
   - 不要只用短 smoke 的 `k` 判断优化效果；短 smoke 只用于确认代码路径和 summary 字段。
