# DeepSpeed 实战

DeepSpeed 是大模型分布式训练的事实标准框架。它将 ZeRO 优化策略封装成简洁的配置。

---

## 1. DeepSpeed 解决的问题

### 原始 PyTorch 分布式训练的痛点

- 需要手动管理模型分片、通信、梯度同步
- DP（DataParallel）效率低（梯度广播+汇总受 Python GIL 限制）
- DDP（DistributedDataParallel）单卡仍需装下完整模型
- 无法 offload 到 CPU/NVMe（显存放不下时只能减 batch size 或换更小的模型）

### DeepSpeed 的答案

- **ZeRO 自动分片**：一条配置开启不同级别的模型/优化器/梯度分片
- **Offload**：自动将优化器状态或参数 offload 到 CPU 内存甚至 NVMe 硬盘
- **通信优化**：梯度压缩、通信-计算重叠
- **混合精度整合**：与 BF16/FP16 AMP 无缝配合

---

## 2. 核心配置

### ZeRO-3 + CPU Offload 的典型配置

```json
{
  "train_batch_size": 256,
  "gradient_accumulation_steps": 8,
  "train_micro_batch_size_per_gpu": 4,

  "bf16": {
    "enabled": true
  },

  "zero_optimization": {
    "stage": 3,
    "offload_optimizer": {
      "device": "cpu",
      "pin_memory": true
    },
    "offload_param": {
      "device": "cpu",
      "pin_memory": true
    },
    "overlap_comm": true,
    "contiguous_gradients": true,
    "reduce_bucket_size": 5e8,
    "stage3_prefetch_bucket_size": 5e8,
    "stage3_param_persistence_threshold": 1e6,
    "stage3_max_live_parameters": 1e9,
    "stage3_max_reuse_distance": 1e9,
    "stage3_gather_16bit_weights_on_model_save": true
  },

  "optimizer": {
    "type": "AdamW",
    "params": {
      "lr": 3e-4,
      "betas": [0.9, 0.95],
      "eps": 1e-8,
      "weight_decay": 0.1
    }
  },

  "scheduler": {
    "type": "WarmupDecayLR",
    "params": {
      "warmup_min_lr": 0,
      "warmup_max_lr": 3e-4,
      "warmup_num_steps": 500,
      "total_num_steps": 10000
    }
  },

  "gradient_clipping": 1.0
}
```

---

## 3. 关键配置项解释

### ZeRO Stage

| Stage | 解决的问题 | 显存节省 | 通信开销 |
|-------|-----------|----------|---------|
| **Stage 1** | 优化器状态冗余 | ~4× | 最小 |
| **Stage 2** | Stage 1 + 梯度冗余 | ~8× | 中等 |
| **Stage 3** | Stage 2 + 参数冗余 | ~N×(GPU数) | 较高 |

**90% 的场景用 Stage 2 就够了**。Stage 3 用于 70B+ 模型或 GPU 显存极少的情况。

### Offload

| 配置 | 作用 | 代价 |
|------|------|------|
| `offload_optimizer` | 优化器状态放 CPU 内存 | 慢 20-30%（CPU↔GPU 传输） |
| `offload_param` | 暂不用的参数放 CPU | 更慢（参数也在 CPU↔GPU 间交换） |

**优先 offload optimizer**（性价比最高）。offload parameter 是最后的手段——显著增加训练时间。

### Gradient Accumulation Steps

```python
# 显存放不下足够大的 micro-batch? 用梯度累积模拟大batch
# actual_batch = micro_batch × accumulation_steps

每 accumulation_steps 步:
    1. 前向传播 (micro_batch)
    2. 反向传播 (计算梯度, 累积不更新)
    3. 重复 1-2
    4. 梯度平均 + 优化器 step

# 例如: 每GPU micro_batch=4, 累积8步, 8张GPU
# 等效 batch_size = 4 × 8 × 8 = 256
```

---

## 4. 使用示例

```python
import deepspeed

# 初始化 DeepSpeed 引擎
model_engine, optimizer, _, _ = deepspeed.initialize(
    model=model,
    model_parameters=model.parameters(),
    config_params='ds_config.json'
)

# 训练循环
for batch in dataloader:
    loss = model_engine(batch)        # 前向 (自动混合精度)
    model_engine.backward(loss)       # 反向 (自动梯度累积)
    model_engine.step()               # 参数更新 (自动 ZeRO 通信)
```

---

## 5. 通信优化

### Overlap Comm（通信-计算重叠）

`"overlap_comm": true` → 在进行当前 micro-batch 计算的同时，异步传输上一个 micro-batch 的梯度。相当于把通信时间"藏"在了计算时间里。

### Reduce Bucket Size

`"reduce_bucket_size": 5e8` → 梯度不要一个一个传（频繁小通信效率低），累积到约 500MB 再批量传输（降低通信次数）。

### Contiguous Gradients

`"contiguous_gradients": true` → 将梯度在内存中连续排列，减少 GPU→CPU 传输时的内存碎片化。

---

## 6. 硬件配置建议

| 模型规模 | GPU | DeepSpeed 配置 | 训练时间估算 |
|----------|-----|---------------|------------|
| 7B | 2×A100 80G | ZeRO-2 | ~200 GPU hours (1T tokens) |
| 13B | 4×A100 80G | ZeRO-2 + CPU offload | ~500 GPU hours |
| 70B | 8×A100/H100 80G | ZeRO-3 | ~5000 GPU hours |
| 405B | 64×H100 80G | TP+PP+ZeRO-3 | ~30000 GPU hours |
