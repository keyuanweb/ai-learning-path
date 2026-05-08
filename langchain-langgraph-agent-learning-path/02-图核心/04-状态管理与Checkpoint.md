# 状态管理与 Checkpoint

## 什么是 Checkpoint

Checkpoint 是 LangGraph 的**状态快照机制**，在图的每个 super-step 之后自动保存 State。它支撑三大能力：

| 能力 | 说明 |
|------|------|
| **多轮对话记忆** | 同一 thread_id 的多次调用自动衔接上下文 |
| **断点恢复 (Time Travel)** | 回退到任意历史步骤，重放或修复 |
| **Human-in-the-Loop** | 暂停执行 → 人工介入 → 从断点继续 |

## Checkpoint 基础

### MemorySaver：内存 Checkpoint

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END

builder = StateGraph(MessagesState)
# ... 添加节点和边 ...

graph = builder.compile(checkpointer=MemorySaver())

# 每次调用传同一个 thread_id，自动维护对话记忆
config = {"configurable": {"thread_id": "user-session-1"}}

# 第 1 轮
result1 = graph.invoke(
    {"messages": [{"role": "user", "content": "我叫张三"}]},
    config
)

# 第 2 轮 —— 自动记住上一轮的对话
result2 = graph.invoke(
    {"messages": [{"role": "user", "content": "我叫什么名字？"}]},
    config
)
# Agent 会回答 "你叫张三"，因为消息历史在 Checkpoint 中保持
```

### SqliteSaver：持久化 Checkpoint

```python
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    # Checkpoint 会被持久化到 SQLite 数据库中
    # 重启应用后对话记忆仍然存在
```

## State Reducer：合并规则

Reducer 决定了同一字段的多次写入如何合并。

### add_messages：消息专用 Reducer

```python
from langgraph.graph import add_messages
from typing import Annotated
from langchain_core.messages import HumanMessage, AIMessage

class State(TypedDict):
    messages: Annotated[list, add_messages]
    # add_messages:
    # - 新消息追加到列表末尾
    # - 同 ID 的消息替换（支持消息更新）
    # - 专门处理 AIMessage 的 tool_calls 合并
```

### operator.add：列表累加

```python
import operator

class State(TypedDict):
    collected_docs: Annotated[list[str], operator.add]
    # 每次节点返回 {"collected_docs": ["doc1"]}
    # 最终 collected_docs = ["doc1", "doc2", "doc3"]
```

### 自定义 Reducer

```python
def keep_latest(current, update):
    """始终保留最新值（默认行为）"""
    return update

def merge_json(current: dict, update: dict) -> dict:
    """深度合并两个 dict"""
    merged = current.copy()
    merged.update(update)
    return merged

class State(TypedDict):
    config: Annotated[dict, merge_json]
```

## Time Travel：历史状态回放

```python
# 查看对话历史
history = list(graph.get_state_history(config))

for snapshot in history:
    print(f"Step {snapshot.metadata.get('step')}:")
    print(f"  Next node: {snapshot.next}")
    print(f"  Messages: {len(snapshot.values.get('messages', []))}")

# 回退到指定 Checkpoint
checkpoint_id = history[2].config["configurable"]["checkpoint_id"]
resumed = graph.invoke(None, {
    "configurable": {
        "thread_id": "user-session-1",
        "checkpoint_id": checkpoint_id
    }
})
```

## Human-in-the-Loop：暂停与恢复

### interrupt() 暂停

```python
from langgraph.types import interrupt

def sensitive_action(state: State) -> dict:
    """执行敏感操作前暂停，等待人工审批"""
    # 这行代码会暂停图执行
    approval = interrupt(f"确认执行：{state['action']}? (yes/no)")

    if approval == "yes":
        return {"result": execute(state["action"])}
    return {"result": "操作已取消"}
```

### 编译时配置打断点

```python
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["sensitive_action"],   # 在此节点之前暂停
    interrupt_after=["tool_execution"]       # 在此节点之后暂停
)
```

### 恢复执行

```python
# 1. 初始调用（会在敏感节点前暂停）
result = graph.invoke(input_data, config)

# 2. 检查是否被暂停
state = graph.get_state(config)
print(state.next)  # 暂停前应该执行的节点

# 3. 人工审批后恢复
graph.invoke(Command(resume={"approved": True}), config)
```

## 完整示例：带记忆和人工审批的 Agent

```python
from typing import TypedDict
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langchain_openai import ChatOpenAI

class AgentState(MessagesState):
    action_requested: str
    approved: bool

llm = ChatOpenAI(model="gpt-4o-mini")

def agent(state: AgentState) -> dict:
    """Agent 决定是否需要执行操作"""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def request_action(state: AgentState) -> dict:
    """请求执行操作（可能触发人工审批）"""
    last_msg = state["messages"][-1].content

    # 如果是敏感操作，触发 interrupt
    if "删除" in last_msg or "支付" in last_msg:
        approval = interrupt(f"⚠️ 确认执行：{last_msg}")
        if not approval:
            return {"messages": [{"role": "assistant", "content": "操作已取消"}]}

    return {"messages": [{"role": "assistant", "content": f"已执行：{last_msg}"}]}

builder = StateGraph(AgentState)
builder.add_node("agent", agent)
builder.add_node("action", request_action)
builder.add_edge(START, "agent")
builder.add_conditional_edges(
    "agent",
    lambda s: "action" if "执行" in s["messages"][-1].content else END,
    {"action": "action", END: END}
)
builder.add_edge("action", END)

graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["action"]  # 所有 action 前都暂停
)

# 使用
config = {"configurable": {"thread_id": "user-1"}}
result = graph.invoke(
    {"messages": [{"role": "user", "content": "帮我删除所有数据"}]},
    config
)

# 检查暂停状态
state = graph.get_state(config)
print(f"等待审批的操作：{state.values.get('messages', [])[-1].content if state.values.get('messages') else 'N/A'}")

# 人工审批通过
graph.invoke(Command(resume=True), config)
```

## 实践练习

1. 实现一个会话记忆系统：同一 thread_id 下的对话能自动记住前 5 轮内容
2. 使用 Time Travel 回退到 3 步之前，修改用户输入后重新执行
3. 为支付流程添加双人审批（两个不同角色分别 approve 后才执行）
