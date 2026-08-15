# LangChain 与 LangGraph 生态

LangChain 是 LLM 应用开发最主流的框架。2024 年后 LangGraph 成为 Agent 开发的核心工具。本章聚焦它们的核心抽象和实战用法。

---

## 1. LangChain 解决什么问题

### 原生 API 调用的痛点

```python
# 不用 LangChain：裸调 API
response = openai.chat.completions.create(...)
# 每次都要手动管理消息历史、拼接 prompt、处理 token 数、选择模型...
# 换一个模型提供商（Anthropic → 阿里）→ 重写所有代码
```

### LangChain 的核心价值

> 提供一套**标准化的 LLM 应用开发抽象**，屏蔽不同模型提供商的差异，内置常用模式（对话记忆、RAG、Agent）。

---

## 2. LangChain 核心抽象

### Chain：把多个步骤串起来

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 定义一个 chain
prompt = ChatPromptTemplate.from_template("将以下内容翻译成{language}: {text}")
model = ChatOpenAI(model="gpt-4o")
parser = StrOutputParser()

chain = prompt | model | parser  # 用 | 串联

# 调用
result = chain.invoke({
    "language": "英文",
    "text": "今天天气真好"
})
# "The weather is really nice today."
```

**`|` 操作符 = LCEL (LangChain Expression Language)**——用管道符串联组件，像 Unix 管道一样直觉。

### Memory：记住对话历史

```python
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(return_messages=True)
# 每次对话自动追加到 memory，下次调用时带入上下文
```

### Retriever：检索增强

```python
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

vectorstore = Chroma(embedding_function=OpenAIEmbeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 在 chain 中使用 retriever
qa_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | model
    | parser
)
```

### Tool：Agent 的工具箱

```python
from langchain.tools import tool

@tool
def get_weather(city: str) -> str:
    """获取指定城市当前天气"""
    # 实际调用天气 API
    return f"{city}: 晴, 25°C"
```

---

## 3. LangGraph：从 Chain 到 Graph

### Chain 的局限

Chain 是**线性**的——固定步骤 A→B→C。Agent 需要**分支、循环、条件跳转**。

### LangGraph 解决的问题

> 用有向图描述 LLM 应用的**控制流**——节点 = 操作（调用 LLM、执行工具），边 = 流转（正常、条件分支、循环）。

### 一个完整的 LangGraph Agent

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

# 1. 定义状态
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # 消息会追加而非覆盖

# 2. 定义节点
def call_model(state):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"         # 走工具分支
    return END                 # 结束

def call_tools(state):
    last_message = state["messages"][-1]
    tool_results = []
    for tool_call in last_message.tool_calls:
        result = execute_tool(tool_call)
        tool_results.append(result)
    return {"messages": tool_results}

# 3. 构建图
workflow = StateGraph(AgentState)
workflow.add_node("llm", call_model)
workflow.add_node("tools", call_tools)
workflow.set_entry_point("llm")

# 4. 添加边
workflow.add_conditional_edges("llm", should_continue, {
    "tools": "tools",
    END: END
})
workflow.add_edge("tools", "llm")  # 工具结果返回 LLM

# 5. 编译运行
app = workflow.compile()
result = app.invoke({"messages": [HumanMessage(content="北京天气？")]})
```

---

## 4. LangGraph 的核心概念

### State：图的记忆

State 是一个在节点间流转的共享字典。每个节点读取 State、返回 State 的更新。最关键的设计选择是**每个字段的"合并策略"**：

```python
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # 追加（对话历史）
    scratchpad: str                           # 覆盖（临时草稿）
    step_count: int                           # 覆盖（步数计数）
```

### Checkpoint：快照与回放

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# 传入 thread_id 启用 checkpoint
config = {"configurable": {"thread_id": "conversation-42"}}
app.invoke(input, config)

# 可以回溯到任意历史状态
state = app.get_state(config)
```

Checkpoint 让 LangGraph 天然支持：
- **多轮对话**：每个 thread_id 保存完整对话历史
- **Human-in-the-Loop**：在关键节点暂停，等待人类批准
- **错误恢复**：出错后回退到上一个 checkpoint

### Human-in-the-Loop

```python
# 在危险操作前暂停
workflow.add_node("approval", human_approval)
workflow.add_edge("tools", "approval")
workflow.add_edge("approval", "llm")

# 编译时指定中断点
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["approval"]  # 执行前中断
)

# 用户批准后恢复
app.invoke(None, config)  # None = 从上次中断处继续
```

---

## 5. LangChain vs LangGraph 选型

| 场景 | 用 LangChain | 用 LangGraph |
|------|-------------|-------------|
| 简单 RAG | ✓ | 过度设计 |
| 固定流程 | ✓ Chain | 可以但没必要 |
| Agent + 工具 | 弱 | ✓ |
| 多轮对话 | ✓ Memory | ✓ Checkpoint |
| 复杂分支 | ✗ | ✓ |
| Human-in-the-Loop | ✗ | ✓ |
| 多 Agent 协作 | ✗ | ✓ |

**2025 年共识**：简单场景用 LangChain（快速开发），Agent 或有复杂控制流用 LangGraph。

---

## 6. 生态工具链

| 工具 | 用途 |
|------|------|
| **LangSmith** | 调试、测试、监控 LLM 应用（LangChain 官方） |
| **LangServe** | 将 LangChain chain 部署为 REST API |
| **LangFuse** | 开源替代 LangSmith，追踪 token 消耗和延迟 |
| **LlamaIndex** | 专注于数据索引和检索（RAG 场景替代/互补 LangChain） |
| **Vercel AI SDK** | 前端 LLM 应用（JS/TS 生态的 LangChain 对应物） |

---

## 本章速查

| 概念 | 一句话 |
|------|--------|
| **LangChain** | LLM 应用的标准化抽象（Chain、Memory、Retriever、Tool） |
| **LCEL** | `\|` 管道符串联组件 |
| **LangGraph** | 有向图描述 Agent 控制流（State + Node + Edge） |
| **State** | 图的共享记忆（每个字段可定义合并策略） |
| **Checkpoint** | 状态快照 → 多轮对话 + 断点恢复 + Human-in-the-Loop |
