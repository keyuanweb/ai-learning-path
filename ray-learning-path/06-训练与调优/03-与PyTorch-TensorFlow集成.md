# 与 PyTorch / TensorFlow 集成

## 提出问题

大部分 ML 项目已经有 PyTorch 或 TensorFlow 代码。怎么把现有的训练脚本改成 Ray Train 格式？需要重写多少代码？能不能同时保留"本地调试"和"分布式运行"的能力？

## PyTorch 集成

### 从单机 PyTorch 迁移到 Ray Train

#### Step 1: 原始单机代码

```python
import torch
from torch.utils.data import DataLoader

# 单机训练
model = MyModel().cuda()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
dataloader = DataLoader(dataset, batch_size=64)

for epoch in range(10):
    for batch in dataloader:
        batch = batch.cuda()
        loss = model(batch)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
```

#### Step 2: 包装为 train_func

```python
from ray.train.torch import prepare_model, prepare_data_loader

def train_func(config):
    # 1. 模型（几乎不变）
    model = MyModel()
    model = prepare_model(model)  # 自动包装为 DDP

    # 2. 优化器（不变）
    optimizer = torch.optim.Adam(model.parameters(), lr=config.get("lr", 0.001))

    # 3. DataLoader（自动分片）
    dataloader = DataLoader(dataset, batch_size=64)
    dataloader = prepare_data_loader(dataloader)

    # 4. 训练循环（不变）
    for epoch in range(10):
        for batch in dataloader:
            # 不需要 .cuda() — prepare_model 已处理
            loss = model(batch)
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
```

#### Step 3: 启动

```python
from ray.train.torch import TorchTrainer
from ray.train import ScalingConfig

trainer = TorchTrainer(
    train_func,
    scaling_config=ScalingConfig(num_workers=4, use_gpu=True)
)
trainer.fit()
```

改动总结：加 `prepare_model` + `prepare_data_loader`，去掉 `.cuda()`。

### Lightning 集成

如果你已经在用 PyTorch Lightning：

```python
import pytorch_lightning as pl
from ray.train.lightning import RayTrainReportCallback, prepare_trainer

class MyLightningModel(pl.LightningModule):
    # ... 你的 Lightning 代码 ...

def train_func(config):
    model = MyLightningModel()
    trainer = pl.Trainer(
        max_epochs=10,
        callbacks=[RayTrainReportCallback()],  # Ray 集成回调
        strategy="ddp",                         # DDP 策略
        devices=1,                              # 每个 Worker 1 GPU
    )
    trainer = prepare_trainer(trainer)          # Ray 化
    trainer.fit(model, dataloader)

trainer = TorchTrainer(
    train_func,
    scaling_config=ScalingConfig(num_workers=4, use_gpu=True)
)
trainer.fit()
```

### Hugging Face Transformers 集成

```python
from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments
from ray.train.huggingface.transformers import prepare_trainer, RayTrainReportCallback

def train_func(config):
    model = AutoModelForSequenceClassification.from_pretrained("bert-base")
    model = ray.train.torch.prepare_model(model)

    args = TrainingArguments(
        output_dir="./checkpoints",
        per_device_train_batch_size=16,
        num_train_epochs=3,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
    )
    trainer = prepare_trainer(trainer)  # 分布式化
    trainer.train()
```

## TensorFlow 集成

### TensorFlow 单机到分布式

```python
# 原始 TensorFlow 代码
import tensorflow as tf

model = tf.keras.Sequential([...])
model.compile(optimizer="adam", loss="mse")
model.fit(dataset, epochs=10)
```

```python
# Ray Train 版本
from ray.train.tensorflow import prepare_dataset

def train_func(config):
    tf_config = ray.train.tensorflow.get_tf_config()  # 获取分布式配置

    strategy = tf.distribute.MultiWorkerMirroredStrategy()
    with strategy.scope():
        model = tf.keras.Sequential([...])
        model.compile(optimizer="adam", loss="mse")

    dataset = prepare_dataset(dataset)
    model.fit(dataset, epochs=10)

trainer = TensorflowTrainer(
    train_func,
    scaling_config=ScalingConfig(num_workers=4, use_gpu=True)
)
trainer.fit()
```

### Keras 回调

```python
from ray.train.tensorflow import RayTrainReportCallback

model.fit(
    dataset,
    epochs=10,
    callbacks=[RayTrainReportCallback()]  # 自动上报 metrics
)
```

## 自定义框架集成

如果你不用 PyTorch 或 TensorFlow（比如 JAX、自定义 C++ 库），Ray Train 也能支持：

```python
import ray
from ray.train import DataParallelTrainer

# Worker 函数
def train_func(config):
    # 获取分布式上下文
    world_rank = ray.train.get_context().get_world_rank()
    world_size = ray.train.get_context().get_world_size()

    # 手动处理分布式逻辑
    initialize_distributed_backend(rank=world_rank, size=world_size)

    # 训练
    for epoch in range(10):
        train_epoch()
        ray.train.report({"loss": loss})

trainer = DataParallelTrainer(
    train_func,
    scaling_config=ScalingConfig(num_workers=4)
)
trainer.fit()
```

## 本地调试技巧

### 单 Worker 调试

```python
# 开发时 num_workers=1，跟单机没区别
trainer = TorchTrainer(
    train_func,
    scaling_config=ScalingConfig(num_workers=1, use_gpu=False)  # CPU 调试
)
trainer.fit()
```

### 关闭 GPU 加速

```python
# 本地调试时用 CPU（启动快，方便 pdb）
trainer = TorchTrainer(
    train_func,
    scaling_config=ScalingConfig(num_workers=1, use_gpu=False)
)
```

### 保留单机运行能力

```python
def train_func(config):
    model = MyModel()
    model = ray.train.torch.prepare_model(model)  # 单 Worker 时 = no-op
    # ... 训练逻辑 ...

# 方式 1：Ray Train 运行
trainer = TorchTrainer(train_func, scaling_config=ScalingConfig(num_workers=4))
trainer.fit()

# 方式 2：直接调用（单机调试）
train_func({"lr": 0.001})
# prepare_model 在非 Ray 上下文中会退化为 no-op
```

## 通信后端选择

```python
import ray.train

# NCCL：NVIDIA GPU 专用，最快
# GLOO：CPU 或跨平台，兼容性好
scaling_config = ScalingConfig(
    num_workers=4,
    use_gpu=True,
    # Ray Train 自动选 NCCL（GPU）或 GLOO（CPU）
)

# 手动指定
from ray.train.torch import TorchConfig
trainer = TorchTrainer(
    train_func,
    torch_config=TorchConfig(backend="gloo"),  # 强制 GLOO
    scaling_config=scaling_config,
)
```

## 数据并行 vs 模型并行

### 数据并行（默认）

```python
# 每个 Worker 有完整模型副本
ScalingConfig(num_workers=8, use_gpu=True)
# 8 个 Worker，每个 1 GPU → 数据并行
# 有效 batch size = per_worker_batch × 8
```

### 模型并行（手动）

```python
# FSDP：模型参数分片
from torch.distributed.fsdp import FullyShardedDataParallel

def train_func(config):
    model = MyLargeModel()
    model = FullyShardedDataParallel(model)
    model = prepare_model(model)
    # 参数分散到所有 GPU，需要时才 gather
```

## 常见迁移问题

### 1. 随机种子

```python
# ❌ 所有 Worker 相同 seed → 数据增强相同 → 没有多样性
torch.manual_seed(42)

# ✅ 每个 Worker 不同 seed
import ray.train
rank = ray.train.get_context().get_world_rank()
torch.manual_seed(42 + rank * 1000)
```

### 2. 日志输出

```python
def train_func(config):
    rank = ray.train.get_context().get_world_rank()
    if rank == 0:  # 只在 rank 0 打印
        print(f"Epoch {epoch}, loss={loss}")
```

### 3. 模型保存

```python
def train_func(config):
    # ❌ 所有 Worker 都保存 → 冲突
    # torch.save(model.state_dict(), "model.pt")

    # ✅ 只在 rank 0 保存
    if ray.train.get_context().get_world_rank() == 0:
        torch.save(model.state_dict(), "model.pt")
```

## 性能对比参考

| 配置 | 训练速度 | 通信开销 | 适用场景 |
|------|----------|----------|----------|
| 1 GPU（基线） | 1× | 0% | 小模型调试 |
| 4 GPU 同节点 | ~3.8× | ~5% | 中等模型 |
| 8 GPU 同节点 | ~7.5× | ~6% | 中等模型 |
| 16 GPU 2 节点 | ~14× | ~12% | 大模型 |
| 64 GPU 8 节点 | ~50× | ~22% | 超大模型 |

实际效率取决于模型大小、batch size、网络带宽等因素。

## 小结

- PyTorch 迁移：加 `prepare_model` + `prepare_data_loader`，去掉 `.cuda()`
- Lightning 和 Transformers 有专门的集成回调
- TensorFlow 用 `MultiWorkerMirroredStrategy` + `prepare_dataset`
- 自定义框架用 `DataParallelTrainer`，手动管理分布式上下文
- 本地调试设置 `num_workers=1`，跟单机完全一样
- `prepare_model` 在非 Ray 上下文自动退化为 no-op，不影响单机运行
