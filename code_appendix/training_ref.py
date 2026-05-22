import torch
import torch.nn as nn
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
import pandas as pd
import os
import sys
# 设备配置
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

class PINN(nn.Module):
def __init__(self):
super(PINN, self).__init__()
# 神经网络结构（预测温度场u(t,x)）
self.layer = nn.Sequential(
nn.Linear(2, 20), nn.Tanh(),
nn.Linear(20, 20), nn.Tanh(),
nn.Linear(20, 20), nn.Tanh(),
nn.Linear(20, 20), nn.Tanh(),
nn.Linear(20, 20), nn.Tanh(),
nn.Linear(20, 1)
).to(device)
# 导热系数α 作为可学习参数（初始化为0.5，限制为正数）

self.alpha = nn.Parameter(torch.tensor(0.5, device=device))
def forward(self, t, x):
u = self.layer(torch.cat([t, x], dim=1))
return u
def physics_loss(model, t, x):
"""物理损失：满足热传导方程"""
u = model(t, x)
# 计算偏导数
u_t = torch.autograd.grad(u, t, torch.ones_like(u), create_graph=True)[0]
u_x = torch.autograd.grad(u, x, torch.ones_like(u), create_graph=True)[0]
u_xx = torch.autograd.grad(u_x, x, torch.ones_like(u), create_graph=True)[0]
# 热传导方程残差（使用模型中的可学习α）
residual = u_t - model.alpha * u_xx
return residual.pow(2).mean()

def boundary_loss(model, t_bc, x_left, x_right, left_value=0, right_value=0):
"""边界损失：u(t, -1)=left_value 和 u(t, 1)=right_value"""
u_left = model(t_bc, x_left)
u_right = model(t_bc, x_right)
# 计算与目标边界值的差异
loss_left = (u_left - left_value).pow(2).mean()
loss_right = (u_right - right_value).pow(2).mean()
return loss_left + loss_right

def initial_loss(model, x_ic):
"""初始损失：u(0, x) = exp(-x^2 / (2*sigma^2)) 高斯分布"""
t_0 = torch.zeros_like(x_ic).to(device)
u_init = model(t_0, x_ic)

# 高斯分布参数（可根据需要调整）
sigma = 0.5 # 标准差
u_exact = torch.exp(-x_ic.pow(2) / (2 * sigma ** 2))
return (u_init - u_exact).pow(2).mean()

def data_loss(model, t_data, x_data, u_data):
"""数据损失：预测值与观测数据的误差"""
u_pred = model(t_data, x_data)
return (u_pred - u_data).pow(2).mean()

def load_synthetic_data(file_path="synthetic_data.csv"):
"""从CSV 文件加载合成数据"""
if not os.path.exists(file_path):

print(f"错误: 文件 {file_path} 不存在!")
print("请先运行 generate_data.py 生成符合高斯分布初始条件和非零边界条件的数据")
sys.exit(1)
df = pd.read_csv(file_path)
t_data = torch.tensor(df['t'].values, dtype=torch.float32).view(-1, 1).to(device)
x_data = torch.tensor(df['x'].values, dtype=torch.float32).view(-1, 1).to(device)
u_data = torch.tensor(df['u'].values, dtype=torch.float32).view(-1, 1).to(device)

print(f"从 {file_path} 加载了 {len(df)} 个数据点")
print(f"数据范围: t ∈ [{df['t'].min():.3f}, {df['t'].max():.3f}]")
print(f"数据范围: x ∈ [{df['x'].min():.3f}, {df['x'].max():.3f}]")
print(f"数据范围: u ∈ [{df['u'].min():.3f}, {df['u'].max():.3f}]")
return t_data, x_data, u_data

def train(model, optimizer, t_data, x_data, u_data, num_epochs):
losses = []
alpha_history = [] # 记录α 的学习过程
model.to(device)
# 边界条件值（根据您的实际需求调整）
left_bc_value = 0
right_bc_value = 0
for epoch in tqdm(range(num_epochs), desc="Training"):
optimizer.zero_grad()
# 1. 物理损失（内部点采样）
t_physics = torch.rand(3000, 1).to(device)
x_physics = (torch.rand(3000, 1) * 2 - 1).to(device)
t_physics.requires_grad = True
x_physics.requires_grad = True
f_loss = physics_loss(model, t_physics, x_physics)
# 2. 边界损失
t_bc = torch.rand(500, 1).to(device)
x_left = -torch.ones(500, 1).to(device)
x_right = torch.ones(500, 1).to(device)
bc_loss = boundary_loss(model, t_bc, x_left, x_right, left_bc_value, right_bc_value)
# 3. 初始条件损失
x_ic = (torch.rand(1000, 1) * 2 - 1).to(device)
ic_loss = initial_loss(model, x_ic)
# 4. 数据损失（使用观测数据）
d_loss = data_loss(model, t_data, x_data, u_data)
# 总损失（平衡各损失项权重）
loss = f_loss + bc_loss + ic_loss + 10.0 * d_loss # 数据损失权重可调整
loss.backward()
optimizer.step()

# 记录损失和α 值
losses.append(loss.item())
alpha_history.append(model.alpha.item())
if epoch % 1000 == 0:
print(f'Epoch {epoch}, Loss: {loss.item():.6f}, Alpha: {model.alpha.item():.6f}')
return losses, alpha_history
# 主程序
if __name__ == "__main__":
# 检查并加载合成数据
data_file = "synthetic_data.csv"
t_data, x_data, u_data = load_synthetic_data(data_file)
# 初始化模型和优化器
model = PINN()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
# 训练模型
losses, alpha_history = train(model, optimizer, t_data, x_data, u_data, num_epochs=5000)
# 结果可视化函数
def plot_results(model, losses, alpha_history, alpha_true=0.5):
# 1. 损失曲线
plt.figure(figsize=(10, 6))
plt.plot(losses, color='blue', lw=1.5, alpha=0.7)
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.title('Training Loss Curve')
plt.grid(True, alpha=0.3)
plt.yscale('log') # 使用对数坐标更好地显示损失变化
plt.show()
# 2. 导热系数α 的学习曲线
plt.figure(figsize=(10, 6))
# 绘制α 的实时值
plt.plot(alpha_history, label='Learned α', color='red', lw=1.5, alpha=0.7)
# 计算移动平均以显示收敛趋势
window_size = min(50, len(alpha_history) // 10) # 动态窗口大小
if window_size > 1:
alpha_ma = np.convolve(alpha_history, np.ones(window_size) / window_size, mode='valid')
plt.plot(range(window_size - 1, len(alpha_history)), alpha_ma,
label=f'Moving Average (window={window_size})', color='darkred', lw=2)
# 添加最终收敛值线
final_alpha = alpha_history[-1]
plt.axhline(y=final_alpha, color='green', linestyle='--',
label=f'Final α={final_alpha:.4f}')
plt.xlabel('Epoch')
plt.ylabel('α')
plt.title('Evolution of Thermal Conductivity')

plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
# 3. 数据拟合效果
with torch.no_grad():
u_pred = model(t_data, x_data).cpu().numpy()
plt.figure(figsize=(10, 6))
plt.scatter(u_data.cpu().numpy(), u_pred, alpha=0.5, s=10)
# 计算R²值
u_data_np = u_data.cpu().numpy()
ss_res = np.sum((u_data_np - u_pred) ** 2)
ss_tot = np.sum((u_data_np - np.mean(u_data_np)) ** 2)
r_squared = 1 - (ss_res / ss_tot)
# 添加完美拟合线和R²值
min_val = min(u_data_np.min(), u_pred.min())
max_val = max(u_data_np.max(), u_pred.max())
plt.plot([min_val, max_val], [min_val, max_val], 'k--', lw=2)
plt.text(0.05, 0.95, f'R² = {r_squared:.4f}',
transform=plt.gca().transAxes, fontsize=12,
verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
plt.xlabel('Measured u')
plt.ylabel('Predicted u')
plt.title('Data Fitting Quality')
plt.grid(True, alpha=0.3)
plt.show()
# 4. 初始条件拟合效果
sigma = 0.5 # 与initial_loss 中使用的相同
x_ic_vis = torch.linspace(-1, 1, 100).view(-1, 1).to(device)
t_0_vis = torch.zeros_like(x_ic_vis).to(device)
with torch.no_grad():
u_init_pred = model(t_0_vis, x_ic_vis).cpu().numpy()
u_exact_initial = np.exp(-x_ic_vis.cpu().numpy() ** 2 / (2 * sigma ** 2))
plt.figure(figsize=(10, 6))
plt.plot(x_ic_vis.cpu().numpy(), u_exact_initial, 'r-', label='Exact Initial Condition')
plt.plot(x_ic_vis.cpu().numpy(), u_init_pred, 'b--', label='Predicted Initial Condition')
plt.xlabel('x')
plt.ylabel('u(0, x)')
plt.title('Initial Condition: Gaussian Distribution')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
# 5. 边界条件拟合效果
t_bc_vis = torch.linspace(0, 1, 100).view(-1, 1).to(device)
x_left_vis = -torch.ones_like(t_bc_vis).to(device)

x_right_vis = torch.ones_like(t_bc_vis).to(device)
with torch.no_grad():
u_left_pred = model(t_bc_vis, x_left_vis).cpu().numpy()
u_right_pred = model(t_bc_vis, x_right_vis).cpu().numpy()
# 边界条件值（与训练中使用的相同）
left_bc_value = 0
right_bc_value = 0
plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.plot(t_bc_vis.cpu().numpy(), u_left_pred, 'b-', label='Predicted Left Boundary')
plt.axhline(y=left_bc_value, color='r', linestyle='--', label='Target Left Boundary')
plt.xlabel('Time (t)')
plt.ylabel('u(t, -1)')
plt.title('Left Boundary Condition')
plt.legend()
plt.grid(True, alpha=0.3)
plt.subplot(1, 2, 2)
plt.plot(t_bc_vis.cpu().numpy(), u_right_pred, 'b-', label='Predicted Right Boundary')
plt.axhline(y=right_bc_value, color='r', linestyle='--', label='Target Right Boundary')
plt.xlabel('Time (t)')
plt.ylabel('u(t, 1)')
plt.title('Right Boundary Condition')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
# 6. 最终3D 温度场
x = torch.linspace(-1, 1, 100).unsqueeze(1).to(device)
t = torch.linspace(0, 1, 100).unsqueeze(1).to(device)
X, T = torch.meshgrid(x.squeeze(), t.squeeze(), indexing='ij')
x_flat = X.reshape(-1, 1).to(device)
t_flat = T.reshape(-1, 1).to(device)
with torch.no_grad():
u_pred = model(t_flat, x_flat).cpu().numpy().reshape(100, 100)
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')
surf = ax.plot_surface(X.cpu().numpy(), T.cpu().numpy(), u_pred,
cmap='viridis', edgecolor='none', alpha=0.8)
# 添加颜色条
fig.colorbar(surf, ax=ax, shrink=0.5, aspect=20, label='Temperature (u)')
ax.set_xlabel('Position (x)')
ax.set_ylabel('Time (t)')
ax.set_zlabel('Temperature (u)')
ax.set_title(f'Predicted Temperature Field (α={model.alpha.item():.4f})')

# 调整视角以便更好地观察
ax.view_init(elev=20, azim=45)
plt.show()
# 7. 添加收敛分析图
plt.figure(figsize=(10, 6))
# 计算α 值的相对变化率
alpha_array = np.array(alpha_history)
relative_change = np.abs(np.diff(alpha_array)) / alpha_array[:-1]
# 绘制相对变化率
plt.semilogy(range(1, len(alpha_array)), relative_change,
color='purple', lw=1.5, alpha=0.7, label='Relative Change')
# 添加收敛阈值线（例如0.1%）
convergence_threshold = 0.001
plt.axhline(y=convergence_threshold, color='red', linestyle='--',
label=f'Convergence Threshold ({convergence_threshold * 100:.1f}%)')
# 找到首次低于阈值的位置
below_threshold = np.where(relative_change < convergence_threshold)[0]
if len(below_threshold) > 0:
first_convergence = below_threshold[0] + 1 # 因为relative_change 从第1 个epoch 开始
plt.axvline(x=first_convergence, color='green', linestyle='--',
label=f'First Convergence (Epoch {first_convergence})')
plt.xlabel('Epoch')
plt.ylabel('Relative Change in α')
plt.title('Convergence Analysis of Thermal Conductivity')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
plot_results(model, losses, alpha_history)