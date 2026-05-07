# 01 · 用户入口：`LLM` 类

**源码**：[`code/vllm/vllm/entrypoints/llm.py`](../../code/vllm/vllm/entrypoints/llm.py)

## 这个类做什么

`LLM` 是离线推理的用户入口类。你的代码 `llm = LLM(model="...")` 创建的就是它。

## 构造函数

```python
class LLM:
    def __init__(self, model, tokenizer=None, tensor_parallel_size=1,
                 dtype="auto", max_model_len=None, ...):
```

构造函数接收用户参数，内部做三件事：
1. 把参数组装成 `EngineArgs` 对象
2. `EngineArgs.create_engine_config()` → `VllmConfig`
3. 创建 `LLMEngine` 实例（存入 `self.llm_engine`）

## 三个对外方法

### `generate(prompts, sampling_params)`

主方法。流程：

```
1. tokenizer.encode() 把 prompt 字符串 → token IDs
2. 逐个调 _add_request(request_id, prompt_token_ids, sampling_params)
3. _run_engine() 循环直到所有请求完成
4. 返回 list[RequestOutput]，按 request_id 排序
```

### `encode(queries, pooling_params)`

与 `generate()` 并行的方法，用于 embedding/pooling 任务。结构和 `generate` 类似但返回 `PoolingRequestOutput`。

### `chat(messages, sampling_params)`

对 `generate()` 的薄封装，先把 messages（OpenAI 格式）通过 tokenizer 的 chat template 转成 prompt 字符串。

## 核心循环：`_run_engine()`

```python
def _run_engine(self):
    outputs_by_req = {}
    while unfinished:
        step_outputs = self.llm_engine.step()  # 驱动一步
        for output in step_outputs:
            outputs_by_req[output.request_id] = output
            if output.finished:
                unfinished.remove(output.request_id)
    return sorted(outputs_by_req.values())
```

每调一次 `step()`，引擎完成一个调度-执行周期。所有未完成的请求一起推进，直到最后一个完成。

## 阅读重点

- 构造函数：看参数怎么变成 `EngineArgs`
- `generate()`：看 prompt → tokenize → add_request 的流程
- `_run_engine()`：看 step 循环的终止条件
- 跳过 `chat()`（只是 `generate()` 的封装）
