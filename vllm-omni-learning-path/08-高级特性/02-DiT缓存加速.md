# 02 · DiT 缓存加速：TeaCache 与 CacheDiT

**源码**：[`code/vllm-omni/vllm_omni/diffusion/cache/`](../../code/vllm-omni/vllm_omni/diffusion/cache/)

## 扩散模型为什么需要缓存加速

扩散模型要去噪 N 步（通常 20-50 步），每步都要跑一次完整的 DiT forward。但实际上，许多**相邻步的中间计算结果非常相似**——模型在前几步和后几步的变化比较剧烈，但在中间的大部分步数中，变化很慢。

如果能跳过那些"变化很小"的步的某些计算，就能大幅加速。

## TeaCache —— 茶缓存

[`teacache/`](../../code/vllm-omni/vllm_omni/diffusion/cache/teacache/)

TeaCache 是 vLLM-Omni 实现的 DiT 缓存加速方案。核心思想是：

```
去噪步 t:    计算完整 DiT forward → 缓存某些层的输出
去噪步 t-1:  检查：输出变化大吗？
            ├─ 变化大 → 完整计算
            └─ 变化小 → 复用缓存的输出（跳过大部分层的计算）
去噪步 t-2:  ...
```

### TeaCache 的文件组织

| 文件 | 功能 |
|------|------|
| `backend.py` | TeaCache 后端：管理缓存读写 |
| `config.py` | TeaCache 配置：哪些层缓存、阈值多少 |
| `extractors.py` | 特征提取器：从模型输出中提取"是否变化大"的信号 |
| `hook.py` | PyTorch hooks：拦截模型前向，注入缓存逻辑 |
| `state.py` | 缓存状态管理 |
| `coefficient_estimator.py` | 系数估计器：估计缓存命中率 |

### TeaCache 配置

```python
class TeaCacheConfig:
    layers_to_cache: list[str]   # 哪些层要缓存
    cache_threshold: float       # 变化阈值（越小越精确，越大越快速）
    start_step: int              # 从第几步开始缓存
    end_step: int                # 到第几步结束缓存
```

### 工作原理

```python
# hook.py 中的简化逻辑
def teacache_hook(module, input, output):
    current_step = get_current_timestep()

    if current_step not in cache:
        # 首次遇到这个 timestep，缓存
        cache[current_step] = output
        return output

    cached = cache[current_step]
    diff = compute_difference(output, cached)

    if diff < threshold:
        # 变化很小，复用缓存
        return cached
    else:
        # 变化大，更新缓存
        cache[current_step] = output
        return output
```

## CacheDiT —— 另一种缓存方案

[`cache_dit_backend.py`](../../code/vllm-omni/vllm_omni/diffusion/cache/cache_dit_backend.py)

CacheDiT 是另一种 DiT 缓存加速方案，与 TeaCache 互补：

```python
class CacheDiTBackend:
    """
    CacheDiT 的不同：
    - TeaCache：在 layer 级别缓存
    - CacheDiT：在 token/sequence 级别缓存
    - 缓存 attention 中的 K、V 值
    """
```

## 缓存选择器

[`selector.py`](../../code/vllm-omni/vllm_omni/diffusion/cache/selector.py) 决定用哪种缓存方案：

```python
def select_cache_backend(model_name):
    if model_name in TEA_CACHE_SUPPORTED:
        return TeaCacheBackend()
    elif model_name in CACHE_DIT_SUPPORTED:
        return CacheDiTBackend()
    else:
        return None  # 不支持缓存
```

## 哪些模型不支持缓存

有些模型的扩散过程对每一步的结果都高度敏感，缓存会导致明显的质量下降。这些模型在[注册表中被标注为 `_NO_CACHE_ACCELERATION`](../../code/vllm-omni/vllm_omni/diffusion/registry.py)：

```python
_NO_CACHE_ACCELERATION = {
    "NextStep11Pipeline",  # 步数很少（1-4步），无需缓存
    "AudioXPipeline",      # 音频对每一步都很敏感
}
```

## 阅读时间

约 20 分钟。TeaCache 是扩散加速的关键优化，理解"缓存中间层输出、比较差异、复用"的核心思想即可。
