# 实验日志

## 当前定位

本项目已经完成从设备连接到数据回看的基础闭环，当前不再处于“环境能否跑通”的阶段，而是进入“固定正式样品 ROI、统一数据格式并为后续反演做准备”的阶段。

## 已完成的任务

### 1. 树莓派与 Thermal-90 基础链路已建立

- 已完成 Raspberry Pi 5 与 Thermal-90 Camera HAT 的接入和基础配置
- 已确认 `i2c_arm`、SPI 等关键链路可用
- 已能通过电脑远程连接树莓派并进行实验操作

### 2. 热像采集链路已跑通

- 官方 `stream_spi.py` 已验证可运行
- [`code/thermal90_ir_temp.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/thermal90_ir_temp.py) 已验证可运行
- 已确认可以持续读取热像帧，而不仅是单次初始化成功

### 3. VNC 实时可视化链路已确认可用

- 已确认在 VNC 桌面环境下可以正常显示实时热像
- 已明确 SSH 终端不适合直接运行需要图形界面的 OpenCV 显示流程
- 已形成“SSH 负责登录和检查，VNC 负责实时显示”的操作分工

### 4. 原始热像数据采集与回传已完成

- 已成功录制真实热像原始数据 `.dat`
- 已成功将原始数据从树莓派回传到 Windows 本地
- 已确认原始数据不是普通视频文件，而是逐帧温度矩阵数据

### 5. 本地数据回看与基础分析已完成

- [`code/view_dat.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/view_dat.py) 已可从原始 `.dat` 数据生成回看与分析结果
- 已可生成 GIF 回看
- 已可生成多帧热图对比图
- 已可生成中心点温度曲线
- 已可生成中心 ROI 温度曲线
- 已可生成热区 ROI 温度曲线

### 6. ROI 训练数据构建流程已完成

- [`code/construct_training_data.py`](/C:/Users/28146/Desktop/thermal-conductivity-project/code/construct_training_data.py) 已可从固定矩形 ROI 构建训练数据
- 已可输出 `npz`
- 已可输出 `csv`
- 已可输出 `meta.json`
- 已完成从原始热像到训练数据样本的基础转换链路

### 7. 项目协作文档和状态记录体系已建立

- 已建立 `docs/agent_memory/` 作为项目状态记录区
- 已整理当前状态、关键决策、问题修复和下一步动作
- 已形成较清晰的实验路线、数据路线和仓库整理规则

## 已确认的关键结果

### 可用能力

- 可连接树莓派并完成远程实验操作
- 可运行官方采集脚本
- 可运行项目内实时热像脚本
- 可在 VNC 下查看实时热像
- 可采集原始热像数据
- 可将原始数据回传到 Windows
- 可在本地生成 GIF 和静态分析图
- 可从固定 ROI 构建训练数据

### 已完成的数据产物

- 原始数据样本：`data/raw/thermal90-20260417-run01.dat`
- GIF 预览：`outputs/preview/thermal90-20260417-run01_preview.gif`
- 静态分析图：`outputs/figures/`
- ROI 训练数据：`data/derived/thermal90-20260417-run01_train_data.*`

## 当前结论

- 真实实验数据闭环已经建立：采集 -> 回传 -> 回看 -> 静态分析 -> 固定 ROI 训练数据构建
- 当前主要风险不再是“采不到数据”，而是“样品 ROI 是否固定、数据格式是否适合后续反演”
- 当前训练数据所用 ROI 仍是候选区域，还不是最终正式样品的物理 ROI

## 当前仍未完成的部分

- 固定正式金属丝 / 金属细杆样品的物理 ROI
- 统一后续实验原始数据命名规则
- 将当前 `x, y, t -> T` 数据进一步整理为更适合 1D 导热反演的形式
- 在样品位置、相机位置、加热过程固定后，再采集一组更标准的正式数据

