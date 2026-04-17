# 实验日志

---
## 2026-03-27

### 内容
- 初步学习树莓派基础结构和系统烧录
- 尝试建立电脑与树莓派的基本连接链路

### 结果
- 建立了项目最初的硬件与系统认知
- 还处在环境搭建阶段

---
## 2026-04-03

### 内容
- 重新接入 Thermal-90 Camera HAT
- 打通 `i2c_arm`、`spi0-0cs` 和官方 `stream_spi.py`
- 首次录制 `.dat` 热像数据并拉回 Windows
- 编写本地读取脚本，对 `.dat` 生成热图和 ROI 曲线

### 结果
- Raspberry Pi 5 + Thermal-90 的采集链路首次跑通
- 成功录得真实热像数据
- 完成了最基础的本地可视化分析

### 结论
- 项目从“环境搭建”进入“真实热像数据预处理”

---
## 2026-04-10

### 内容
- 建立项目内 `docs/agent_memory/` 协作文档体系
- 纠正样品路线：主线应为金属丝 / 金属圆杆，不再默认金属条
- 明确采集、文档、Git 同步的协作规则

### 结果
- 项目记忆与协作规则初步稳定
- 主实验路线更清晰

---
## 2026-04-17

### 内容
- 排查 `stream_spi.py` 间歇性卡在第一帧前的问题
- 验证官方 `stream_spi.py` 和 [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py) 都能重新跑通
- 在 VNC 中确认 `thermal90_ir_temp.py` 的实时可视化正常
- 采集新的原始热像数据并在 Windows 本地回看
- 将原始热像数据转换为 GIF 预览、静态图和固定 ROI 训练数据

### 关键结果
- 官方 `stream_spi.py` 跑通
- [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py) 跑通
- VNC 可视化链路确认可用
- 当前原始数据已成功回放为 GIF
- 当前训练数据已从疑似金属丝 ROI 构建完成

### 数据产物
- 原始数据：`data/raw/thermal90-20260417-run01.dat`
- 回看预览：`outputs/preview/thermal90-20260417-run01_preview.gif`
- 静态分析图：`outputs/figures/`
- ROI 训练数据：`data/derived/thermal90-20260417-run01_train_data.*`

### 当天结论
- 真实实验数据闭环已经建立：采集 -> 回看 -> 静态分析 -> 固定 ROI 训练数据
- 当前 ROI 仍属于“候选 ROI”，尚未完全等同于正式金属丝物理 ROI
- 下一阶段重点不是继续排采集，而是固定样品 ROI 和训练数据格式
