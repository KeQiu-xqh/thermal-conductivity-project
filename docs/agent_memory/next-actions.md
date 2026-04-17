# Next Actions

更新时间：2026-04-10

## 当前短期动作

1. 后续本项目任务优先使用 `thermal-conductivity-lab` 作为入口 skill。
2. 每次更新项目文件后，验证并自动 commit + push 到 GitHub。
3. 下一轮若处理采集脚本，先核查 `camera_id_hexsn`、GUI 判断和尾部 GPIO 变量名。
4. 下一轮电脑端分析脚本优先加入时间轴、center/hot ROI 同图比较和 CSV 输出。
5. 正式实验采购优先围绕智能加热台、金属圆杆/粗金属丝、黑色高发射率材料、热电偶和固定支架。

## 本轮不做

- 不重写 `stream_spi.py`，除非下一步明确要处理采集脚本。
- 不修改 `code_appendix/thermal90_ir_temp.py`，除非下一步明确要修复附录代码。
- 不进入 PINN 训练代码。
- 不把明文密码写入项目文件。
## 追加动作
- 先在树莓派上跑一次 `code_appendix/thermal90_ir_temp.py` 的实时显示模式，确认热像窗口、帧率和样品入镜情况。
- 如果实时图稳定，再决定是否开启 `-r` 录制并保存首组 `.dat`。
- 下一轮若继续处理分析脚本，再补时间轴、固定 ROI 和 CSV 输出。
