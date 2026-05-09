# 03 · StagePool 阶段池：副本管理与轮询

**源码**：[`code/vllm-omni/vllm_omni/engine/stage_pool.py`](../../code/vllm-omni/vllm_omni/engine/stage_pool.py)

## StagePool 是什么

`StagePool` 管理**一个逻辑 Stage 的多个副本**。每个副本都是一个独立的推理客户端（`StageEngineCoreClient`），可以跑在不同的 GPU 上。

为什么需要副本？因为一个 Stage 可能成为瓶颈（比如 Thinker 计算量最大），需要多个副本来并行处理不同请求。

```
              StagePool (Stage 0: Thinker)
        ┌──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
    Replica 0     Replica 1     Replica 2     Replica 3
    (GPU 0)       (GPU 1)       (GPU 2)       (GPU 3)
```

## 核心数据结构

```python
class StagePool:
    stage_id: int              # 这个 Pool 属于第几个 Stage
    clients: list              # 副本列表（每个副本一个 StageEngineCoreClient）
    _next_replica_id: int      # 轮询指针（下一个分配哪个副本）
    _request_bindings: dict    # request_id → replica_id（亲和性绑定）
    _output_processor          # 输出处理器（将原始输出转成结构化输出）
```

## 副本选择策略

### 轮询 + 亲和性

```python
def _pick_replica(self, affinity_request_id=None):
    if affinity_request_id and affinity_request_id in self._request_bindings:
        # 亲和性：同一个"父请求"的子请求路由到同一个副本
        return self._request_bindings[affinity_request_id]

    # 轮询选择
    chosen = self._next_replica_id
    self._next_replica_id = (chosen + 1) % len(self.clients)
    return chosen
```

"亲和性"主要用于 CFG（Classifier-Free Guidance）：条件路径和无条件路径的请求需要路由到**同一个副本**，因为它们的 KV Cache 需要共享。

### 绑定管理

```python
# 提交请求时绑定
self._request_bindings[request_id] = replica_id

# 请求完成后释放
def release_bindings(self, request_ids):
    for rid in request_ids:
        self._request_bindings.pop(rid, None)
```

## 提交请求：`submit_initial` 和 `submit_update`

```python
# 第一次提交（新请求）
async def submit_initial(self, request_id, req_state, prompt, ...):
    replica_id = self._pick_replica(affinity_request_id)
    self._request_bindings[request_id] = replica_id
    await self.clients[replica_id].submit(request)  # 发送到对应副本

# 流式更新（后续数据）
async def submit_update(self, request_id, req_state, prompt, ...):
    replica_id = self._request_bindings[request_id]  # 必须用同一个副本
    await self.clients[replica_id].update(request)
```

第一次提交时选择一个副本并绑定；之后的更新必须发到同一个副本。

## 轮询输出

Orchestrator 在 `_orchestration_loop` 中轮询所有 StagePool 的所有副本：

```python
for stage_id in range(self.num_stages):
    pool = self.stage_pools[stage_id]
    for replica_id in range(pool.num_replicas):
        if pool.stage_type == "diffusion":
            output = pool.poll_diffusion_output(replica_id)  # 扩散引擎专用
        else:
            raw_outputs = await pool.poll_llm_raw_output(replica_id)  # AR/Gen 引擎
            raw_output = await pool.process_llm_raw_outputs(replica_id, raw_outputs)
```

### 扩散 Stage 的特殊处理

扩散引擎不使用 vLLM 的 V1 引擎输出模型，它有自己独立的结果获取方式（`poll_diffusion_output`）。

## Stage 级别的属性

```python
@property
def stage_type(self):
    return getattr(self.stage_client, "stage_type", None)
    # "ar" / "generation" / "diffusion"

@property
def final_output(self):
    return bool(getattr(self.clients[0], "final_output", False))
    # True 表示这个 Stage 的输出直接返回用户
```

`final_output` 决定了 Orchestrator 在收到这个 Stage 的输出后，是继续转发还是直接返回用户。

## 指标收集

```python
def build_stage_metrics(self, outputs, submit_ts, replica_id):
    # 计算该 Stage 的延迟、吞吐、token 数等
    metrics = StageRequestMetrics(...)
    return metrics
```

每个副本维护自己的 `_ReplicaMetrics` 累加器。

## 阅读时间

约 20 分钟。StagePool 的逻辑相对简洁，重点理解副本选择（轮询+亲和性）和请求绑定机制。
