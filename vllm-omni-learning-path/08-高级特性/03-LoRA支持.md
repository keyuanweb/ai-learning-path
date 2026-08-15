# 03 · LoRA 支持：AR 与 Diffusion 的低秩适配

**源码**：
- [`code/vllm-omni/vllm_omni/lora/`](../../code/vllm-omni/vllm_omni/lora/)
- [`code/vllm-omni/vllm_omni/config/lora.py`](../../code/vllm-omni/vllm_omni/config/lora.py)
- [`code/vllm-omni/vllm_omni/diffusion/lora/`](../../code/vllm-omni/vllm_omni/diffusion/lora/)

## LoRA 是什么

LoRA（Low-Rank Adaptation）是一种参数高效微调方法。它不修改原模型权重，而是在旁边加一个小的"适配器矩阵"（低秩分解）。推理时：

```
output = W·x + (B·A)·x
        原权重     LoRA 增量
```

好处：一个基础模型可以挂多个 LoRA（不同风格、不同任务），显存开销很小。

## vLLM-Omni 的 LoRA 支持

vLLM-Omni 在**两类模型**上都支持 LoRA：

| 模型类型 | LoRA 位置 | 源码 |
|---------|----------|------|
| **AR 模型** | vLLM 原生 LoRA + Punica 内核 | `vllm_omni/lora/` |
| **扩散模型** | DiT 的 Linear 层 | `vllm_omni/diffusion/lora/` |

## AR 模型的 LoRA

vLLM-Omni 直接复用 vLLM 的 LoRA 系统（基于 Punica 内核），并做了扩展：

### `lora/request.py`

```python
class LoRARequest:
    lora_name: str       # LoRA 名称
    lora_path: str       # LoRA 权重路径
    lora_int_id: int     # LoRA 的内部 ID
```

### `config/lora.py`

```python
class LoRAConfig:
    max_loras: int            # 最多同时加载多少个 LoRA
    max_lora_rank: int        # 最大 LoRA rank
    target_modules: list[str] # 限制 LoRA 应用到哪些模块后缀
    fully_sharded_loras: bool # 是否跨 GPU 分片 LoRA
```

## 扩散模型的 LoRA

[`diffusion/lora/`](../../code/vllm-omni/vllm_omni/diffusion/lora/) 为 DiT 模型提供了 LoRA 支持：

### Layer 实现

扩散 LoRA 的关键是支持不同的并行模式下的 LoRA 层：

| 文件 | 并行模式 | 说明 |
|------|---------|------|
| `layers/base_linear.py` | 无并行 | 基础 LoRA Linear |
| `layers/replicated_linear.py` | 数据并行 | 每 GPU 有完整 LoRA |
| `layers/column_parallel_linear.py` | 列并行 | LoRA 按列分片 |
| `layers/row_parallel_linear.py` | 行并行 | LoRA 按行分片 |

### LoRA Manager

[`manager.py`](../../code/vllm-omni/vllm_omni/diffusion/lora/manager.py) 管理扩散模型的 LoRA 生命周期：

```python
class DiffusionLoRAManager:
    def add_adapter(self, lora_request):
        # 注册并加载 LoRA 适配器

    def set_active_adapter(self, lora_request, lora_scale=1.0):
        # 激活特定 LoRA（切换 LoRA 时用）

    def remove_adapter(self, adapter_id):
        # 移除 LoRA 适配器
```

### LoRA Utils

[`utils.py`](../../code/vllm-omni/vllm_omni/diffusion/lora/utils.py) 提供了 LoRA 相关的工具函数（如 target modules 匹配、packed layers 模块展开）。

## LoRA 的使用示例

```python
# 加载带 LoRA 的模型
omni = Omni(
    model="Qwen/Qwen2.5-Omni-7B",
    enable_lora=True,
    max_loras=4,
    max_lora_rank=64,
)

# 在请求中指定使用哪个 LoRA
output = omni.generate(
    prompts=["你好"],
    sampling_params=SamplingParams(
        lora_request=LoRARequest(
            lora_name="my_fine_tuned_style",
            lora_path="/path/to/lora",
        )
    ),
)
```

## 阅读时间

约 20 分钟。如果你不关注 LoRA/微调，可以跳过。扩散模型的 LoRA 实现（并行感知的层设计）是技术亮点。
