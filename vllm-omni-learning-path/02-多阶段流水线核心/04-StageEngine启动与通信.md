# 04 · Stage Engine 启动与通信

**源码**：
- [`code/vllm-omni/vllm_omni/engine/stage_engine_startup.py`](../../code/vllm-omni/vllm_omni/engine/stage_engine_startup.py)
- [`code/vllm-omni/vllm_omni/engine/stage_engine_core_proc.py`](../../code/vllm-omni/vllm_omni/engine/stage_engine_core_proc.py)
- [`code/vllm-omni/vllm_omni/engine/stage_engine_core_client.py`](../../code/vllm-omni/vllm_omni/engine/stage_engine_core_client.py)

## Stage 的启动流程

每个 Stage 都是一个**独立进程**，有自己的 GPU 上下文、vLLM EngineCore、模型参数。启动过程如下：

```mermaid
flowchart TD
  n0["Orchestrator 初始化"]
  n1["读取 PipelineRegistry → 知道有几个 Stage"]
  n2["对每个 Stage："]
  n3["构建 Stage 的 VLLM Config（OmniModelConfig → VLLM Config）"]
  n4["创建 StageEngineCoreProc（子进程）"]
  n5["启动独立进程"]
  n6["初始化 CUDA 上下文"]
  n7["加载模型权重"]
  n8["创建 EngineCore（vLLM 的后端引擎）"]
  n9["进入推理循环"]
  n10["创建 StageEngineCoreClient（通信客户端）"]
  n11["将 Client 包装成 StagePool"]
  n12["所有 Stage 就绪 → 开始接收请求"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
  n5 --> n6
  n6 --> n7
  n7 --> n8
  n8 --> n9
  n9 --> n10
  n10 --> n11
  n11 --> n12
```

## 三个关键类

### `StageEngineCoreProc` —— Stage 进程

运行在**子进程**中，是真正的推理执行者：

```python
class StageEngineCoreProc:
    """
    子进程入口：
    1. 初始化 vLLM EngineCore
    2. 加载模型权重
    3. 进入 step() 循环
    4. 通过 IPC 与 Client 通信
    """
```

### `StageEngineCoreClient` —— Stage 客户端

运行在**主进程**中（Orchestrator 线程），是 Stage 的"遥控器"：

```python
class StageEngineCoreClient:
    """
    主进程侧：
    1. 通过 IPC 向子进程发送请求
    2. 接收子进程的输出
    3. 实现 process_engine_inputs()（Stage 间数据转换）
    """
```

### `StageEngineStartup` —— Stage 启动器

负责"创建 Proc + Client 对"，以及配置初始化：

```python
class StageEngineStartup:
    """
    为每个 Stage：
    1. 创建 OmniModelConfig
    2. 创建 StageEngineCoreProc（子进程）
    3. 创建 StageEngineCoreClient（客户端）
    4. 返回 (client, proc) 对
    """
```

## IPC（进程间通信）

主进程（Orchestrator）和子进程（Stage Engine）之间的通信方式：

```mermaid
flowchart TD
  n0["主进程（Orchestrator）                   子进程（Stage Engine）"]
  n1["submit(request) ────────────────────▶│  接收请求"]
  n2["EngineCore.step()"]
  n3["模型 forward"]
  n4["◀──────────── output ────────────────┤  输出结果"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
```

具体的 IPC 实现取决于配置：
- **同机**：使用 `multiprocessing` 队列或共享内存
- **跨机**：使用 Mooncake Transfer Engine、Yuanrong 等分布式连接器

## `process_engine_inputs` —— Stage 间数据转换的关键

每个 Stage 的 Client 上有一个 `process_engine_inputs` 方法，它负责把上一 Stage 的**原始输出**转为当前 Stage 的**输入格式**：

```python
def process_engine_inputs(self, source_outputs, original_prompt, streaming_context):
    """
    source_outputs: 上一 Stage 的输出列表
    original_prompt: 用户最初输入的 prompt
    streaming_context: 流式状态

    返回：当前 Stage 的输入列表（可以是多个，如 CFG 双路径）
    """
```

这个方法的实现通常在各个模型的 `stage_input_processor` 文件中。例如：
- Qwen Omni 的 Thinker→Talker 转换：[`stage_input_processors/qwen2_5_omni.py`](../../code/vllm-omni/vllm_omni/model_executor/stage_input_processors/qwen2_5_omni.py)
- CosyVoice 的 AR→DiT 转换：[`stage_input_processors/cosyvoice3.py`](../../code/vllm-omni/vllm_omni/model_executor/stage_input_processors/cosyvoice3.py)

## 阅读时间

约 25 分钟。重点理解 Proc/Client 的配对设计（前后端分离在 Stage 级别的应用）和 `process_engine_inputs` 的作用。
