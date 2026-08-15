# 04 · 扩散 Worker 与 Model Runner

**源码**：
- [`code/vllm-omni/vllm_omni/diffusion/worker/diffusion_worker.py`](../../code/vllm-omni/vllm_omni/diffusion/worker/diffusion_worker.py)
- [`code/vllm-omni/vllm_omni/diffusion/worker/diffusion_model_runner.py`](../../code/vllm-omni/vllm_omni/diffusion/worker/diffusion_model_runner.py)
- [`code/vllm-omni/vllm_omni/diffusion/worker/input_batch.py`](../../code/vllm-omni/vllm_omni/diffusion/worker/input_batch.py)
- [`code/vllm-omni/vllm_omni/diffusion/worker/utils.py`](../../code/vllm-omni/vllm_omni/diffusion/worker/utils.py)

## DiffusionWorker —— 扩散模型的 GPU 执行者

```python
class DiffusionWorker:
    """
    在 GPU 上执行扩散模型的一次去噪 step：
    1. 接收 batch（多个请求，同一去噪步）
    2. 准备输入 tensor
    3. 调用模型 forward
    4. 调用 pipeline.step_scheduler() 更新 latent
    5. 返回更新后的 latent
    """
```

### 执行流程

```python
def execute_stepwise(self, scheduler_output: DiffusionSchedulerOutput) -> BaseRunnerOutput:
    # 委托给 DiffusionModelRunner 执行一次去噪 step：
    # 1. 准备输入：构造 InputBatch（latent、timestep、条件）
    # 2. 模型前向（预测噪声）：pipeline.denoise_step(input_batch)
    # 3. Scheduler 更新：pipeline.step_scheduler(req, noise_pred)
    # 4. 更新请求状态：step_index 前进，完成的请求做 post_decode
    return self.model_runner.execute_stepwise(scheduler_output)
```

## DiffusionModelRunner —— 管理模型前向

```python
class DiffusionModelRunner:
    """
    封装模型前向调用：
    - 构造 InputBatch
    - 调用 DiT Transformer.forward()
    - 处理 CFG（条件/无条件双路径）
    - 处理跨 Stage 的 KV cache 接收
    """

    def execute_model(self, req: OmniDiffusionRequest) -> DiffusionOutput:
        # 调用 pipeline 的 forward 执行完整扩散生成
        return self.pipeline.forward(req)
```

### InputBatch —— 批量输入管理

[`input_batch.py`](../../code/vllm-omni/vllm_omni/diffusion/worker/input_batch.py) 负责将多个请求的数据组装为 batch：

```python
class InputBatch:
    """
    管理一个 batch 的扩散请求：
    - latent 拼接：多个请求的 latent 拼成 (B,C,H,W)
    - timestep 对齐：同一个 batch 中所有请求在相同步数
    - CFG 双路径：条件+无条件的 latent 交替排列
    """
```

## CFG（Classifier-Free Guidance）的实现

CFG 需要同时计算条件路径和无条件路径：

```python
# 条件路径：带 prompt embedding 的 forward
latent_cond = [l1_c, l2_c, ...]      # B 个条件 latent

# 无条件路径：空 prompt embedding 的 forward
latent_uncond = [l1_u, l2_u, ...]    # B 个无条件 latent

# 拼接为一个 batch
latent_batch = [l1_c, l1_u, l2_c, l2_u, ...]  # 2B 个 latent

# 一次 forward 同时算两条路径
noise_pred = model(latent_batch, ...)
# noise_pred 的前半是条件预测，后半是无条件预测

# 混合
noise_pred_final = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)
```

在跨 Stage 场景中，CFG 的两条路径作为**两个独立的 companion request** 提交给扩散引擎：

```python
# Orchestrator._handle_add_companion()
companion_prompt = empty_condition_prompt
companion_replica_id = await stage_pool.submit_initial(
    companion_id, companion_state, companion_prompt, affinity_request_id=parent_id
)
```

## 扩散模型的编译优化

[`diffusion/compile.py`](../../code/vllm-omni/vllm_omni/diffusion/compile.py) 使用 `torch.compile` 来加速 DiT 模型：

```python
# 对 DiT Transformer 的重复 block 做区域编译（regionally_compile）
compiled_model = regionally_compile(model, dynamic=True)
```

因为扩散模型要跑 N 步（N 通常为 20-50），每步的 forward 图相同，所以 `torch.compile` 的加速效果显著。

## 扩散 Offloader —— 显存优化

[`diffusion/offloader/`](../../code/vllm-omni/vllm_omni/diffusion/offloader/) 实现了模型层的 CPU offloading：

- `ModelLevelOffloadBackend`：模型级加载/卸载（encoder 与 DiT 互斥，简单但慢）
- `LayerWiseOffloadBackend`：按层加载/卸载（更精细的显存控制）

当 GPU 显存不够时，可以将部分层放到 CPU 内存，用到时再加载回来。

## 阅读时间

约 25 分钟。重点理解 DiffusionWorker 的 step 循环和 CFG 双路径的 batch 处理方式。
