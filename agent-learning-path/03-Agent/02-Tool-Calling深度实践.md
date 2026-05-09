# Tool Calling 深度实践

## 工具定义

### @tool 装饰器（最简洁）

```python
from langchain_core.tools import tool

@tool
def search_knowledge_base(query: str) -> str:
    """搜索内部知识库。适用于产品文档、公司政策等问题。"""
    # 实际对接向量数据库或搜索 API
    results = vector_store.similarity_search(query, k=3)
    return "\n---\n".join([doc.page_content for doc in results])

@tool
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """获取指定时区的当前时间。timezone 如 'Asia/Shanghai', 'America/New_York'。"""
    from datetime import datetime
    import pytz
    tz = pytz.timezone(timezone)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
```

### StructuredTool（需要复杂参数 Schema）

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class SQLQueryInput(BaseModel):
    """SQL 查询参数"""
    table: str = Field(description="要查询的表名")
    columns: list[str] = Field(description="需要返回的列名")
    condition: str = Field(description="WHERE 条件，如 'age > 18'")
    limit: int = Field(default=10, description="返回行数上限")

def execute_sql(table: str, columns: list[str], condition: str, limit: int = 10) -> str:
    """执行参数化 SQL 查询（只读）"""
    cols = ", ".join(columns)
    query = f"SELECT {cols} FROM {table} WHERE {condition} LIMIT {limit}"
    # 实际环境中使用参数化查询防止 SQL 注入
    return execute_readonly_query(query)

sql_tool = StructuredTool.from_function(
    func=execute_sql,
    name="sql_query",
    description="执行只读 SQL 查询。table/columns/condition 为必填。",
    args_schema=SQLQueryInput
)
```

## 工具错误处理

### 重试机制

```python
from langgraph.prebuilt import ToolNode

def fallback_search(query: str) -> str:
    """备用搜索：主搜索失败时使用"""
    return "备用搜索结果：..."

tool_node = ToolNode(
    [search_knowledge_base, get_current_time],
    handle_tool_errors=True  # 捕获异常，返回错误消息而非抛出
)

# 或为每个工具配置降级
tool_node_with_fallback = ToolNode(
    [search_knowledge_base],
    handle_tool_errors="搜索服务暂时不可用，请稍后重试"
)
```

### 自定义错误处理

```python
from langgraph.prebuilt import ToolNode

def custom_error_handler(error: Exception, tool_call: dict) -> str:
    """自定义工具错误处理"""
    tool_name = tool_call.get("name", "unknown")
    if isinstance(error, TimeoutError):
        return f"[{tool_name}] 请求超时，请简化查询后重试"
    if isinstance(error, PermissionError):
        return f"[{tool_name}] 权限不足，请联系管理员"
    return f"[{tool_name}] 执行出错：{str(error)[:200]}"

tool_node = ToolNode(
    [search_knowledge_base],
    handle_tool_errors=custom_error_handler
)
```

## 工具绑定与调用

### bind_tools：基础绑定

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")
tools = [search_knowledge_base, get_current_time, sql_tool]

# 绑定工具
llm_with_tools = llm.bind_tools(tools)

# LLM 会自动选择是否调用工具、调用哪些工具
response = llm_with_tools.invoke("搜索产品 X 的文档")
print(response.tool_calls)
# [{"name": "search_knowledge_base", "args": {"query": "产品 X 文档"}, "id": "call_xxx"}]
```

### bind_tools 的参数控制

```python
# tool_choice 控制工具调用行为
llm.bind_tools(tools, tool_choice="auto")     # 自动决定（默认）
llm.bind_tools(tools, tool_choice="any")      # 必须调用某个工具
llm.bind_tools(tools, tool_choice="none")     # 禁止调用工具

# 强制使用特定工具
llm.bind_tools(tools, tool_choice={"type": "function", "function": {"name": "search_knowledge_base"}})

# 并行工具调用
llm.bind_tools(tools, parallel_tool_calls=True)   # 允许并行调用多个工具
llm.bind_tools(tools, parallel_tool_calls=False)  # 一次只能调用一个
```

## 完整 Agent 示例

```python
from typing import TypedDict
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

@tool
def calculator(expression: str) -> str:
    """安全执行数学表达式。支持 +-*/() 和小数。"""
    import re
    if not re.match(r"^[\d\+\-\*/\(\)\.\s]+$", expression):
        return "错误：表达式包含不允许的字符"
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算错误：{e}"

@tool
def web_search(query: str) -> str:
    """搜索互联网获取最新信息"""
    # 实际对接 Tavily 或其他搜索 API
    return f"关于 '{query}' 的搜索结果：..."

tools = [calculator, web_search]
llm = ChatOpenAI(model="gpt-4o").bind_tools(tools)

def agent(state: MessagesState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state: MessagesState) -> str:
    last_msg = state["messages"][-1]
    if last_msg.tool_calls:
        return "tools"
    return END

builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

graph = builder.compile(checkpointer=MemorySaver())

# 使用
config = {"configurable": {"thread_id": "session-1"}}
result = graph.invoke(
    {"messages": [{"role": "user", "content": "计算 (123 * 456) / 789 的结果"}]},
    config
)
print(result["messages"][-1].content)
```

## 工具设计最佳实践

1. **清晰的描述**：docstring 是 LLM 选择工具的关键依据，写清楚"何时使用"
2. **类型注解**：确保参数类型明确，这会被转换为 JSON Schema
3. **幂等性**：只读工具可重试，写操作需要幂等设计
4. **返回结构化**：返回易读的字符串或 JSON，方便 LLM 理解和后续处理
5. **安全第一**：SQL 用参数化查询，eval 尽量不用或用沙箱

## 实践练习

1. 设计一个"航班查询"工具，包含出发地、目的地、日期参数
2. 为工具添加自定义错误处理：超时重试 + 降级 API
3. 对比 `tool_choice="auto"` vs `"any"` 的行为差异
