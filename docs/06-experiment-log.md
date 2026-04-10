# 实验日志

---
## 2026-03-27
### 实验内容
- 学习树莓派主板的结构
- 烧入系统
- 将树莓派与电脑连在同一网络下

### 阶段结果
- 初步建立了对树莓派硬件与系统烧录流程的认识
- 开始尝试无显示器方案

---
## 2026-04-03
### 实验目标
- 重新接入 Thermal-90 Camera HAT
- 跑通树莓派与热像仪的通信
- 完成第一次真实热像数据采集
- 将热像数据拷贝到本地电脑并做初步可视化分析

### 实验过程

#### 1. 树莓派与电脑重新连接
- 通过手机热点让树莓派和电脑处于同一网络
- 通过 PowerShell 使用 SSH 远程连接树莓派
- 再次确认了基本连接流程：
  - 树莓派上电
  - 等待 2～3 分钟
  - 查看热点分配的 IP
  - `ssh 用户名@IP`

#### 2. 连接 Thermal-90 硬件
- 将 Thermal-90 插到树莓派 40 针 GPIO 上
- 明确了 Thermal-90 不是 USB 摄像头，而是 HAT 扩展板
- 热像仪通过 GPIO + I2C + SPI 与树莓派通信

#### 3. 安装基础依赖并检查接口
在树莓派上安装了基础软件依赖：

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git i2c-tools python3-smbus python3-opencv python3-gpiozero python3-spidev
```

检查设备节点：

```bash
ls /dev/i2c*
ls /dev/spidev*
```

最初看到：

- `/dev/i2c-13`
- `/dev/i2c-14`
- `/dev/spidev10.0`

这说明底层总线节点已经存在，但还不能直接说明 demo 可用。

#### 4. 发现关键问题：`i2c_arm` 没打开
运行官方 demo 后，出现 `FileNotFoundError`，定位到：

- demo 默认使用 `RPI_GPIO_I2C_CHANNEL = 1`
- 但系统中当时没有 `/dev/i2c-1`

因此修改了 `/boot/firmware/config.txt`：

```txt
dtparam=spi=on
dtparam=i2c_arm=on
dtoverlay=spi0-0cs
```

然后重启树莓派。

#### 5. 成功识别 Thermal-90
重启后检查：

```bash
ls /dev/i2c*
i2cdetect -l
sudo i2cdetect -y 1
```

确认结果：
- 出现了 `/dev/i2c-1`
- 在 `i2c-1` 上成功扫描到地址 `0x40`

这说明：
- Thermal-90 已经在正确总线上被树莓派识别
- 官方 demo 需要的 I2C 通道就是 `1`

#### 6. 运行官方 demo 并解决无显示器 GUI 报错
运行：

```bash
cd ~/thermal90/pysenxor-master/example
sudo python3 stream_spi.py
```

程序成功输出了相机信息和连续帧温度统计，但随后因为 OpenCV 尝试弹窗，在 SSH 环境下报错：

- `could not connect to display`
- `Could not load the Qt platform plugin "xcb"`

解决办法：
- 将 `stream_spi.py` 中的 GUI 显示逻辑关闭
- 把 `if GUI:` 改为 `if False:`

修改后重新运行，程序可以持续输出每一帧的统计信息，例如：

- `FID`
- `time`
- `V_dd`
- `T_SX`
- `Min`
- `Max`
- `Avg`
- `Std`

这说明 Thermal-90 已经真正跑通。

#### 7. 尝试录制数据并修复 `--record` 模式
运行：

```bash
sudo python3 stream_spi.py -r
```

第一次失败，报错为：

```text
AttributeError: 'MI48' object has no attribute 'camera_id_hex'. Did you mean: 'camera_id_hexsn'?
```

修复方法：
- 将 `stream_spi.py` 中：

```python
filename = get_filename(mi48.camera_id_hex)
```

改为：

```python
filename = get_filename(mi48.camera_id_hexsn)
```

再次运行后，录制模式成功工作，程序将温度帧保存为 `.dat` 文件。

#### 8. 生成了第一份真实热像数据文件
成功录制后，在目录中看到了数据文件，例如：

- `2000.0.0.000000--20260403-161239.dat`

说明：
- 热像数据已经不仅能实时读取
- 而且已经可以落盘保存

#### 9. 将 `.dat` 文件拷贝到本地电脑
先从 SSH 退出，再在本地 PowerShell 中执行 `scp`，把 `.dat` 文件下载到电脑桌面。

过程中还确认了一点：
- `scp` 应该在本地 PowerShell 里执行
- 不能在树莓派 SSH 终端里直接使用 Windows 桌面路径

#### 10. 在本地电脑读取 `.dat` 并做第一次可视化
在本地电脑编写了 `view_dat.py` 脚本，用于：

- 读取 `.dat` 文件
- 将每帧数据重塑为 `62 × 80`
- 生成热图和温度曲线

第一次成功解析后得到：

- 原始数组形状：`(26, 4960)`
- 重塑后形状：`(26, 62, 80)`

随后解决了 `matplotlib` 弹窗被中断的问题：
- 不再使用 `plt.show()`
- 改为直接 `plt.savefig(...)`

从而成功保存：
- `first_frame.png`
- `frames_compare.png`
- `center_temp_curve.png`
- `center_roi_curve.png`
- `hot_roi_curve.png`

#### 11. 第一组与第二组数据的分析结果
第一组数据：
- 帧数较少（26 帧）
- 最热点位置不稳定
- 中心区域变化较小
- 更适合作为系统联通测试

第二组数据：
- 总帧数 118 帧
- 最热点位置更稳定
- 热区 ROI 温度变化明显
- 更像一个真实的冷却过程数据集

分析结果显示：
- 中心 `5×5` ROI 变化幅度较小
- 热区 ROI 变化幅度明显更大
- 热区曲线呈现“先明显下降，后趋于平缓”的趋势

这说明：
- 设备链路已经跑通
- 本地分析脚本已经能正常提取 ROI 温度曲线
- 当前已经从“设备配置阶段”进入“热像数据预处理阶段”

### 当天收获
- 学会了树莓派与 Thermal-90 的真实连接链路
- 明确了 `i2c_arm=on` 是关键配置
- 理解了官方 demo 依赖的 I2C 通道与 I2C 地址关系
- 学会了在 SSH 无显示器环境下关闭 OpenCV GUI
- 学会了用 `-r` 录制 `.dat` 文件
- 学会了把 `.dat` 文件拷到本地电脑
- 学会了在电脑上重建热图和提取 ROI 曲线
- 初步理解了“中心 ROI”和“热区 ROI”的区别

### 当前结论
截至 2026-04-03，已经完成：

**树莓派 5 + Thermal-90 的配置、连通、采集、录制、本地可视化分析。**

当前阶段已经不是单纯的环境搭建，而是进入：

**热像数据采集与预处理阶段。**

### 下一步计划
- 将横轴从帧号改为时间（秒）
- 同时比较中心 ROI 与热区 ROI 曲线
- 固定热目标位置与视场位置
- 采集更规范的加热/冷却过程数据
- 逐步整理成适合后续 PINN 训练的数据格式

---
## 2026-04-10

### 实验协作机制更新

本次没有修改树莓派采集代码，也没有重写电脑端分析脚本。

本次重点是建立 Codex 后续接手项目时使用的协作记忆机制，避免每次都重新解释背景。

新增计划：
- 使用 `docs/agent_memory/` 记录 Codex 的长期项目记忆。
- 阶段性进展完成后，同步更新实验日志和项目笔记。
- 遇到 bug、采集异常或环境问题时，优先查找已有 skill 和历史记录，不直接从零造轮子。
- 不在项目文件中记录树莓派密码、VNC 密码、热点密码等敏感信息。

### 当前状态总结

- Thermal-90 采集链路已经跑通。
- `.dat` 录制与本地读取分析已经跑通。
- VNC 远程桌面和实时热像窗口已经跑通。
- 当前主线倾向使用智能加热台完成正式实验复现。
- PTC + MOS DIY 热源路线暂时作为备选。

### 下一步建议

- 先核查 `code_appendix/thermal90_ir_temp.py` 与 IDE 中显示的中文文件名是否指向同一个真实文件。
- 保持树莓派采集和 VNC 链路稳定，不急于重写采集程序。
- 下一步优先规范电脑端分析脚本：时间轴、双 ROI 对比、CSV 输出。

### 风险点

- 讲义中的热源路线存在混写，后续不能机械照抄。
- 当前附录代码中仍可能存在旧字段名和变量名不一致问题，正式运行前需要核查。
- 正式实验的热源、样品固定、相机固定和高发射率表面处理还没有完成。

### 补充更正

- IDE 中的 `Thermal-90 热像仪红外成温.py` 已确认是用户命名为 `code_appendix/thermal90_ir_temp.py` 的附录代码文件。
- 用户允许 Codex 在需要时修改 `code/` 和 `code_appendix/`。
- 树莓派连接凭据允许 Codex 在会话中使用；项目文件中默认不保存明文密码。

### Codex 项目专属 Skill

本次创建了用户级自动发现 skill：

- skill 名称：`thermal-conductivity-lab`
- skill 路径：`C:\Users\28146\.codex\skills\thermal-conductivity-lab`
- 作用：作为本项目入口流程，要求先读 `docs/agent_memory/`，再选择调试、TDD、文件处理、实验搭建、日志更新或子 agent 分配策略。

验证结果：
- 使用子 agent 做了采集报错、实验搭建、`view_dat.py` 改造三个只读场景验证。
- 官方 `quick_validate.py` 验证通过，输出 `Skill is valid!`。
- skill 文件中未写入明文密码。

### 当前状态总结

- 项目已经有专属 Codex skill，可用于后续自动接管项目上下文。
- `docs/agent_memory/` 继续作为真实项目记忆源。
- 后续遇到本项目相关任务时，应优先使用 `thermal-conductivity-lab`。

### 下一步建议

- 下一轮继续推进电脑端分析脚本标准化：时间轴、双 ROI 对比、CSV 输出。
- 如果先处理采集脚本，则优先核查 `camera_id_hexsn`、GUI 判断和 GPIO 清理变量名。

### 风险点

- skill 能规范流程，但不能替代真实验证；涉及树莓派和 Thermal-90 的改动仍要用实际命令或 VNC 结果确认。
- skill 存在于用户级 `.codex` 目录，不在当前 git 仓库内；如果换机器，需要重新复制或安装。
