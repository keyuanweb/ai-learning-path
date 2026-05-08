# create_agent 新 API

## API 演进

LangChain v1.0 引入了统一的 `create_agent()` API，替代旧的分散式创建方式。

| 旧 API (已废弃) | 新 API |
|-----------------|--------|
| `create_react_agent()` | `create_agent()` |
| `create_tool_calling_agent()` | `create_agent()` |
| `create_openai_functions_agent()` | `create_agent()` |
| `create_structured_chat_agent()` | `create_agent()` |

## 基础用法

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    return f"{city}：晴，22°C"

@tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

agent = create_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[get_weather, calculator],
    system_prompt="你是一个有用的助手，可以使用天气查询和计算器工具。",
)

# create_agent 返回的是编译好的 StateGraph
result = agent.invoke({
    "messages": [{"role": "user", "content": "北京今天天气如何？"}]
})
print(result["messages"][-1].content)
```

## 工作原理

`create_agent()` 内部自动编译了一个标准的 ReAct StateGraph：

```
START → agent (LLM + tools) → tools → agent → ... → END
                              ↑_________|  (循环直到 LLM 不再调用工具)
```

等价的手动构建代码：

```python
# create_agent() 内部等价于：
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

builder = StateGraph(MessagesState)
builder.add_node("agent", model.bind_tools(tools))
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")
graph = builder.compile()
```

## 高级配置

### 系统提示词

```python
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="""你是一个专业的金融分析助手。

规则：
1. 涉及到数字计算时必须使用 calculator 工具
2. 对于不确定的信息，明确说明
3. 给出分析结论时提供计算依据""",
)
```

### 中间件（Middleware）

```python
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ToolRetryMiddleware,
    SummarizationMiddleware,
)

agent = create_agent(
    model=llm,
    tools=tools,
    middleware=[
        ToolRetryMiddleware(max_retries=3),
        SummarizationMiddleware(max_tokens=4000),  # 超过 4000 token 自动摘要
    ],
)
```

### 自定义 State

```python
from typing import TypedDict
from langgraph.graph import MessagesState

class CustomAgentState(MessagesState):
    user_id: str
    session_context: str
    tool_call_count: int

agent = create_agent(
    model=llm,
    tools=tools,
    state_schema=CustomAgentState,  # 使用自定义 State
    system_prompt="...",
)
```

## 与手动 StateGraph 混用

`create_agent()` 创建的 Agent 可以作为子图嵌套到更大的工作流中：

```python
from langgraph.graph import StateGraph, START, END

# 创建子 Agent
research_agent = create_agent(
    model=llm,
    tools=[web_search],
    system_prompt="你是研究员，负责搜索信息。"
)

class MainState(TypedDict):
    question: str
    research_result: str
    final_answer: str

def do_research(state: MainState) -> dict:
    result = research_agent.invoke({
        "messages": [{"role": "user", "content": state["question"]}]
    })
    return {"research_result": result["messages"][-1].content}

def synthesize(state: MainState) -> dict:
    response = llm.invoke(f"基于以下研究结果，回答问题：\n{state['research_result']}\n\n问题：{state['question']}")
    return {"final_answer": response.content}

main_builder = StateGraph(MainState)
main_builder.add_node("research", do_research)
main_builder.add_node("synthesize", synthesize)
main_builder.add_edge(START, "research")
main_builder.add_edge("research", "synthesize")
main_builder.add_edge("synthesize", END)

main_graph = main_builder.compile()
```

## 迁移指南

```python
# 旧代码
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(model=llm, tools=tools)

# 新代码（一行改动）
from langchain.agents import create_agent
agent = create_agent(model=llm, tools=tools)

# 行为完全兼容，invoke 参数和返回值格式一致
result = agent.invoke({"messages": [HumanMessage(content="...")]})
```

## 实践练习

1. 用 `create_agent()` 创建一个带 3 个以上工具的 Agent，测试工具自动选择
2. 实现 `ToolRetryMiddleware` 场景：模拟一个不稳定的工具，观察重试行为
3. 将 `create_agent()` 的 Agent 嵌套到包含预处理和后处理步骤的 StateGraph 中
