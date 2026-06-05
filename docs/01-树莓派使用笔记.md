# 02-树莓派基础操作

> 适用场景：树莓派 5 + Thermal-90 Camera HAT，无显示器，通过电脑 SSH 远程操作。  
> 本笔记重点关注：  
> 1. 树莓派与电脑的正确连接方式  
> 2. Thermal-90 的正确配置顺序  
> 3. `i2c_arm` 必须开启这一关键步骤  
> 4. 无显示器 SSH 环境下 OpenCV 弹窗导致程序中断的问题

---

## 一、树莓派和电脑怎么连接

### 1. 插卡、上电、联网
- 确保 microSD 卡已经插入树莓派
- 给树莓派插上电源
- 开手机热点（推荐）
- 让电脑连接到同一个热点
- 在手机热点设备列表中查看树莓派的 IP 地址

> 推荐使用手机热点，而不是校园网。  
> 原因：手机热点方便查看已连接设备和 IP，排错更直接。

### 2. 打开 PowerShell 连接树莓派
```bash
ssh piqio@树莓派的IP地址
```

例如：
```bash
ssh piqio@10.144.18.7
```

第一次连接可能会出现：
```text
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```
输入：
```text
yes
```

然后输入树莓派密码。

> 注意：输入密码时 **屏幕上不会显示任何字符**，这是正常现象。

### 3. 如果第一次连接失败
如果出现：
```text
Connection closed by ... port 22
```
不要慌，通常不是坏了，而是：
- 树莓派刚启动完，SSH 服务还没稳定
- 第一次连接时网络刚建立好

此时：
- 等 20～30 秒
- 再重新输入同一条 SSH 命令

如果还是不行，可以用：
```bash
ssh -v piqio@树莓派的IP地址
```
查看更详细的连接过程。

### 4. 成功标志
成功后会看到类似：
```bash
piqio@pi5:~ $
```

这说明：
- 电脑已经通过网络连上树莓派
- 后续所有操作都在这个终端里进行

---

## 二、第一次连上树莓派后，做哪些基础检查（可跳过）

### 1. 常用命令测试
```bash
pwd
ls
whoami
hostname
python3 --version
```

### 2. 新建实验目录
```bash
mkdir -p ~/experiment
cd ~/experiment
pwd
```

### 3. 测试 Python 是否能运行
```bash
nano test.py
```
输入：
```python
print("hello")
print("raspberry pi works")
```
保存退出：
- `Ctrl + O`
- 回车
- `Ctrl + X`

运行：
```bash
python3 test.py
```

如果输出正常，说明：
- 你已经能远程操作树莓派
- 你已经能新建和运行 Python 文件

---

## 三、Thermal-90 的正确硬件理解

Thermal-90 **不是 USB 摄像头**，而是 **HAT 扩展板**。  
它不是插电脑 USB 用的，而是：

- 直接插到树莓派的 **40 针 GPIO** 上
- 通过 **I2C + SPI + GPIO** 和树莓派通信

Thermal-90 通过 40 针 GPIO 安装在树莓派上；树莓派通过脚本完成数据采集、处理与输出。  
所以整个实验链条是：

**Thermal-90 → 树莓派 → 电脑（SSH 远程操作）**


---

## 四、Thermal-90 接到树莓派后的基础依赖安装

### 1. 安装基础依赖
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git i2c-tools python3-smbus python3-opencv python3-gpiozero python3-spidev
```

这几类库的作用：
- `i2c-tools` / `python3-smbus`：I2C 通信
- `python3-spidev`：SPI 通信
- `python3-gpiozero`：GPIO 控制
- `python3-opencv`：图像处理和显示

### 2. 检查 I2C / SPI 设备节点
```bash
ls /dev/i2c*
ls /dev/spidev*
```

实际可能看到类似：
```bash
/dev/i2c-13  /dev/i2c-14
/dev/spidev10.0
```

这说明：
- 树莓派底层已经有 I2C / SPI 设备节点
- 但这 **还不代表相机已经真正跑通**

### 3. 建立 Thermal-90 工作目录
```bash
mkdir -p ~/thermal90
cd ~/thermal90
pwd
```

### 4. 检查 Python 库能否导入
```bash
python3 -c "import cv2, smbus, spidev; print('basic imports ok')"
```

如果输出：
```bash
basic imports ok
```
说明最基础的软件环境已经没问题。

---

## 五、下载并安装官方 demo

### 1. 下载与安装
```bash
cd ~/thermal90

wget https://files.waveshare.com/wiki/Thermal-Camera-HAT/Pysenxor-master.zip
unzip -o Pysenxor-master.zip

sudo apt update
sudo apt install -y python3-numpy python3-smbus python3-crcmod python3-matplotlib python3-opencv unzip

wget https://files.pythonhosted.org/packages/25/47/f1d2c686253bea1454cc7db687a09ae912fbe4648a86ef7fcd9765f7639f/cmapy-0.6.6.tar.gz

tar -xzf cmapy-0.6.6.tar.gz
cd cmapy-0.6.6
sudo python3 setup.py install

cd ~/thermal90/pysenxor-master
sudo python3 setup.py install
```

---

## 六、必须同时启用 SPI 和 i2c_arm

**SPI 要开，I2C 主总线也要开。**

### 1. 打开配置文件
```bash
sudo nano /boot/firmware/config.txt
```

### 2. 确保下面三行存在且有效
```txt
dtparam=spi=on
dtparam=i2c_arm=on
dtoverlay=spi0-0cs
```

注意：
- 如果原来看到的是：
```txt
#dtparam=i2c_arm=on
```
要把前面的 `#` 删除，改成：
```txt
dtparam=i2c_arm=on
```

### 3. 保存退出
- `Ctrl + O`
- 回车
- `Ctrl + X`

### 4. 重启树莓派
```bash
sudo reboot
```

重启后等待 2～3 分钟，再重新通过 SSH 登录。

---

## 七、重启后，确认真正该用的 I2C 总线已经打开

### 1. 查看 I2C 设备
```bash
ls /dev/i2c*
i2cdetect -l
```

正确情况应当能看到：
```bash
/dev/i2c-1  /dev/i2c-13  /dev/i2c-14
```

这一步很关键：  
**必须出现 `/dev/i2c-1`。**

### 2. 扫描 `i2c-1`
```bash
sudo i2cdetect -y 1
```

正确情况应能看到地址 `40`：
```bash
40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
```

这说明：
- 相机真实挂在 `i2c-1`
- I2C 地址是 `0x40`
- Thermal-90 已被树莓派识别

> 这一点是整个过程中最关键的结论。  
> 一开始虽然能看到 `/dev/i2c-13` 和 `/dev/i2c-14`，但那不是 demo 真正要用的总线。  
> 官方 demo 需要的是 `i2c-1`。

---

## 八、检测运行 `grep -R "RPI_GPIO_I2C_CHANNEL" -n ..`

进入示例目录：
```bash
cd ~/thermal90/pysenxor-master/example
```

运行：
```bash
grep -R "RPI_GPIO_I2C_CHANNEL" -n ..
```

这条命令的作用：
- 在上一级目录及子目录里搜索
- 查看 `RPI_GPIO_I2C_CHANNEL` 被定义成几

正常输出类似：
```bash
../example/stream_spi.py:107:RPI_GPIO_I2C_CHANNEL = 1
```

这说明官方 demo 默认就是要用：
```python
RPI_GPIO_I2C_CHANNEL = 1
```

所以如果程序因为找不到 I2C 文件报错，通常**不要先改 Python 代码**，而应先检查：
- `i2c_arm` 是否真的开启
- `/dev/i2c-1` 是否出现
- `i2cdetect -y 1` 是否扫到 `0x40`

---

## 九、第一次运行官方示例程序

进入目录：
```bash
cd ~/thermal90/pysenxor-master/example
```

运行：
```bash
sudo python3 stream_spi.py
```

如果配置正确，会看到类似输出：
```text
Resetting the MI48...
Done.
...
INFO:__main__:Camera info:
...
DEBUG:__main__:FID     0  time      13  V_dd 3.316  T_SX 35.27
Min   14.8   Max   37.6  Avg  23.4  Std 2.8
```

这说明：
- 相机已经成功复位
- 相机信息已被读取
- 已进入连续采集模式
- 已成功读到热像帧

---

## 十、无显示器 SSH 环境下，必须关闭 GUI

### 1. 现象
如果直接运行 demo，可能报错：
```text
qt.qpa.xcb: could not connect to display
Could not load the Qt platform plugin "xcb"
Aborted
```

原因：
- 程序默认要弹 OpenCV 图形窗口
- 现在是 SSH 远程环境
- 没有本地图形界面，所以显示失败

### 2. 修改方法
编辑文件：
```bash
nano ~/thermal90/pysenxor-master/example/stream_spi.py
```

把显示部分：
```python
if GUI:
    cv_display(img8u)
    key = cv.waitKey(1)
    if key == ord("q"):
        break
```
改成：
```python
if False:
    cv_display(img8u)
    key = cv.waitKey(1)
    if key == ord("q"):
        break
```

### 3. 保存退出
- `Ctrl + O`
- 回车
- `Ctrl + X`

### 4. 重新运行
```bash
sudo python3 stream_spi.py
```

这样程序就不会再因为图形窗口而中断。

---

## 十一、如何判断 Thermal-90 已经真正跑通

如果程序持续输出类似：
```text
DEBUG:__main__:FID    16  time    2643  V_dd 3.316  T_SX 35.52
Min   20.0   Max   36.3  Avg  24.2  Std 3.2
```

就说明：
- 树莓派已经在连续读取热像帧
- 相机已经成功工作
- 终端打印的是每一帧的温度统计信息

各字段含义：
- `FID 16`：第 16 帧
- `time 2643`：程序运行到这一帧时经过约 2643 ms
- `V_dd 3.316`：模块供电电压约 3.316 V
- `T_SX 35.52`：模块内部参考温度约 35.52 ℃
- `Min 20.0`：该帧最低温度约 20.0 ℃
- `Max 36.3`：该帧最高温度约 36.3 ℃
- `Avg 24.2`：该帧平均温度约 24.2 ℃
- `Std 3.2`：该帧温度标准差约 3.2 ℃

### 关于偶发 CRC error
如果中间偶尔出现：
```text
Frame CRC error
```
或者有一帧温度变成 `-273.15`，但后续帧立刻恢复正常，通常只是：
- 偶发坏帧
- 不代表整体采集失败

只要后续还能继续稳定输出 `FID / Min / Max / Avg / Std`，就说明整体仍然是成功的。


---

## 十二、关机与下次重连

### 1. 结束采集
如果程序正在运行，按：
```text
Ctrl + C
```

### 2. 安全关机
不要直接拔电。先输入：
```bash
sudo shutdown now
```

等待 10～20 秒，再拔电源。

### 3. 下次重连的固定流程
- 给树莓派插电
- 等 2～3 分钟
- 电脑连同一个热点
- 查看树莓派 IP
- PowerShell 输入：
```bash
ssh piqio@树莓派的IP地址
```
- 如果第一次被断开，等 20～30 秒再试一次


---

## 十三、录制热像数据并在电脑端做第一次可视化分析

这一部分是在 **Thermal-90 已经跑通、`stream_spi.py` 能连续输出 FID / Min / Max / Avg / Std** 的基础上继续做的。  
目标是：

1. 把热像数据录制成文件  
2. 把文件从树莓派拷到电脑  
3. 在电脑上还原成热图  
4. 提取 ROI 温度曲线，初步判断数据质量

---

### 1. 录制数据前的小修正

在 `stream_spi.py` 中，官方 demo 的录制模式默认写的是：

```python
filename = get_filename(mi48.camera_id_hex)
```

但当前环境里实际可用的属性名是：

```python
mi48.camera_id_hexsn
```

所以需要改成：

```python
filename = get_filename(mi48.camera_id_hexsn)
```

否则运行 `-r` 时会报：

```text
AttributeError: 'MI48' object has no attribute 'camera_id_hex'
```

> 这是一个 demo 兼容性问题，不是相机没连好。

---

### 2. 用 `-r` 录制一段热像数据

进入示例目录：

```bash
cd ~/thermal90/pysenxor-master/example
```

运行录制：

```bash
sudo python3 stream_spi.py -r
```

如果程序正常，会持续输出类似：

```text
DEBUG:__main__:FID    10  time    1658  V_dd 3.316  T_SX 34.15
  Min   19.3   Max   32.3  Avg  23.4  Std 1.7
```

含义：
- `FID`：第几帧
- `time`：到当前帧为止的时间（毫秒）
- `Min/Max/Avg/Std`：该帧的最低温、最高温、平均温度和标准差

录制完成后按：

```text
Ctrl + C
```

程序会正常结束，并输出类似：

```text
INFO:__main__:Exiting due to SIGINT or SIGTERM
INFO:__main__:Done.
```

---

### 3. 检查录制文件是否生成

录制完成后查看目录：

```bash
ls -lh ~/thermal90/pysenxor-master/example
```

会生成一个 `.dat` 文件，例如：

```text
2000.0.0.000000--20260403-161239.dat
```

这个文件就是录下来的热像数据。

> 每一行通常对应一帧，每帧包含 `62×80 = 4960` 个温度值。

---

### 4. 把 `.dat` 文件拷到电脑

**注意：这一步必须在电脑的 PowerShell 里执行，不是在树莓派 SSH 终端里执行。**

如果当前还在树莓派里，先退出：

```bash
exit
```

回到类似：

```text
PS C:\Users\28146>
```

再运行：

```bash
scp piqio@树莓派IP:/home/piqio/thermal90/pysenxor-master/example/文件名.dat .
```

例如：

```bash
scp piqio@10.144.18.7:/home/piqio/thermal90/pysenxor-master/example/2000.0.0.000000--20260403-161239.dat .
```

如果想直接拷到桌面，也可以把最后的 `.` 改成桌面路径。

> 如果在树莓派终端里误用了 Windows 路径，例如 `~/Desktop/`，很容易报：
> ```text
> scp: open local "~/Desktop/": No such file or directory
> ```
> 本质原因是：你在错误的机器上执行了拷贝命令。

---

### 5. 在电脑上读取 `.dat` 文件

在本地电脑写一个 Python 脚本，例如 `view_dat.py`，核心流程是：

1. 读取 `.dat` 文件所有行  
2. 每一行拆成浮点数  
3. 还原成形状为 `(帧数, 62, 80)` 的三维数组  
4. 保存热图和曲线图

运行成功后会看到类似输出：

```text
原始数组形状: (118, 4960)
重塑后形状: (118, 62, 80)
总帧数: 118
```

这说明：
- 一共有 118 帧
- 每帧是 4960 个像素
- 成功还原成 `62×80` 温度矩阵

---

### 6. 关于 `plt.show()` 的说明

如果脚本最后写了：

```python
plt.show()
```

有时窗口虽然弹出来了，但终端会出现：

```text
KeyboardInterrupt
```

这通常不是数据坏了，而是：
- `matplotlib` 正在维护图形窗口
- 程序在显示窗口过程中被手动中断或关闭

所以在当前阶段，更稳妥的做法是：

```python
plt.savefig("first_frame.png", dpi=200, bbox_inches="tight")
```

**先保存图片，不依赖交互窗口。**

---

### 7. 第一次本地可视化：热图与曲线

电脑端脚本建议至少输出这几类图：

#### （1）多帧热图对比
例如保存：

```text
frames_compare.png
```

用于比较第 `0 / 10 / 20` 帧热图，判断温度场是否变化明显。

#### （2）中心点温度曲线
例如保存：

```text
center_temp_curve.png
```

用于查看单个中心像素的温度随帧数变化。

#### （3）中心区域平均温度曲线
例如保存：

```text
center_roi_curve.png
```

做法：取中心附近 `5×5` 区域，计算每帧平均温度。  
这比单个像素稳定，更接近后面正式实验的“监测区域平均温度”。

---

### 8. 用程序自动找“最热点”

不要只靠肉眼看热图颜色，可以直接在脚本里算：

```python
first_max_idx = np.unravel_index(np.argmax(first_frame), first_frame.shape)
last_max_idx = np.unravel_index(np.argmax(last_frame), last_frame.shape)
```

输出类似：

```text
第一帧最高温位置(y, x): (52, 73) 温度: 39.34
最后一帧最高温位置(y, x): (61, 72) 温度: 36.16
```

这可以帮助判断：
- 最热点是否稳定
- 热源是否在画面边缘
- 目标是否真的进入了画面中心区域

---

### 9. 热区 ROI 曲线比中心 ROI 更重要

如果热源不在画面中心，那么中心 `5×5` 区域虽然也能反映变化，但不一定是真正最有代表性的区域。  
所以进一步做法是：

- 以第一帧最热点为中心
- 再取一个 `5×5` 热区 ROI
- 计算这个区域在每一帧的平均温度

例如输出：

```text
热区ROI前5帧温度: [32.9304 32.8412 32.4132 31.7488 31.3332]
热区ROI最后5帧温度: [30.7756 30.748  30.8256 30.9324 31.0848]
热区ROI最低温: 27.2060
热区ROI最高温: 32.9304
```

这类结果比中心 ROI 更接近真实热目标。

---

### 10. 如何解读当前采集到的数据

以这次 118 帧数据为例：

- 总帧数足够长，适合做曲线分析
- 最热点位置在右下区域附近，说明热源位置相对稳定
- 热区 ROI 从约 `32.93°C` 逐渐下降到约 `31.08°C`
- 中心 ROI 从约 `31.46°C` 缓慢降到约 `30.89°C`

这说明当前这一组数据更像：

**一个热目标在缓慢冷却的过程。**

而且热区 ROI 的变化幅度（约 `5.72°C`）明显大于中心 ROI（约 `0.95°C`），说明：

- 热区 ROI 更能代表真实热目标
- 中心 ROI 只是一个较温暖但不够敏感的区域

---

### 11. 到这里意味着什么

到这里，你已经完成了下面这条链路：

**树莓派采集热像 → 保存 `.dat` 文件 → 拷到电脑 → 还原热图 → 提取 ROI 曲线 → 识别热区变化**

这说明你已经不仅仅是“把设备调通”，而是已经进入：

**实验数据预处理与初步分析阶段。**

---

### 12. 这一阶段的经验结论

1. **树莓派端负责采集和保存数据**  
2. **电脑端负责可视化和 ROI 分析**  
3. 不必一开始就做复杂的 OpenCV 交互界面  
4. 当前最重要的是先得到：
   - 稳定的 `.dat` 数据文件
   - 清晰的热区 ROI 曲线
   - 较长时间的温度响应过程

---

### 13. 下一步建议

接下来建议继续做：

1. 把横轴从“帧号”改成“时间（秒）”  
2. 在同一张图上同时画：
   - `center_roi_temp`
   - `hot_roi_temp`
3. 固定热源和相机位置，采集更标准的一组实验数据  
4. 再把 ROI 从“自动找热区”过渡到“固定样品监测区”  
5. 最终进入正式实验流程：加热、取样、保存、分析、反演导热系数

也就是说，当前这一部分的任务是：

**把热像数据从“采下来”推进到“能在电脑上稳定分析”。**
