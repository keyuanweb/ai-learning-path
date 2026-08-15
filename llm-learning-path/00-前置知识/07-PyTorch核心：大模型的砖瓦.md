# PyTorch 核心：大模型的砖瓦

> PyTorch 是大模型的事实标准工具。LLaMA、Qwen、DeepSeek——全部用 PyTorch 实现。这章用乐高积木的比喻，帮你理解 PyTorch 的核心模块。

---

## 1. 乐高积木的比喻

如果把大模型比作一个复杂的乐高城堡，PyTorch 提供的三个核心工具就是：

| PyTorch 模块 | 乐高比喻 | 干什么 |
|-------------|---------|--------|
| **Tensor** | 积木块 | 存储数据的多维数组，GPU 上并行计算 |
| **Autograd** | 自动"检测员" | 自动计算每个积木对最终结果的贡献（梯度） |
| **nn.Module** | 说明书 | 把积木块按步骤组织成模型，管理参数 |

---

## 2. Tensor：乐高积木块

### 这玩意儿干嘛的

Python 的列表（list）是通用的，但做数学运算太慢——每个元素都是独立的对象，无法 GPU 加速。Tensor 把数据打包成**连续内存块**——一个指令就能对所有元素同时操作。

### PyTorch Tensor vs Python 列表

```python
# Python 列表——每个元素逐个处理
a = [1, 2, 3]
result = [x * 2 for x in a]  # 逐个乘 2，CPU 只能串行

# PyTorch Tensor——一条指令批量处理
a = torch.tensor([1, 2, 3], device='cuda')
result = a * 2  # 一次性操作所有元素，GPU 千核心并行
```

### 三个核心维度操作

在大模型代码中，你会频繁看到 tensor 的"变形"：

```python
x.shape  # torch.Size([32, 512, 4096])   batch=32句话, seq_len=512个token, d_model=4096维

# view: 换个角度看同一块内存（不拷贝数据！）
x = x.view(32, 8, 512, 128)  # 把 4096 拆成 8 个头 × 128 维——"拆分多头"

# transpose: 交换两个维度（也不拷贝数据！）
x = x.transpose(1, 2)  # [32, 512, 8, 128] → 把 seq 和 heads 换位置

# unsqueeze: 增加一个维度
x = x.unsqueeze(0)  # [512, 4096] → [1, 512, 4096]   (加 batch 维度)
```

**有个大坑**：`.view()` 要求内存连续，否则会报错。如果你前面做了 `.transpose()`，内存就不是连续的了，这时要用 `.reshape()` 或者先 `.contiguous().view()`。

### 数据类型与显存

| 类型 | 每个数字占 | 7B 模型显存 |
|------|---------|-----------|
| float32 | 4 字节 | ~28 GB |
| bfloat16 | 2 字节 | ~14 GB |
| int8 | 1 字节 | ~7 GB |
| int4 | 0.5 字节 | ~3.5 GB |

```python
# 把参数从 FP32 切到 BF16 → 显存减半，精度几乎不变
model = model.to(torch.bfloat16)

# 推理时把数据也切 BF16
x = x.to(device='cuda', dtype=torch.bfloat16)
```

**为什么用 BF16 而不是 FP16**：BF16 的指数范围跟 FP32 一样大（8 位指数），不容易溢出。FP16 只有 5 位指数，大模型训练时很容易碰到梯度下溢。

---

## 3. Autograd：自动"检测员"

### 这玩意儿干嘛的

你搭好了乐高城堡（模型），想知道"调整第 3 层的第 42 个参数会对最终结果产生多大影响"。手动算？30 层的 Transformer 有几千亿个计算步骤，完全不可能。

Autograd 帮你自动完成。
- 前向时记录每步运算
- 反向时沿记录链自动求梯度

### 三个关键操作

```python
# 1. 推理：告诉 PyTorch "别记录计算图，我不需要梯度"
with torch.no_grad():
    output = model(input_ids)   # 省显存 + 加速

# 2. 切断梯度：想让某个 tensor 不再参与梯度计算
x = x.detach()  # x 变成一个普通值，梯度到它就断了
# 场景：评估时不需要梯度，或者知识蒸馏中需要冻结 teacher 模型

# 3. 清零梯度：每次更新参数前必须做！
optimizer.zero_grad()  # 如果不做，batch2 的梯度会累加到 batch1 上
loss.backward()        # 算梯度
optimizer.step()       # 更新参数
```

**为什么梯度会累积**：PyTorch 的设计是每次 `backward()` 后梯度**累加**到 `.grad` 上，而不是替换。这样设计是因为梯度累积（Gradient Accumulation）是大模型训练的常见技巧。

---

## 4. nn.Module：乐高说明书

### 这玩意儿干嘛的

一个大模型有几百个子模块（Embedding + 32 层 Transformer + Norm + lm_head）。需要一个系统化的方式来组织它们。

`nn.Module` 提供的核心能力：
- **参数自动管理**：`model.parameters()` 递归收集所有参数
- **设备统一管理**：`model.to('cuda')` 一键搬到 GPU
- **模式切换**：`model.train()` / `model.eval()` 控制 Dropout 等行为
- **状态保存**：`model.state_dict()` → 保存/加载模型权重

### register_buffer：不参与训练但需要保存的数据

这是很多新手不理解的概念：

```python
class MyAttention(nn.Module):
    def __init__(self):
        super().__init__()
        # 因果掩码：不需要训练（不是参数），但要跟模型一起保存和移动
        self.register_buffer('causal_mask', self.create_mask(max_len=2048))

    # 普通参数 vs Buffer
    # self.linear = nn.Linear(...)   → 会训练，state_dict 保存
    # self.register_buffer(...)      → 不训练，state_dict 保存，model.to(device) 会跟随
```

大模型中的因果掩码、RoPE 的 cos/sin 预计算表都用 buffer。

---

## 5. 训练循环：一个完整的"猜-看-改"流水线

```python
import torch
import torch.nn.functional as F

model = MyTransformer().to(device)       # 1. 建模型，搬到 GPU
optimizer = torch.optim.AdamW(           # 2. 创建优化器
    model.parameters(),
    lr=1e-4,
    weight_decay=0.1
)

for batch in dataloader:                 # 3. 开始循环
    # === 前向传播（"猜"） ===
    with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
        logits = model(batch['input_ids'])        # 模型输出
        loss = F.cross_entropy(                   # 跟答案比较
            logits.view(-1, vocab_size),
            batch['labels'].view(-1)
        )

    # === 反向传播（"看差距"） ===
    optimizer.zero_grad()               # 清空上一轮的梯度
    loss.backward()                     # 自动计算所有参数的梯度

    # === 梯度裁剪（"别让一步迈太大"） ===
    torch.nn.utils.clip_grad_norm_(
        model.parameters(), max_norm=1.0
    )

    # === 参数更新（"改"） ===
    optimizer.step()                    # 根据梯度微调所有参数
```

每一行都有"为什么"：

| 代码 | 解决什么问题 |
|------|-----------|
| `torch.autocast` | 混合精度——省一半显存，加速 30% |
| `zero_grad()` | 梯度会累积，不重置就变成"多轮梯度叠加" |
| `clip_grad_norm` | 一个异常 batch 可能产生巨大梯度，把模型"炸飞" |
| `loss.view(-1, vocab_size)` | 把 [B, T, V] 摊平成 [B×T, V]，交叉熵只接受二维 |
| `weight_decay=0.1` | AdamW 的 L2 正则化——防止参数膨胀 |

---

## 6. 大模型中的 5 个核心模式

### 1. 移动设备：`.to(device)`
```python
model.to('cuda')      # 模型搬到 GPU
x = x.to('cuda')      # 数据搬到 GPU
# 习惯：在脚本开头设 device = 'cuda' if torch.cuda.is_available() else 'cpu'
```

### 2. 改变形状：`.view()` vs `.reshape()`
```python
# view: 不拷贝，但要求内存连续
x.view(B, T, H, D)

# reshape: 安全但可能拷贝
x.reshape(B, T, H, D)

# 经验：不知道内存是否连续时用 reshape
```

### 3. 调整维度顺序：`.transpose()` 和 `.permute()`
```python
# transpose: 交换两个维度
x = x.transpose(1, 2)  # [B, S, H, D] → [B, H, S, D]

# permute: 按任意顺序重排所有维度
x = x.permute(0, 2, 1, 3)  # 同上，但更灵活
```

### 4. 拼接与拆分
```python
# 沿最后一维切分——Attention 中把 X 拆成 Q/K/V
Q, K, V = torch.split(x, d_head, dim=-1)

# 沿某一维拼接——多头输出合回一起
x = torch.cat([head0, head1, ..., head7], dim=-1)
```

### 5. 矩阵乘法：`@`, `torch.matmul`, `torch.bmm`
```python
# @ = torch.matmul: 支持广播的标准矩阵乘
scores = Q @ K.transpose(-2, -1)  # 最常用

# torch.bmm: batch 矩阵乘，输入必须是 3D
# 老代码中常见，现在 @ 就够用了
```

---

## 本章速查

| 概念 | 一句话解释 |
|------|----------|
| **Tensor** | GPU 上的多维数组（乐高积木块） |
| **Autograd** | 自动算梯度（"每个参数对结果影响多大"） |
| **nn.Module** | 模型组织框架（乐高说明书） |
| **训练循环** | 猜→比答案→算梯度→改参数→重复 |
| **BF16** | 半精度训练，跟 FP32 一样范围，不会溢出 |
| **梯度累积** | 多 batch 才更新一次参数，用小显存模拟大 batch |
| **梯度裁剪** | 限制最大梯度，防止一个 batch 炸飞模型 |
| **register_buffer** | 不训练但要跟随模型保存/移动的数据 |

**记住这个就够了**：PyTorch 让你用搭积木的方式定义模型，用 3 行代码（`zero_grad`→`backward`→`step`）完成一次参数更新。
