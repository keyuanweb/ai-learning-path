# StateGraph 四要素

LangGraph 的 StateGraph 由四个核心要素构成：**State**、**Nodes**、**Edges**、**Compile**。

## 要素 1：State（状态）

State 是贯穿整个图执行过程的共享数据结构。使用 TypedDict 或 Pydantic BaseModel 定义。

### TypedDict 定义

```python
from typing import TypedDict, Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    task_progress: int
    final_answer: str
```

### 使用 MessagesState（推荐）

LangGraph 内置了消息列表专用的 State：

```python
from langgraph.graph import MessagesState

# MessagesState 等价于：
# class MessagesState(TypedDict):
#     messages: Annotated[list[AnyMessage], add_messages]

# 扩展 MessagesState
class AgentState(MessagesState):
    context: str
    tool_results: list
```

### Annotated + Reducer 机制

`Annotated[Type, reducer]` 定义了字段的**合并策略**：

```python
from typing import Annotated
import operator

class State(TypedDict):
    # 累加（追加不覆盖）
    results: Annotated[list[str], operator.add]
    # 消息专用合并逻辑
    messages: Annotated[list, add_messages]
    # 普通字段：后写入覆盖前写入
    final_answer: str
```

## 要素 2：Nodes（节点）

节点是图的执行单元，可以是任意 Python 函数或 Runnable。

```python
def my_node(state: State) -> dict:
    """节点函数签名：(state) → state_update_dict

    返回的 dict 会按照 Reducer 规则合并回全局 State
    """
    # 读取 state
    current_value = state.get("key", "default")

    # 处理逻辑
    result = process(current_value)

    # 返回需要更新的字段（可以只返回变化的部分）
    return {"key": result, "processed": True}

# 节点也可以是 async 函数
async def async_node(state: State) -> dict:
    result = await async_process(state["input"])
    return {"output": result}
```

### 节点类型

| 类型 | 说明 | 示例 |
|------|------|------|
| Python 函数 | 普通处理逻辑 | 数据清洗、格式转换 |
| LLM 调用 | `model.invoke(state["messages"])` | 意图识别、内容生成 |
| Tool 执行 | `ToolNode([tools])` | 搜索、计算、API 调用 |
| Agent | `create_agent()` 编译后的子图 | 完整 Agent 作为子节点 |

## 要素 3：Edges（边）

边定义了节点间的执行顺序。

### 普通边（Static Edge）

```python
# A 执行完 → 总是执行 B
builder.add_edge("node_a", "node_b")

# 特殊节点 START 和 END
builder.add_edge(START, "first_node")
builder.add_edge("last_node", END)
```

### 条件边（Conditional Edge）

```python
# A 执行完 → 根据 state 决定下一步
def router(state: State) -> str:
    if state.get("needs_search"):
        return "search"
    if state.get("needs_summary"):
        return "summarize"
    return "end"

builder.add_conditional_edges(
    "agent",
    router,
    {
        "search": "search_node",     # router 返回 "search" → 跳转到 search_node
        "summarize": "summarize_node",
        "end": END
    }
)
```

### 并行边（Parallel Edge）

多个节点共享同一个源和目标时，它们会并行执行：

```python
# B 和 C 会并行执行，两者的结果按 Reducer 规则合并
builder.add_edge("A", "B")
builder.add_edge("A", "C")
builder.add_edge("B", "D")
builder.add_edge("C", "D")
```

### Send API（动态并行）

```python
from langgraph.types import Send

def continue_to_jokes(state):
    """动态创建 N 个并行任务"""
    return [Send("tell_joke", {"topic": t}) for t in state["topics"]]
```

## 要素 4：Compile（编译）

`compile()` 验证图结构、绑定 checkpoint 并返回可执行的 CompiledGraph。

```python
from langgraph.checkpoint.memory import MemorySaver

# 基本编译
graph = builder.compile()

# 带 Checkpoint 的编译（支持记忆和断点恢复）
graph = builder.compile(checkpointer=MemorySaver())

# 带打断的编译
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["human_approval_node"],
    interrupt_after=["tool_execution"]
)
```

## 完整示例：客服意图路由

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

class CustomerState(TypedDict):
    query: str
    intent: str
    response: str

llm = ChatOpenAI(model="gpt-4o-mini")

def classify(state: CustomerState) -> dict:
    """分类用户意图"""
    prompt = f"将以下客服查询分类为 'billing'/'technical'/'general'：{state['query']}"
    intent = llm.invoke(prompt).content.strip().lower()
    return {"intent": intent}

def handle_billing(state: CustomerState) -> dict:
    return {"response": "[账单处理] 正在查询您的账单信息..."}

def handle_technical(state: CustomerState) -> dict:
    return {"response": "[技术支持] 已创建工单，技术团队将回复您..."}

def handle_general(state: CustomerState) -> dict:
    return {"response": "[通用客服] 您好，请问有什么可以帮助您的？"}

def route(state: CustomerState) -> str:
    intent = state.get("intent", "general")
    if "billing" in intent:
        return "billing"
    if "technical" in intent or "tech" in intent:
        return "technical"
    return "general"

builder = StateGraph(CustomerState)
builder.add_node("classify", classify)
builder.add_node("billing", handle_billing)
builder.add_node("technical", handle_technical)
builder.add_node("general", handle_general)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route, {
    "billing": "billing",
    "technical": "technical",
    "general": "general",
})
builder.add_edge("billing", END)
builder.add_edge("technical", END)
builder.add_edge("general", END)

graph = builder.compile(checkpointer=MemorySaver())

# 执行
result = graph.invoke(
    {"query": "我的账单为什么多扣了50元？"},
    {"configurable": {"thread_id": "user-123"}}
)
print(result["intent"])    # "billing"
print(result["response"])  # "[账单处理] 正在查询您的账单信息..."
```

## 实践练习

1. 用 Pydantic BaseModel 定义 State（而非 TypedDict）
2. 为客服路由系统增加一个"升级到人工"的条件（涉及金额 > 1000 时直接转人工）
3. 用 `add_messages` Reducer 实现消息历史的自动合并
