# Current State

更新时间：2026-04-10

## 项目阶段

当前项目已经不是树莓派入门或设备联通阶段，而是进入：

**实验复现准备 + 热像数据预处理 + 后续 PINN 数据准备阶段。**

## 已经确认跑通

- Windows 电脑可以通过 SSH 连接树莓派。
- 树莓派用户名为 `piqio`。
- 树莓派连接凭据由用户授权 Codex 在会话中使用；默认不写入仓库明文文件。
- Thermal-90 Camera HAT 已正确插到树莓派 40 针 GPIO。
- `/boot/firmware/config.txt` 已做过关键配置：
  - `dtparam=i2c_arm=on`
  - `dtoverlay=spi0-0cs`
- 重启后已经确认：
  - `/dev/i2c-1` 存在。
  - `sudo i2cdetect -y 1` 能看到地址 `0x40`。
- `stream_spi.py` 已经能初始化相机并连续采集。
- `sudo python3 stream_spi.py -r` 已经能录制 `.dat` 文件。
- Windows 本地已经能读取 `.dat`，重建为 `(帧数, 62, 80)` 的温度矩阵。
- 已经能保存热图、中心 ROI 曲线、热区 ROI 曲线。
- VNC Viewer 已经能看到树莓派桌面。
- VNC 下 Thermal-90 实时热像窗口已经弹出成功。

## 当前最有价值的数据

第二组较长数据是目前最重要的数据：

- 原始数组形状：`(118, 4960)`
- 重塑后形状：`(118, 62, 80)`
- 总帧数：`118`
- 第一帧最高温位置：`(52, 73)`，温度 `39.34`
- 最后一帧最高温位置：`(61, 72)`，温度 `36.16`
- 热区 ROI 变化幅度约 `5.72°C`
- 整体更像一个热目标冷却过程。

## 当前主线

- 正式热源路线优先考虑智能加热台。
- PTC + MOS DIY 热源保留为备选，不作为当前主线。
- 主样品路线已纠正为金属丝/金属圆杆；金属条只作为热像调试和备选样品。
- 先保住采集和 VNC 可视化链路，再规范数据分析和实验搭建。

## 文件与代码权限

- PDF 附录中的 `Thermal-90 热像仪红外成温.py` 已由用户命名为 `code_appendix/thermal90_ir_temp.py`。
- `code/` 和 `code_appendix/` 都允许 Codex 在需要时修改。
- 修改原则：先查 skill 和历史记录，再做小范围改动；采集链路相关代码改动前要明确风险，改后要验证。

## Codex 项目专属 Skill

- 已创建用户级自动发现 skill：`thermal-conductivity-lab`。
- skill 路径：`C:\Users\28146\.codex\skills\thermal-conductivity-lab`。
- 用途：处理本项目相关任务时，先读项目记忆，再选择调试、TDD、文件处理、GitHub 或实验搭建等支持 skill。
- 验证：`quick_validate.py` 已通过，输出 `Skill is valid!`。

## 当前风险

- 讲义中的 PTC DIY 路线与智能加热台路线存在混写，不能机械照抄。
- 当前 `.dat` 分析脚本还偏测试性质，后续需要加入时间轴、固定 ROI、CSV 导出。
- 正式实验还缺稳定热源、金属圆杆/金属丝样品、夹具、黑色高发射率材料、热电偶和固定支架。
- 样品位置、相机距离和 ROI 还没有固定，暂时不适合直接进入 PINN。
## 追加状态
- `code_appendix/thermal90_ir_temp.py` 已完成第一次试拍前的最小稳定化修补：录制文件名改为使用 `camera_id_hexsn`，尾部资源关闭对象已对齐为当前脚本里的实际变量名。
- 已完成语法级验证，脚本当前可继续进入实时热像试拍验证。
- 首次试拍时发现程序可能卡在 `DATA_READY` 外部脚等待上，因此当前脚本已切换为轮询 `STATUS.DATA_READY` 的更稳路径。
