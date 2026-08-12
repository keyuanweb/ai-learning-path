# MCP 客户端与 Agent 集成

## 概述

MCP Server 开发完成后，需要集成到 Agent 框架中才能被 AI 使用。本章介绍三大主流框架的 MCP 集成方式。

## LangChain / LangGraph 集成

### 使用 langchain-mcp-adapters

```bash
pip install langchain-mcp-adapters
```

### 基础集成：stdio 模式

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

async def create_mcp_agent():
    # 1. 配置 MCP Server 连接
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )

    # 2. 建立连接并加载工具
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 3. 将 MCP 工具转换为 LangChain Tool
            tools = await load_mcp_tools(session)

            # 4. 创建 Agent
            agent = create_agent(
                model=ChatOpenAI(model="gpt-4o"),
                tools=tools,
                system_prompt="你是一个企业助手，可以使用 MCP 工具查询文档和创建工单。"
            )

            # 5. 调用 Agent
            result = agent.invoke({
                "messages": [{"role": "user", "content": "搜索关于微服务架构的文档"}]
            })
            return result["messages"][-1].content

# 运行
response = asyncio.run(create_mcp_agent())
print(response)
```

### HTTP 模式集成（远程 MCP Server）

```python
from mcp.client.streamable_http import streamablehttp_client

async def create_remote_mcp_agent():
    async with streamablehttp_client("http://localhost:8000/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)

            agent = create_agent(
                model=ChatOpenAI(model="gpt-4o"),
                tools=tools,
                system_prompt="你是一个企业助手。"
            )

            result = agent.invoke({
                "messages": [{"role": "user", "content": "查询系统状态"}]
            })
            return result["messages"][-1].content
```

### 多 MCP Server 集成

```python
async def create_multi_mcp_agent():
    # 配置多个 MCP Server
    servers = [
        {
            "name": "docs",
            "params": StdioServerParameters(command="python", args=["docs_server.py"])
        },
        {
            "name": "tickets",
            "params": StdioServerParameters(command="python", args=["tickets_server.py"])
        },
        {
            "name": "github",
            "url": "https://mcp.github.com/mcp"  # 远程 Server
        }
    ]

    all_tools = []

    # 连接本地 Server
    for server in servers:
        if "params" in server:
            stdio_context = stdio_client(server["params"])
            read, write = await stdio_context.__aenter__()
            session = ClientSession(read, write)
            await session.initialize()
            tools = await load_mcp_tools(session)
            # 为工具添加来源标记
            for tool in tools:
                tool.name = f"{server['name']}__{tool.name}"
            all_tools.extend(tools)

    agent = create_agent(
        model=ChatOpenAI(model="gpt-4o"),
        tools=all_tools,
        system_prompt="""你有以下工具来源：
- docs: 文档搜索
- tickets: 工单管理
- github: GitHub 操作"""
    )
    return agent
```

### 在 LangGraph StateGraph 中集成

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

async def build_mcp_graph():
    # 加载 MCP 工具
    tools = await load_mcp_tools_from_session(session)

    # 构建 Graph
    builder = StateGraph(MessagesState)

    # Agent 节点（LLM + 工具绑定）
    llm = ChatOpenAI(model="gpt-4o").bind_tools(tools)

    def agent_node(state: MessagesState):
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    return builder.compile()
```

## OpenAI Agents SDK 集成

### 基础集成

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp

# 方式 1：本地 stdio MCP Server
async with MCPServerStdio(
    name="Enterprise MCP",
    params={"command": "python", "args": ["server.py"]},
) as server:
    agent = Agent(
        name="企业助手",
        instructions="你是一个企业助手，可以使用 MCP 工具。",
        model="gpt-4o",
        mcp_servers=[server],
    )

    result = await Runner.run(agent, "搜索关于微服务架构的文档")
    print(result.final_output)

# 方式 2：远程 HTTP MCP Server
async with MCPServerStreamableHttp(
    name="Remote MCP",
    params={"url": "http://localhost:8000/mcp"},
) as server:
    agent = Agent(
        name="远程助手",
        instructions="你可以使用远程 MCP 工具。",
        model="gpt-4o",
        mcp_servers=[server],
    )
    result = await Runner.run(agent, "查询系统状态")
    print(result.final_output)
```

### 工具审批策略

```python
from agents.mcp import MCPServerStdio

async with MCPServerStdio(
    name="Enterprise MCP",
    params={"command": "python", "args": ["server.py"]},
    # 审批策略配置
    approval_policy={
        "search_docs": "never",           # 只读操作无需审批
        "create_support_ticket": "always", # 写操作始终审批
        "check_ticket_status": "never",    # 只读
    },
    # 或全局策略
    # approval_policy="always",
) as server:
    agent = Agent(
        name="企业助手",
        instructions="...",
        mcp_servers=[server],
    )
```

### 多 MCP Server + 工具过滤

```python
async with MCPServerStdio(
    name="Docs MCP",
    params={"command": "python", "args": ["docs_server.py"]},
) as docs_server, MCPServerStdio(
    name="Tickets MCP",
    params={"command": "python", "args": ["tickets_server.py"]},
) as tickets_server:

    agent = Agent(
        name="企业助手",
        instructions="""你是企业助手。
- 使用 Docs MCP 搜索文档
- 使用 Tickets MCP 管理工单""",
        model="gpt-4o",
        mcp_servers=[docs_server, tickets_server],
        # 按工具名过滤
        tool_use_allowlist=[
            "mcp__EnterpriseTools__search_docs",
            "mcp__EnterpriseTools__check_ticket_status",
        ],
    )
```

## Claude Agent SDK 集成

```python
# Claude Agent SDK 通过 MCP 配置文件集成
# 工具自动以 mcp__<server>__<tool> 命名

# .mcp.json 或 claude_desktop_config.json
{
  "mcpServers": {
    "enterprise-tools": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/project"
    },
    "github": {
      "url": "https://mcp.github.com/mcp"
    }
  }
}
```

```python
# Python SDK 中使用 MCP 工具
from claude_agent_sdk import ClaudeAgent

agent = ClaudeAgent(
    model="claude-sonnet-5",
    # MCP Server 从配置自动加载
    # 工具可通过 mcp__<server>__<tool> 名称访问
    system_prompt="你是一个企业助手。"
)
```

## 工具动态发现

MCP 的核心优势之一是 Agent 在运行时自动发现 MCP Server 提供的工具，无需预先定义：

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def discover_mcp_tools(server_command: str, server_args: list[str]):
    """动态发现 MCP Server 提供的所有工具"""
    server_params = StdioServerParameters(
        command=server_command,
        args=server_args,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 列出工具
            tools_result = await session.list_tools()
            print(f"发现 {len(tools_result.tools)} 个工具:")
            for tool in tools_result.tools:
                print(f"  🔧 {tool.name}: {tool.description}")

            # 列出资源
            resources_result = await session.list_resources()
            print(f"\n发现 {len(resources_result.resources)} 个资源:")
            for resource in resources_result.resources:
                print(f"  📄 {resource.uri}: {resource.name}")

            # 列出提示模板
            prompts_result = await session.list_prompts()
            print(f"\n发现 {len(prompts_result.prompts)} 个提示模板:")
            for prompt in prompts_result.prompts:
                print(f"  💬 {prompt.name}")

            return {
                "tools": tools_result.tools,
                "resources": resources_result.resources,
                "prompts": prompts_result.prompts,
            }

# 运行发现
discovered = asyncio.run(discover_mcp_tools("python", ["server.py"]))
```

## 工具调用追踪

```python
from langsmith import traceable
from mcp import ClientSession

class TracedMCPSession:
    """带 LangSmith 追踪的 MCP 会话封装"""

    def __init__(self, session: ClientSession):
        self.session = session

    @traceable(run_type="tool", name="mcp_call_tool")
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP 工具并记录追踪"""
        result = await self.session.call_tool(tool_name, arguments)
        # result 自动包含在 LangSmith trace 中
        return result.content[0].text if result.content else ""

# 使用
async with ClientSession(read, write) as session:
    traced = TracedMCPSession(session)
    result = await traced.call_tool("search_docs", {"query": "test"})
```

## 错误处理与重试

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class RobustMCPClient:
    """带重试和超时的 MCP 客户端"""

    def __init__(self, session: ClientSession, max_retries: int = 3):
        self.session = session
        self.max_retries = max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def call_tool_safe(self, tool_name: str, arguments: dict, timeout: int = 30):
        """安全调用 MCP 工具（带重试和超时）"""
        try:
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return f"⚠️ 工具 {tool_name} 执行超时（>{timeout}秒）"
        except ConnectionError:
            return f"❌ 连接 MCP Server 失败，请检查服务状态"
        except Exception as e:
            return f"❌ 工具调用异常: {str(e)}"
```

## 完整集成示例：多源 MCP Agent

```python
"""
多源 MCP Agent 示例
集成本地文档搜索 + 远程 GitHub 两个 MCP Server
"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

async def main():
    all_tools = []

    # 1. 连接本地文档 MCP Server
    print("连接本地文档 MCP Server...")
    doc_params = StdioServerParameters(command="python", args=["docs_server.py"])
    async with stdio_client(doc_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            doc_tools = await load_mcp_tools(session)
            all_tools.extend(doc_tools)
            print(f"  加载 {len(doc_tools)} 个文档工具")

    # 2. 连接远程 GitHub MCP Server
    print("连接远程 GitHub MCP Server...")
    async with streamablehttp_client("https://mcp.github.com/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            github_tools = await load_mcp_tools(session)
            all_tools.extend(github_tools)
            print(f"  加载 {len(github_tools)} 个 GitHub 工具")

    # 3. 创建集成 Agent
    agent = create_agent(
        model=ChatOpenAI(model="gpt-4o"),
        tools=all_tools,
        system_prompt="""你是一个全栈开发助手，拥有以下能力：
- 📄 搜索企业内部文档
- 🐙 查询 GitHub 仓库信息

根据任务需求选择合适的工具。""",
    )

    # 4. 测试
    result = agent.invoke({
        "messages": [{"role": "user", "content": "搜索微服务部署文档，然后看看最近有哪些相关 PR"}]
    })
    print(f"\n🤖 Agent 回复:\n{result['messages'][-1].content}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 实践练习

1. 将你之前开发的 MCP Server 集成到 LangChain `create_agent` 中，测试 3 个以上工具调用场景
2. 实现多 MCP Server 集成（本地+远程），验证 Agent 能正确选择不同 Server 的工具
3. 为 MCP 工具调用添加 LangSmith 追踪，观察一次 Agent 调用中的工具选择链
