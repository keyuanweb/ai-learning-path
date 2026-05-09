# LangSmith 可观测性

## 什么是 LangSmith

LangSmith 是 LangChain 官方的 LLM 应用可观测性平台，提供执行轨迹追踪、性能监控、评估测试和调试工具。

官网：https://smith.langchain.com

## 配置

```python
import os

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls_..."       # 从 smith.langchain.com 获取
os.environ["LANGCHAIN_PROJECT"] = "my-agent-prod" # 项目名，用于组织追踪数据
```

## 核心能力

### 1. 执行轨迹追踪

每次 `graph.invoke()` 自动记录完整的执行轨迹：

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver

graph = builder.compile()
result = graph.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    {"configurable": {"thread_id": "trace-123"}}
)
# 自动在 LangSmith 中生成一条 Trace，包含：
# - 每个节点的输入/输出
# - LLM 调用的 Prompt 和 Response
# - Token 用量（输入/输出/总计）
# - 每个节点的执行耗时
```

### 2. Trace 内容

在 LangSmith UI 中可以看到：

```
Trace: thread_id=trace-123
├── agent_node (1.2s, 450 tokens)
│   ├── Input: [HumanMessage("..."), SystemMessage("...")]
│   ├── LLM Call: gpt-4o-mini (420 tokens in, 30 tokens out)
│   └── Output: AIMessage(tool_calls=[...])
├── tool_node (0.3s)
│   ├── Tool: web_search("query") → "..."
│   └── Output: ToolMessage("...")
└── agent_node (0.8s, 380 tokens)
    ├── LLM Call: gpt-4o-mini (350 tokens in, 30 tokens out)
    └── Output: AIMessage("最终回答...")
```

### 3. 延迟分析

```python
import time
from langsmith import traceable

# 对自定义函数添加追踪
@traceable(run_type="tool")
def my_custom_tool(query: str) -> str:
    """搜索数据库"""
    start = time.time()
    result = db.search(query)
    duration = time.time() - start
    # 延迟数据自动发送到 LangSmith
    return result
```

### 4. Token 用量统计

```python
from langsmith import Client

client = Client()

# 查询项目的 Token 用量
runs = client.list_runs(
    project_name="my-agent-prod",
    start_time="2026-05-01T00:00:00Z",
)
total_tokens = sum(
    (r.total_tokens or 0)
    for r in runs
)
print(f"本月 Token 总用量：{total_tokens:,}")
```

### 5. 错误追踪与重放

```python
# LangSmith 自动捕获异常
try:
    result = graph.invoke(input_data, config)
except Exception as e:
    # 错误在 LangSmith 中标记为 Error，包含完整堆栈
    raise

# 在 LangSmith UI 中：
# - 查看失败的 Trace
# - 复制输入数据
# - 在 Playground 中重放和调试
```

## Dataset 与评估

```python
from langsmith import Client

client = Client()

# 1. 创建评估数据集
dataset = client.create_dataset(
    dataset_name="customer_qa_eval",
    description="客户问答评估集"
)

examples = [
    {"question": "如何重置密码？", "expected": "在设置页面点击..."},
    {"question": "退款需要几天？", "expected": "3-5 个工作日"},
]

for ex in examples:
    client.create_example(
        inputs={"question": ex["question"]},
        outputs={"expected": ex["expected"]},
        dataset_id=dataset.id
    )

# 2. 运行评估
from langsmith.evaluation import evaluate

def predict(example: dict) -> dict:
    result = graph.invoke({
        "messages": [{"role": "user", "content": example["question"]}]
    })
    return {"answer": result["messages"][-1].content}

def correct_answer(outputs: dict, reference_outputs: dict) -> dict:
    """评估答案是否正确（LLM as Judge）"""
    from langchain_openai import ChatOpenAI

    judge = ChatOpenAI(model="gpt-4o-mini")
    score_prompt = f"""参考答案：{reference_outputs['expected']}
Agent 回答：{outputs['answer']}

回答是否正确？评分 0-1（1 表示完全正确）。只返回数字。"""
    score = float(judge.invoke(score_prompt).content.strip())
    return {"key": "correctness", "score": score}

results = evaluate(
    predict,
    data="customer_qa_eval",
    evaluators=[correct_answer],
    experiment_prefix="v2.1",
)

print(f"平均正确率：{sum(r['correctness'] for r in results) / len(results):.2%}")
```

## 监控与告警

```python
# LangSmith 支持设置监控规则
# 在 UI 中配置：
# - Token 用量超过阈值时告警
# - 错误率超过 5% 时告警
# - P95 延迟超过 10s 时告警
# - 特定评估分数下降时告警
```

## 最佳实践

| 实践 | 说明 |
|------|------|
| **命名规范** | 项目名包含环境标识：`my-agent-prod` / `my-agent-staging` |
| **metadata 标记** | 每次调用添加版本号、用户 ID、feature flag |
| **评估驱动开发** | 每次改 Prompt 前先跑评估集 |
| **定期回顾** | 每周检查 P95 延迟和异常 Trace |

```python
# 添加 metadata 标记
config = {
    "configurable": {"thread_id": "user-123"},
    "metadata": {
        "version": "2.1.0",
        "user_id": "user-123",
        "feature": "customer_support",
        "environment": "production"
    }
}
result = graph.invoke(input_data, config)
```

## 实践练习

1. 在项目中集成 LangSmith，运行 10 次不同查询并查看 Trace
2. 创建一个 20 条的评估数据集，对 Agent 进行自动评估
3. 使用 LangSmith Playground 对比两个不同 Prompt 的效果
