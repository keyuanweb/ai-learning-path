# LoRA 原理与实践

LoRA (Low-Rank Adaptation) 解决了大模型微调的核心矛盾：**全参数微调效果好但太贵（175B 模型需要 700GB+ 显存），而 freeze 大部分参数微调效果差。**

---

## 1. 问题的根源

### 全参数微调为什么贵

对 7B 模型做全参数微调：
- 模型参数：14 GB (FP16)
- 梯度：14 GB
- 优化器状态 (AdamW)：42 GB (FP32 的三份)
- 激活值：~20 GB
- **总计：~90 GB** → 需要 2×A100 或 1×H100

如果是 70B 模型：~900 GB → 需要 12 张 A100。对大多数团队和个人开发者来说，这不现实。

### LoRA 的核心洞察

> 模型微调时，权重变化矩阵 $\Delta W$ 是**低秩的**——虽然权重矩阵本身是高维的（如 4096 × 4096），但微调带来的变化可以用两个小矩阵的乘积来近似。

---

## 2. LoRA 的数学原理

### 操作

对于一个预训练权重矩阵 $W \in \mathbb{R}^{d \times k}$，不直接更新 $W$，而是学一个低秩分解：

$$W_{\text{fine-tuned}} = W_{\text{pretrained}} + \frac{\alpha}{r} \cdot BA$$

其中：
- $B \in \mathbb{R}^{d \times r}$，$A \in \mathbb{R}^{r \times k}$
- $r \ll \min(d, k)$（通常 r=8 或 16）
- $\alpha$ 是缩放因子（通常 $\alpha = 2r$）

### 为什么低秩够用

预训练已经让模型学到了通用的语言能力（语法、常识、知识）。微调只需要在这些能力的基础上做小幅调整——将模型"引导"到特定行为模式（如助手风格）。这种"方向性调整"的信息量远小于原始权重矩阵的秩，因此低秩分解就足够表达了。

### 参数效率

对于 Attention 的 $W_Q$ (4096 × 4096)：
- 全参数更新：16.8M 参数
- LoRA (r=8)：$B$ (4096×8) + $A$ (8×4096) = 65K 参数 → **仅为原来的 0.4%**

---

## 3. LoRA 应该加在哪些层

### 标准做法：所有 Attention 的 Q 和 V

```python
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],  # 只对 Q 和 V 加 LoRA
    lora_dropout=0.1,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(base_model, lora_config)
model.print_trainable_parameters()
# 输出: trainable params: 4.2M || all params: 7004.2M || trainable%: 0.06%
```

### 为什么不加所有层

| 策略 | 可训练参数 | 效果 | 推荐 |
|------|-----------|------|------|
| 只 Q+V | ~0.06% | 足够好 | 默认选择 |
| Q+K+V+O | ~0.12% | 略好 | 任务困难时 |
| Attention + FFN | ~0.5% | 进一步提升 | 数据量大且有足够显存 |
| 所有 Linear | ~1% | 接近全参数微调 | 接近全量效果但依然高效 |

---

## 4. Rank 的选择

### r=8 的魔力

实践中 r=8 几乎总是足够好。更高 rank（64, 128）的收益递减明显：
- r=8 → r=16：提升 ~1-2% 下游指标
- r=16 → r=64：提升 <1%
- r=128+：与全参数微调几乎无差别

### 什么时候用更高的 rank

- **复杂任务**：代码生成、数学推理——需要更精细的调整
- **大领域差异**：从英文模型适配到完全不同的语言/领域
- **充足数据**：有 10 万+ 高质量 SFT 数据时

---

## 5. LoRA 的训练配置

```python
training_args = TrainingArguments(
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,            # LoRA 的学习率比全参数微调高
    warmup_ratio=0.03,
    num_train_epochs=3,
    bf16=True,
    logging_steps=10,
    save_strategy="epoch",
    optim="adamw_8bit",           # 8-bit 优化器进一步省显存
)
```

### LoRA 的学习率为什么可以更高

LoRA 只更新新增的 A 和 B 矩阵（预训练权重被冻结）。这些矩阵是随机初始化的，需要比预训练权重更大的更新步长来收敛。

| 微调方式 | 典型学习率 |
|----------|-----------|
| 全参数微调 | 1e-5 ~ 3e-5 |
| LoRA | 1e-4 ~ 5e-4 |

---

## 6. LoRA 的保存与合并

```python
# 保存 LoRA adapter (只有 4-10 MB!)
model.save_pretrained("my_lora_adapter")

# 加载
from peft import PeftModel
model = PeftModel.from_pretrained(base_model, "my_lora_adapter")

# 合并到基础模型 (推理时省掉 adapter 的计算)
model = model.merge_and_unload()
model.save_pretrained("merged_model")
```
