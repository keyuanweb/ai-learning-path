# 04 · IPC 抽象层：`EngineCoreClient`

**源码**：[`code/vllm/vllm/v1/engine/core_client.py`](../../code/vllm/vllm/v1/engine/core_client.py)

## 为什么需要这一层

前端（`LLMEngine`）和后端（`EngineCore`）可以在同一个进程内，也可以在不同的进程甚至不同的机器上。`EngineCoreClient` 抽象了这个差异，让前端不需要关心后端在哪里。

## 五个实现

| 子类 | 部署模式 | 通信方式 | 典型场景 |
|------|---------|---------|---------|
| `InprocClient` | 单进程 | 直接函数调用 `engine_core.step()` | `LLM.generate()` 离线推理 |
| `SyncMPClient` | 多进程 + 共享内存 | ZMQ 同步 REQ/REP + msgpack | 多 GPU TP 离线推理 |
| `AsyncMPClient` | 多进程 + asyncio | ZMQ 异步 + asyncio event loop | 生产 API 服务器（OpenAI 兼容服务） |
| `DPAsyncMPClient` | 数据并行 | 多个 EngineCoreProc 实例，轮询/最少负载路由请求 | DP > 1 的在线服务 |
| `DPLBAsyncMPClient` | 数据并行 + 外部负载均衡 | 带外部负载均衡器协同的 DP 客户端 | 大规模生产部署（K8s + 外部 LB） |

## 工厂方法

```python
@staticmethod
def make_client(multiproc_mode: bool, asyncio_mode: bool,
                data_parallel_mode: bool, ...):
    if data_parallel_mode and asyncio_mode:
        return DPLBAsyncMPClient(...)      # 生产 DP
    elif multiproc_mode and asyncio_mode:
        return AsyncMPClient(...)           # 生产单引擎
    elif multiproc_mode:
        return SyncMPClient(...)            # 多 GPU 离线
    else:
        return InprocClient(...)            # 单 GPU 离线
```

## 抽象接口

```python
class EngineCoreClient(ABC):
    @abstractmethod
    def add_request(self, request: EngineCoreRequest) -> None: ...

    @abstractmethod
    def abort_requests(self, request_ids: list[str]) -> None: ...

    @abstractmethod
    def get_output(self) -> EngineCoreOutputs: ...

    @abstractmethod
    def profile(self, is_start: bool = True) -> None: ...

    @abstractmethod
    def shutdown(self) -> None: ...
```

## 各实现的内部要点

### InprocClient（最简单）
- 构造函数中直接创建 `EngineCore` 对象（非 `EngineCoreProc`）
- `get_output()` 直接 `return self.engine_core.step()` ——同步紧循环
- 没有任何 IPC 开销，适合单卡调试和离线推理

### SyncMPClient / AsyncMPClient
- 创建并管理 `EngineCoreProc` 子进程
- 通过 ZMQ socket 管道发送 EngineCoreRequest / 接收 EngineCoreOutputs
- `send_fn()` 和 `recv_fn()` 使用 `MsgpackEncoder/Decoder` 序列化
- 大 tensor 通过共享内存传递（零拷贝），不在 ZMQ 管道中传输
- AsyncMPClient 增加 asyncio event loop 和协程支持

### DPAsyncMPClient / DPLBAsyncMPClient
- 管理多个 EngineCoreProc 实例（每个 GPU 一个）
- 维护每个 engine 的负载队列（inflight request 计数）
- 新增请求路由到负载最低的 engine
- DPLBAsyncMPClient 额外支持外部负载均衡器的状态协作

## 阅读重点

- 知道存在这五种子类，理解它们的选择逻辑
- 记住 `InprocClient` 最简单（直接函数调用），适合离线推理
- `AsyncMPClient` 最常用（生产环境的 API 服务器）
- 大 tensor 通过共享内存零拷贝传递——这是 V1 性能优化的核心之一
- 第一遍不需要读各子类的实现细节
