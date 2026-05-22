import torch
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# -------- 模型定义 --------
class AlphaNet(torch.nn.Module):
    def __init__(self, hidden_dim=32):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(2, hidden_dim),
            torch.nn.Tanh(),
            torch.nn.Linear(hidden_dim, hidden_dim),

            torch.nn.Tanh(),
            torch.nn.Linear(hidden_dim, 1)
        )

    def forward(self, x, y):
        inputs = torch.cat([x, y], dim=1)
        return self.net(inputs)

# -------- 加载模型 --------
alpha_net = AlphaNet(hidden_dim=32)
state_dict = torch.load("alpha_net.pt", map_location='cpu')
alpha_net.load_state_dict(state_dict)
alpha_net.eval()

# -------- 构造坐标网格 --------
x = np.linspace(0, 1, 100)
y = np.linspace(0, 1, 100)
X, Y = np.meshgrid(x, y)
x_tensor = torch.tensor(X.flatten(), dtype=torch.float32).unsqueeze(1)
y_tensor = torch.tensor(Y.flatten(), dtype=torch.float32).unsqueeze(1)

# -------- 温度预测 --------
with torch.no_grad():
    T_pred = alpha_net(x_tensor, y_tensor).numpy().reshape(X.shape)

# -------- 三维图 --------
fig = plt.figure(figsize=(12, 5))

# --- 3D 温度分布图 ---
ax = fig.add_subplot(121, projection='3d')
ax.plot_surface(X, Y, T_pred, cmap='hot')
ax.set_title('3D Temperature Distribution')
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.set_zlabel('Temperature')

# --- 2D 等高图 ---
ax2 = fig.add_subplot(122)
contour = ax2.contourf(X, Y, T_pred, cmap='hot')
fig.colorbar(contour, ax=ax2)
ax2.set_title('2D Temperature Map')
ax2.set_xlabel('x')
ax2.set_ylabel('y')

plt.tight_layout()
plt.savefig('temperature_distribution.png', dpi=300)
plt.show()

# -------- 反演导热系数 α 输出 --------
alpha_value = float(state_dict['net.4.weight'].mean())  # 取最后线性层的权重均值作为 α 近似
print(f"\n【反演导热系数 α 估计值】: {alpha_value:.5f}")