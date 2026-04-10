# Bugs And Fixes

更新时间：2026-04-10

## 1. SSH 无显示器环境下 OpenCV GUI 报错

- 现象：通过 SSH 运行 `stream_spi.py` 时，OpenCV 尝试弹窗，出现 GUI / Qt / display 相关错误。
- 原因：普通 SSH 终端没有图形显示环境。
- 修复：在无显示器采集模式下关闭 GUI 显示逻辑，只保留采集和输出。
- 验证：关闭 GUI 后，相机可以连续输出每帧温度统计。

## 2. `--record` 模式中相机 ID 字段不兼容

- 现象：运行 `sudo python3 stream_spi.py -r` 时出现：
  - `AttributeError: 'MI48' object has no attribute 'camera_id_hex'`
- 原因：当前安装的库中字段名不是 `camera_id_hex`。
- 修复：将 `mi48.camera_id_hex` 改为 `mi48.camera_id_hexsn`。
- 验证：修改后已经成功录制 `.dat` 文件。

## 3. VNC 能显示桌面但热像窗口不弹出

- 现象：VNC Viewer 已经能看到树莓派桌面，但运行 GUI 版本脚本时没有热像窗口。
- 原因：文件中显示逻辑被写成了 `if False:`，即使 `GUI = True` 也不会执行显示。
- 修复：将 while 循环中的显示判断恢复为 `if GUI:`。
- 验证：恢复后，电脑端通过 VNC 成功看到 Thermal-90 实时热像视频窗口。

## 4. `code_appendix/thermal90_ir_temp.py` 仍有待核查风险

- 现象：当前文件中仍可见 `mi48.camera_id_hex`。
- 风险：如果直接在当前库环境运行录制模式，可能再次触发相机 ID 字段不兼容。
- 现象：文件尾部出现 `reset_pin.close()` / `dr_pin.close()`。
- 风险：当前脚本前文使用的是 `mi48_reset_n` / `mi48_data_ready`，尾部变量名可能不一致。
- 当前处理：先记录为待核查，不在本轮修改附录代码。

## 5. IDE 中文文件名与磁盘文件名已确认

- 现象：IDE 标签页显示 `Thermal-90 热像仪红外成温.py`，当前文件系统列表中 `code_appendix` 看到的是 `thermal90_ir_temp.py`。
- 原因：用户已将中文文件名命名为 `thermal90_ir_temp.py`。
- 当前处理：不再按“文件丢失”处理；后续以 `code_appendix/thermal90_ir_temp.py` 为准。

## 6. 实验样品路线纠偏：不能默认把金属条当主样品

- 现象：Codex 曾把“金属条”作为正式实验主样品推荐。
- 用户纠正：实验目标是一维金属丝导热系数测量，主样品应优先考虑金属丝/金属圆杆。
- 原因：Codex 过度偏向 Thermal-90 成像便利性，忽略了实验对象“一维金属丝”的约束。
- 修正：主线改为直径 `3-4 mm`、长度 `200-300 mm` 的金属圆杆/粗金属丝；金属条只作为调试和备选。
- 防复发：后续采购、实验布局和 PINN 反演说明中，不再默认使用金属条作为主样品。
