# Current State

更新：2026-04-17

## 当前主线

项目当前已经进入：

**真实实验数据闭环已建立，开始收敛正式样品 ROI 和训练数据格式。**

## 已确认可用

- 官方 `stream_spi.py` 可运行
- [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py) 可运行
- VNC 下实时热像显示正常
- 原始热像数据已成功采集并回传到 Windows
- [`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py) 可从原始数据生成：
  - GIF 回看
  - 多帧对比图
  - 中心点/中心 ROI 曲线
  - 热区 ROI 曲线
- [`code/construct_training_data.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/construct_training_data.py) 可从固定矩形 ROI 构建 `npz/csv/meta.json`

## 当前数据状态

- 当前原始数据样本：`data/raw/thermal90-20260417-run01.dat`
- 当前可回看预览：`outputs/preview/thermal90-20260417-run01_preview.gif`
- 当前训练数据：`data/derived/thermal90-20260417-run01_train_data.*`
- 当前构造的 ROI 是疑似金属丝候选区域，不是最终物理定义 ROI

## 当前判断

- 采集链路已经不是主要风险
- 目前更重要的是：
  - 固定金属丝所在 ROI
  - 统一数据命名
  - 将 `x, y, t -> T` 数据进一步压缩或变换为更适合 1D 导热反演的形式

## 最新分析

- `data/raw/thermal90-20260424-run02.dat` 对应的恒温加热台附件金属丝数据中，出现了一条从左上向右下延伸的稳定高温斜带
- 依据该斜带构造的候选 wire ROI，平均温度约在 `79°C` 左右，时间波动很小
- 这说明当前实验已经具备做“红外摄温稳定性/准确性验证”的条件，但还不足以直接得出最终热导率
