# Session Handoff

更新：2026-05-22

## 下次对话先看

1. [current-state.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/current-state.md)
2. [next-actions.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/next-actions.md)
3. [05-数据记录日志.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/05-%E6%95%B0%E6%8D%AE%E8%AE%B0%E5%BD%95%E6%97%A5%E5%BF%97.md)
4. [06-实验进度.md](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/06-%E5%AE%9E%E9%AA%8C%E8%BF%9B%E5%BA%A6.md)

## 今天的截止状态

- 当前正式原始数据是 `data/raw/thermal90-20260522-run02.dat`
- 当前正式 ROI 已固定为 `x=10~80, y=30~34`
- 当前正式时间轴已固定为 `7 fps`，并从冷态 `frame 0` 开始
- 当前正式物理模型是带对流与辐射项的一维非稳态导热方程
- 当前正式边界处理是：
  - 左边界：支座外第一列棒身像素温度曲线
  - 右边界：`none`
  - 初始条件：前 `5` 帧实测平均温度分布
- 当前最可信回测结果是：
  - `alpha = 6.99e-5 m^2/s`
  - `h = 11.07 W/m^2/K`
  - `k = 169.82 W/(m*K)`
  - `temperature MSE = 0.371 C^2`

## 下次继续时不要回退

- 不要再用旧 ROI `x=8~80`
- 不要再把可见右边界当成物理自由端
- 不要再把初始条件硬设成全场 `25 C`
- 不要再把 `run01` 裸铝数据当正式 PINN 数据

## 下次最值得做的事

1. 复现一组同装配、同黑体化条件的数据
2. 用同样流程验证 `k` 是否稳定落在同一量级
3. 若要进一步提高可信度，补外部长度标尺标定
