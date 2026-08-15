# 必备 Python 速通

> 这章不讲 Python 基础语法（if/for/def），假设你至少写过几十行 Python。我们聚焦大模型代码中频繁出现、但初学者经常看不懂的几个高阶特性。

---

## 1. 列表推导式：一行写循环

### 这玩意儿干嘛的

把循环和条件写到一行里，简洁但可读。

### 直观例子

```python
# 正常写法
squares = []
for i in range(10):
    squares.append(i ** 2)

# 列表推导式 —— 一句话等价于上面三行
squares = [i ** 2 for i in range(10)]

# 加条件
even_squares = [i ** 2 for i in range(10) if i % 2 == 0]
```

在大模型项目中，你经常看到这种用法来构造数据：

```python
# 从 dataset 中选长度小于 2048 的样本
short_texts = [s for s in dataset if len(s) < 2048]
```

**记住这个就够了**：`[对每个元素的处理 for 元素 in 来源 if 条件]`，从左往右读即可。

---

## 2. 类型提示：给变量贴标签

### 这玩意儿干嘛的

Python 不会检查类型，但**人需要知道**。在一个几百行的函数里，看到 `x` 你完全不知道它是 int 还是 tensor。类型提示就是给人看的"注释"，让代码可读。

### 直观例子

```python
# 没提示 —— 完全不知道 input_ids 是什么
def process(input_ids):
    ...

# 有提示 —— 一目了然
def process(input_ids: torch.Tensor) -> torch.Tensor:
    ...

# 大模型项目中常见写法
def forward(
    self,
    x: torch.Tensor,           # [batch, seq_len, d_model]
    attention_mask: torch.Tensor | None = None,  # 可以为 None
) -> tuple[torch.Tensor, torch.Tensor]:          # 返回两个 tensor
    ...
```

**记住这个就够了**：类型提示是给人看的，不影响运行，但它让你的代码从"天书"变成"文档"。

---

## 3. Context Manager：`with` 语句

### 这玩意儿干嘛的

有些资源用完需要"归还"——文件要关闭、锁要释放、梯度要关闭。你当然可以手动归还，但 `with` 保证了无论发生什么（包括报错），资源都一定会被释放。

### 直观例子

```python
# 不用 with —— 可能忘记 close，出异常时更不会 close
f = open('data.json')
data = json.load(f)
f.close()  # 容易忘！

# 用 with —— 自动 close
with open('data.json') as f:
    data = json.load(f)
# 出了这个缩进，文件自动关闭
```

### 大模型中的核心用法

```python
# 推理时不构建计算图——省显存
with torch.no_grad():
    output = model(input_ids)

# 混合精度——自动管理运算精度
with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
    logits = model(input_ids)
    loss = loss_fn(logits, labels)
```

**记住这个就够了**：`with` = "我借了这个资源，用完请自动还"。`torch.no_grad()` 借的是"不记录梯度的运行模式"。

---

## 4. Class 基础：面向对象的最小必要知识

### 这玩意儿干嘛的

大模型就是一个巨大的 class。LLaMA、GPT、Qwen——它们都是 `nn.Module` 的子类。

打个比方：class 像建筑蓝图，instance 像根据蓝图盖出来的房子。`nn.Module` 是所有模型蓝图的"母版"——它提供了建造房子的基本工具（参数管理、设备移动、保存加载）。

### 最简模型示例

```python
import torch.nn as nn

class MyFirstModel(nn.Module):
    def __init__(self):
        super().__init__()   # 必须调用父类的初始化——"继承建筑工具"
        self.linear = nn.Linear(128, 10)  # 注册一个参数层

    def forward(self, x):
        return self.linear(x)  # 定义数据怎么流动
```

### 三个核心概念

| 概念 | 直觉 |
|------|------|
| `__init__` | 建筑蓝图——定义模型有哪些"零件"（层、参数） |
| `forward()` | 流水线——零件怎么串起来工作 |
| `super().__init__()` | 继承建筑工具——获取参数管理、设备移动等能力 |

### 在大模型中的体现

```python
# 实际 LLaMA 代码的简化版结构
class LlamaModel(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.layers = nn.ModuleList([  # 32 个相同的 block
            LlamaDecoderLayer(config) for _ in range(config.num_layers)
        ])
        self.norm = RMSNorm(config.hidden_size)

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)          # 一层一层地加工
        return self.norm(x)       # 最后归一化
```

**记住这个就够了**：`__init__` 定义有什么零件，`forward` 定义怎么流水线处理。`super().__init__()` 别忘写。

---

## 5. 装饰器：给函数套一层壳

### 这玩意儿干嘛的

你想在不改函数源码的情况下，给函数加上额外行为（比如计时、缓存、关闭梯度）。装饰器就是"给函数包一层外衣"。

### 直观例子

```python
# @torch.no_grad() 等价于把整个函数包在 with torch.no_grad() 里面
@torch.no_grad()
def generate(model, prompt):
    ...  # 这里面的所有运算都不需要梯度

# 不用装饰器的等价写法
def generate(model, prompt):
    with torch.no_grad():
        ...
```

### 大模型中的其他装饰器

```python
# @staticmethod：这个方法不需要 self，就是个普通函数
class MyModel(nn.Module):
    @staticmethod
    def create_mask(seq_len):
        return torch.triu(torch.ones(seq_len, seq_len))  # "不需要模型状态，只是工具函数"

# @property：把方法伪装成属性
class ModelConfig:
    @property
    def total_params(self):
        return sum(p.numel() for p in self.model.parameters())
# 使用: config.total_params  (不用加括号!)
```

**记住这个就够了**：`@decorator` = 给函数包层壳，等价于 `decorator(original_function)`。你不需要会写装饰器，但需要认识 `@torch.no_grad()` 和 `@staticmethod`。

---

## 6. 迭代器与生成器：边吃边做

### 这玩意儿干嘛的

想象你要处理 100GB 的数据。如果先把所有数据加载到内存再处理——内存炸了。生成器让你**一次只产生一条数据，边产生边处理**。

### 直观例子

```python
# 用 return —— 全部加载到内存
def read_all_lines(path):
    lines = []
    with open(path) as f:
        for line in f:
            lines.append(line.strip())
    return lines  # 100GB 的文件会撑爆内存

# 用 yield —— 一条一条产生，不占内存
def read_lines(path):
    with open(path) as f:
        for line in f:
            yield line.strip()  # 每次只"喷"出一条

# 使用
for line in read_lines('huge_file.txt'):
    process(line)  # 一条一条处理，内存始终很小
```

### 在大模型中的应用

```python
# PyTorch DataLoader 内部就是靠生成器，一批一批喂数据
dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
for batch in dataloader:   # 每次只产生一个 batch，不占太多内存
    loss = train_step(batch)
```

**记住这个就够了**：`return` = 一锅全端出来，`yield` = 一碗一碗盛给你。处理大数据用 `yield`。

---

## 本章速查

| 语法 | 一句话解释 | 大模型场景 |
|------|----------|-----------|
| `[x for x in ...]` | 一行写循环 | 数据过滤、预处理 |
| `def fn(x: int) -> str` | 给人看的类型标签 | 所有大模型代码 |
| `with ... as ...` | 用完自动还 | `with torch.no_grad()` |
| `class M(nn.Module)` | 盖房子的蓝图 | 所有模型都是这样定义的 |
| `@decorator` | 给函数包壳 | `@torch.no_grad()` |
| `yield` | 一次给一点 | 大数据加载、批量训练 |

如果你对每个概念都能用一句话解释清楚，说明你已经可以继续往下看了。
