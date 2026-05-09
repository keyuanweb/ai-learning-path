# vLLM 与 PagedAttention

vLLM 是目前最主流的高吞吐大模型推理引擎。它的核心贡献 PagedAttention 类比了操作系统中的虚拟内存管理。

---

## 1. 传统推理引擎的 KV Cache 浪费

### 问题

标准实现中，每个请求预分配一段固定大小的连续内存来存储 KV Cache（按照 max_seq_len）。两个浪费：
1. **内部碎片**：实际序列长度 < max_seq_len → 预分配的显存白费
2. **外部碎片**：多个请求的分配/释放导致显存碎片化

对于批量服务（同时处理数百请求），总 KV Cache 利用率可能低至 20-30%。

### PagedAttention 的解决方案

> 将 KV Cache 切分成固定大小的"页"（page），像操作系统的虚拟内存一样按需分配。

```
传统: 每个请求 = 一大块连续内存 (max_len)
PagedAttention: 每个请求 = 多个不连续的小页 (page_size, 比如 16 tokens)

请求 A: [页0] [页1] [页2] → 只需要 48 个 token 的 KV
请求 B: [页4] [页7] → 只需要 32 个 token 的 KV
请求 C: [页3] [页5] [页6] [页8] → 需要 64 个 token 的 KV

空闲: [页9] [页10] ... 可以被新请求使用
```

**这消除了内部碎片**（请求用多少分配多少）和**显著减少外部碎片**（所有请求用统一大小的页，无奇数大小空隙）。

---

## 2. Continuous Batching（连续批处理）

### 传统 Static Batching 的问题

```
批次1: [请求A(短), 请求B(长), 请求C(短)]
        → 必须等 B 也完成才能返回结果给 A 和 C
        → A 和 C 的算力在白白等待
```

### Continuous Batching 的做法

请求生成完 EOS 后立即退出批次，新请求随时可以加入：

```
时刻1: Batch [A, B, C, D]  开始
时刻2: A 完成了 → Batch [B, C, D]  (A 的结果立即返回)
时刻3: E 到达 → Batch [B, C, D, E] (新请求无缝加入)
时刻4: C 完成了 → Batch [B, D, E]
...
```

**解决了什么问题**：高并发场景下 GPU 算力利用率从 ~50% 提升到 ~90%+。

---

## 3. KV Cache 共享：Prefix Caching

### 问题

多个请求共享相同的 system prompt：

```
请求1: "<system>你是翻译助手...</system> 翻译 'hello'"
请求2: "<system>你是翻译助手...</system> 翻译 'world'"
请求3: "<system>你是翻译助手...</system> 翻译 'goodbye'"
```

传统做法每个请求重新计算一次 system prompt 的 KV Cache。完全相同的内容，计算了三次。

### Prefix Caching 的做法

```python
# 检测到相同 prefix → 共享 KV Cache
cache_key = hash(prompt_tokens[:prefix_len])
if cache_key in prefix_cache:
    kv_cache[prefix_len] = prefix_cache[cache_key]  # 直接复用
else:
    kv_cache[prefix_len] = compute_kv(prompt_tokens[:prefix_len])
    prefix_cache[cache_key] = kv_cache[prefix_len]
```

**节省**：如果有 50% 的请求共享相同的 system prompt，prefill 阶段的延迟直接减半。

---

## 4. vLLM 的使用

```bash
pip install vllm
```

```python
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-3-8B", dtype="bfloat16")

prompts = ["法国的首都是哪里？", "写一首关于春天的诗", "解释一下黑洞"]
sampling_params = SamplingParams(temperature=0.8, top_p=0.95, max_tokens=256)

outputs = llm.generate(prompts, sampling_params)
for output in outputs:
    print(output.outputs[0].text)
```

### 服务化 (OpenAI 兼容 API)

```bash
vllm serve meta-llama/Llama-3-8B --dtype bfloat16 --max-model-len 4096
```

这会启动一个与 OpenAI API 兼容的 HTTP 服务：

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
response = client.chat.completions.create(
    model="meta-llama/Llama-3-8B",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

---

## 5. vLLM vs 其他推理引擎

| 引擎 | 核心优化 | 适用场景 |
|------|---------|---------|
| **vLLM** | PagedAttention + Continuous Batching | 高吞吐在线服务 |
| **TGI** (HuggingFace) | 类似 vLLM，生态更好 | 与 HF 生态集成 |
| **SGLang** | RadixAttention + 结构化生成 | 复杂 prompt 场景 |
| **TensorRT-LLM** | NVIDIA 编译优化（极致性能） | 追求最高吞吐 |
| **llama.cpp** | CPU 推理 + 量化 | 本地/边缘设备 |
