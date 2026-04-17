# Bugs And Fixes

更新：2026-04-17

## 1. SSH 环境下 OpenCV GUI 无法显示

- 现象：在普通 SSH 终端运行热像脚本时，OpenCV / Qt 报 `could not connect to display`
- 结论：这不是采集失败，而是显示环境缺失
- 处理：需要在 VNC 桌面终端运行，或者显式配置 `DISPLAY` / `XAUTHORITY`

## 2. `stream_spi.py` 间歇性卡在第一帧前

- 现象：程序打印 `Entering continuous capture mode.` 后没有继续输出帧统计
- 特征：失败时常伴随 `FRAME_MODE: 0x0`、`STATUS: 0x4`、`Mode : 0x0`、`CAMERA_TYPE: 0`
- 结论：更像间歇性初始化 / 状态机异常，不是固定配置错误
- 补充：同样命令后续又能成功运行，证明问题具有间歇性

## 3. Windows 不能“直接看录像”

- 现象：采集回来的原始文件不能像普通视频那样直接双击播放
- 原因：原始热像记录保存的是逐帧温度矩阵，不是 `mp4/avi`
- 结论：这不是数据无效，而是数据格式本来就不是标准视频
- 处理：通过 [`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py) 生成 GIF 回看层
- 当前结果：已能输出 `outputs/preview/<stem>_preview.gif`

## 4. 当前 ROI 还不是最终样品 ROI

- 现象：当前训练数据已从固定矩形 ROI 构建，但该 ROI 仍是“疑似金属丝候选区域”
- 风险：如果直接把当前 ROI 当成正式样品区域，后续反演可能混入背景或偏离真实样品位置
- 处理：下一步先固定样品物理 ROI，再进入正式建模
