# 04 · IPC 抽象层：`EngineCoreClient`

**源码**：[`code/vllm/vllm/v1/engine/core_client.py`](../../code/vllm/vllm/v1/engine/core_client.py)

## 为什么需要这一层

前端（`LLMEngine`）和后端（`EngineCore`）可以在同一个进程内，也可以在不同的进程甚至不同的机器上。`EngineCoreClient` 抽象了这个差异，让前端不需要关心后端在哪里。

## 五个实现

| 子类 | 部署模式 | 通信方式 |
|------|---------|---------|
| `InprocClient` | 单进程离线推理 | 直接函数调用 |
| `SyncMPClient` | 多进程离线推理 | ZMQ 同步通信 |
| `AsyncMPClient` | 在线服务 | ZMQ + asyncio 异步通信 |
| `DPAsyncMPClient` | 数据并行 | 多个 EngineCore 实例 |
| `DPLBAsyncMPClient` | 数据并行 + 外部负载均衡 | 带负载均衡逻辑 |

## 工厂方法

```python
@staticmethod
def make_client(multiproc_mode, asyncio_mode, ...):
    if multiproc_mode and asyncio_mode:
        return AsyncMPClient(...)
    elif multiproc_mode:
        return SyncMPClient(...)
    elif data_parallel_mode:
        return DPAsyncMPClient(...)
    else:
        return InprocClient(...)
```

## 抽象接口

```python
class EngineCoreClient(ABC):
    def add_request(self, request: EngineCoreRequest) -> None: ...
    def abort_requests(self, request_ids: list[str]) -> None: ...
    def get_output(self) -> dict[int, EngineCoreOutputs]: ...
    def shutdown(self) -> None: ...
```

## 阅读重点

- 知道存在这些子类，理解它们的选择逻辑
- 第一遍不需要读各子类的实现
- 记住 `InprocClient` 最简单（直接调 `EngineCore.step()`），适合离线推理
- `AsyncMPClient` 最常用（生产环境的 API 服务器）
