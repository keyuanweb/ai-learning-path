# 01 · 用户入口：`LLM` 类

**源码**：[`code/vllm/vllm/entrypoints/llm.py`](../../code/vllm/vllm/entrypoints/llm.py)

## 这个类做什么

`LLM` 是离线推理的用户入口类。你的代码 `llm = LLM(model="...")` 创建的就是它。它封装了 tokenizer、引擎、输入处理和输出处理——用户只需要传 prompt 和 sampling_params。

## 构造函数

```python
class LLM:
    def __init__(self, model, tokenizer=None, tensor_parallel_size=1,
                 dtype="auto", max_model_len=None, ...):
```

内部做三件事：
1. 把参数组装成 `EngineArgs` 对象
2. `EngineArgs.create_engine_config()` → `VllmConfig`（聚合所有子配置）
3. `LLMEngine.from_engine_args(engine_args)` 创建引擎实例（存入 `self.llm_engine`）

同时创建 tokenizer（从 HuggingFace 加载或使用传入的），并通过 InputProcessor / OutputProcessor 建立输入输出处理链。

## 四个对外方法

### `generate(prompts, sampling_params)` — 主方法

流程：

```
1. 规范化输入 → list[PromptType]（str / TextPrompt / TokensPrompt / EmbedsPrompt）
2. tokenizer.encode() 把 prompt 字符串 → token IDs（或直接使用传入的 token_ids）
3. 逐个调 self._add_request(request_id, prompt_token_ids, sampling_params)
4. self._run_engine() 循环直到所有请求完成
5. 返回 list[RequestOutput]，按 request_id 排序
```

`_add_request()` 内部：`self.llm_engine.add_request(request_id, prompt, sampling_params)`。

### `encode(queries, pooling_params)` — embedding/pooling

与 `generate()` 并行的方法。结构和 `generate()` 类似，但：
- 使用 `PoolingParams` 而非 `SamplingParams`
- 返回 `PoolingRequestOutput`（含 embeddings）
- 内部引擎通过检查 `pooling_params is not None` 区分生成和 pooling 请求

### `chat(messages, sampling_params)` — OpenAI 格式对话

对 `generate()` 的薄封装：先把 messages（`[{"role": "user", "content": "你好"}]` 格式）通过 tokenizer 的 `apply_chat_template()` 转成 prompt 字符串，再调用 `generate()`。

### `collective_rpc(method, *args, **kwargs)` — 分布式调用

在分布式部署中，在所有 worker 上执行同一方法。离线推理通常不需要。

## 核心循环：`_run_engine()`

```python
def _run_engine(self):
    outputs_by_req: dict[str, RequestOutput] = {}
    unfinished = set(all_request_ids)
    while unfinished:
        # 驱动引擎一步：调度 → 执行 → 采样 → 输出
        step_outputs = self.llm_engine.step()
        for output in step_outputs:
            outputs_by_req[output.request_id] = output
            if output.finished:
                unfinished.remove(output.request_id)
    # 按 request_id 排序返回（保证确定性）
    return [outputs_by_req[rid] for rid in sorted_keys]
```

每调一次 `step()`，引擎完成一个完整的调度-执行-采样周期。所有未完成的请求一起推进。关键：`step()` 返回的 `step_outputs` 可能包含多个请求——不是每步只处理一个。

## LLM.generate() 完整调用链

```
LLM.generate(["你好"])
  → LLM._add_request()          # 把 prompt tokenize 后发给引擎
  → LLM._run_engine()           # 循环驱动
    → LLMEngine.step()          # 一步推进
      → EngineCoreClient.get_output()  # 从后端拿结果
      → OutputProcessor.process_outputs()  # 后处理（detokenize 等）
    → 返回 RequestOutput
```

## 阅读重点

- 构造函数：看参数怎么变成 `EngineArgs` → `VllmConfig` → `LLMEngine`
- `generate()`：看 prompt → tokenize → add_request → _run_engine 的完整流程
- `_run_engine()`：理解 step 循环只在一个 thread 中推进所有请求
- 跳过 `chat()`（只是 `generate()` 的薄封装）
- 跳过 `collective_rpc()`（分布式细节）
