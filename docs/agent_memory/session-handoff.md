# Session Handoff

更新时间：2026-04-10

这个文件用于在新对话或上下文压缩后快速接上项目，不需要用户重复背景。

## 下个对话开始时先做

1. 使用项目 skill：`.codex/skills/thermal-conductivity-lab/SKILL.md`。
2. 读取：
   - `docs/agent_memory/current-state.md`
   - `docs/agent_memory/decisions.md`
   - `docs/agent_memory/next-actions.md`
   - 如遇 bug，再读 `docs/agent_memory/bugs-and-fixes.md`
3. 不从树莓派、SSH、GPIO 基础重新讲起。
4. 回答保持短步骤，优先推进真实实验复现。
5. 修改项目文件后自动验证、commit、push 到 GitHub；但不要把明显无关的用户改动混进提交。

## 当前必须记住的事实

- Thermal-90 + 树莓派 5 采集链路已打通。
- SSH、`.dat` 录制、本地解析、ROI 曲线、VNC 实时热像显示都已成功过。
- 树莓派用户名：`piqio`；连接凭据可在会话中使用，但不要写入仓库明文。
- `code_appendix/thermal90_ir_temp.py` 是 PDF 附录 Thermal-90 代码的当前文件名。
- `code/` 和 `code_appendix/` 都允许修改，但采集链路改动要小、可验证。
- 项目专属 skill 已创建并提交到仓库：`.codex/skills/thermal-conductivity-lab/`。

## 实验路线纠偏

- 正式主样品不是金属条。
- 主样品应为金属丝 / 金属圆杆，优先直径 `3-4 mm`、长度 `200-300 mm`。
- 金属条只作为热像调试、ROI 练习、备选样品。
- 这是用户明确纠正过的错误，后续不要再默认“金属条优先”。

## 当前采购方向

采购清单在 `docs/03-plan-private.md`。

当前清单已改成真正 Markdown 任务列表格式：

```md
- [ ] **器材名称**：规格
```

用户希望可以在 VS Code / GitHub 里勾选是否已买。

优先采购：

- DLAB HP550-S 数显加热台
- T2 紫铜圆棒 3 mm / 4 mm
- 6061 铝圆棒 3 mm / 4 mm
- 304 不锈钢圆棒 3 mm / 4 mm
- 3M Super 33+ 黑色电工胶带
- 黑色聚酰亚胺高温胶带
- UNI-T UT320D 双通道 K 型热电偶温度计
- K 型贴片热电偶
- 桌面俯拍支架 / 魔术臂
- 实验铁架台 + 万向夹
- 耐高温隔热垫

## 最近一次 VS Code 问题

用户发现：从资源管理器单独打开 `03-plan-private.md` 能看到新版本；但从整个项目打开 VS Code 看到旧版本。

判断：很可能是 VS Code Hot Exit / 未保存旧编辑器缓存。

建议：

- 不要直接保存旧窗口。
- 检查标签页是否有未保存圆点。
- 用 `File: Revert File` 或 `Developer: Reload Window` 刷新。

## 当前 Git 状态提醒

最近一次检查时，工作区出现用户自己的改动：

- `docs/04-questions.md` deleted
- `docs/05-questions.md` untracked

这不是 Codex 当前任务产生的，不要静默提交，除非用户明确要求。

## 下一步建议

如果用户继续采购：

1. 让用户发候选商品链接/截图。
2. 逐项判断：能买 / 不建议 / 规格不合适。
3. 如果用户确认已买，可以把 `docs/03-plan-private.md` 中对应 `- [ ]` 改成 `- [x]`。
4. 每次修改后自动 commit + push。

如果用户想推进代码：

1. 先处理 `code/view_dat.py`：
   - 时间轴
   - center/hot ROI 同图
   - CSV 输出
2. 不先进入 PINN。

## 最近推送

- `4bc0f68 改进采购清单复选框格式`
- `6bc5cbb 给采购清单添加勾选框`
- `6888120 更新采购路线和自动同步规则`
