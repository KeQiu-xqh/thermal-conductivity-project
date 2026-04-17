# Session Handoff

更新：2026-04-17

## 下一轮对话先看

1. [`docs/agent_memory/current-state.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/current-state.md)
2. [`docs/agent_memory/decisions.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/decisions.md)
3. [`docs/agent_memory/next-actions.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/next-actions.md)
4. 如遇问题，再看 [`docs/agent_memory/bugs-and-fixes.md`](/C:/Users/28146/Desktop/thermal-conductivity-project/docs/agent_memory/bugs-and-fixes.md)

## 当前最重要事实

- 官方 `stream_spi.py` 与 [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py) 都已跑通
- VNC 下实时热像显示正常
- 原始数据、GIF 回看、静态图、ROI 训练数据都已生成成功
- 当前问题不再是“能不能采到”，而是“如何固定正式 ROI 并整理数据格式”

## 立即避免的误区

- 不要把当前候选 ROI 直接当成最终金属丝物理 ROI
- 不要再把原始热像数据和结果图堆在仓库根目录
- 不要把讲义附录代码继续当作主运行入口
