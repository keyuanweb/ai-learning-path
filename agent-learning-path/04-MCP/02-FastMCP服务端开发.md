# FastMCP 服务端开发

## FastMCP 简介

FastMCP 是 MCP 协议的 Python 高级框架，灵感来自 FastAPI 的设计哲学——用装饰器和类型注解快速构建 MCP Server。它是目前最流行的 MCP 服务端开发方式。

```bash
# 安装
pip install mcp[cli]
# 或使用 uv
uv add mcp[cli]
```

## 第一个 MCP Server

```python
# server.py
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server 实例
mcp = FastMCP("My First MCP Server", version="1.0.0")

@mcp.tool()
def hello(name: str) -> str:
    """向用户打招呼"""
    return f"你好，{name}！欢迎使用 MCP。"

# 运行服务
if __name__ == "__main__":
    mcp.run()  # 默认使用 stdio 传输
```

运行方式：

```bash
# stdio 模式（本地开发/Claude Desktop 使用）
python server.py

# 或通过 MCP CLI 运行
mcp run server.py
```

## 工具（Tools）定义

Tool 是 MCP Server 最核心的原语，让 Agent 可以执行操作。

### 基础 Tool

```python
@mcp.tool()
def calculate(expression: str) -> str:
    """安全计算数学表达式

    Args:
        expression: 数学表达式，如 "2 + 3 * 4"
    """
    try:
        # 安全计算（仅允许数学运算）
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return "错误：表达式包含不允许的字符"
        result = eval(expression)
        return f"计算结果：{result}"
    except Exception as e:
        return f"计算错误：{e}"
```

### 带复杂参数的 Tool

```python
from typing import Optional
from pydantic import BaseModel, Field

class SearchParams(BaseModel):
    """搜索参数模型（自动生成 JSON Schema）"""
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=10, ge=1, le=100, description="最大结果数")
    category: Optional[str] = Field(default=None, description="分类过滤")
    sort_by: Optional[str] = Field(default="relevance", description="排序方式")

@mcp.tool()
async def search_knowledge_base(params: SearchParams) -> str:
    """在知识库中搜索文档

    Args:
        params: 搜索参数
    """
    # 实际搜索逻辑
    results = await kb_search(
        query=params.query,
        limit=params.max_results,
        category=params.category,
        sort=params.sort_by
    )
    return format_search_results(results)
```

### 异步 Tool

```python
import asyncio
import httpx

@mcp.tool()
async def fetch_api_data(url: str, timeout: int = 30) -> str:
    """异步获取 API 数据

    Args:
        url: API 端点 URL
        timeout: 请求超时（秒）
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text[:4000]  # 截断长响应
```

### Tool 错误处理

```python
from mcp.server.fastmcp import FastMCP
import logging

mcp = FastMCP("RobustServer")
logger = logging.getLogger(__name__)

@mcp.tool()
async def query_database(sql: str) -> str:
    """执行只读 SQL 查询"""
    # 安全检查
    if not sql.strip().upper().startswith("SELECT"):
        return "❌ 错误：仅允许 SELECT 查询"

    try:
        result = await db.execute(sql)
        return f"✅ 查询成功\n{format_table(result)}"
    except TimeoutError:
        logger.error(f"查询超时: {sql[:100]}")
        return "❌ 查询超时，请简化查询条件后重试"
    except Exception as e:
        logger.error(f"数据库错误: {e}")
        return f"❌ 查询失败: {str(e)}"
```

## 资源（Resources）暴露

Resource 用于暴露只读的结构化数据。

### 静态资源

```python
@mcp.resource("config://app")
def get_app_config() -> str:
    """返回应用配置"""
    return json.dumps({
        "version": "1.0.0",
        "environment": "production",
        "features": ["search", "analytics", "export"]
    }, indent=2, ensure_ascii=False)

@mcp.resource("docs://readme")
def get_readme() -> str:
    """返回项目 README"""
    with open("README.md", "r") as f:
        return f.read()
```

### 动态资源（URI 模板）

```python
@mcp.resource("user://{user_id}/profile")
async def get_user_profile(user_id: str) -> str:
    """获取用户资料"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        return f"用户 {user_id} 不存在"
    return json.dumps(user, ensure_ascii=False)

@mcp.resource("file://{path}")
async def read_file(path: str) -> str:
    """读取文件内容"""
    # 安全检查：防止路径遍历
    safe_path = os.path.normpath(path)
    if ".." in safe_path:
        return "❌ 不允许的路径"
    with open(safe_path, "r") as f:
        return f.read()
```

### 资源列表发现

```python
@mcp.resource("system://tools")
def list_available_tools() -> str:
    """列出所有可用工具（元数据）"""
    tools_info = []
    for tool in mcp._tool_manager.list_tools():
        tools_info.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema
        })
    return json.dumps(tools_info, indent=2)
```

## 提示模板（Prompts）

```python
@mcp.prompt()
def code_review(code: str, language: str = "python") -> str:
    """代码审查提示模板"""
    return f"""请对以下 {language} 代码进行审查，检查：
1. 代码规范
2. 潜在 Bug
3. 性能问题
4. 安全风险

```{language}
{code}
```

请逐条列出发现的问题和改进建议。"""

@mcp.prompt()
def meeting_summary(transcript: str) -> list:
    """会议纪要提示模板"""
    return [
        {"role": "user", "content": f"""请对以下会议转录内容生成纪要：
1. 会议主题
2. 关键决策
3. 行动项（负责人+截止日期）
4. 待讨论问题

转录内容：
{transcript}"""}
    ]
```

## 传输方式配置

### stdio（默认，本地使用）

```python
# server.py
if __name__ == "__main__":
    mcp.run()  # 默认 stdio
```

Claude Desktop 配置（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/project"
    }
  }
}
```

### HTTP + SSE（远程部署）

```python
# server.py
if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
```

客户端连接：

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async with sse_client("http://localhost:8000/sse") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

### Streamable HTTP（生产推荐，MCP 2026-07-28+）

```python
# server.py
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

## 完整示例：企业文档搜索 MCP Server

```python
"""
企业文档搜索 MCP Server
提供文档搜索、用户信息查询、工单创建等功能
"""
import json
import logging
from typing import Optional
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EnterpriseMCPServer")

# 创建 MCP Server
mcp = FastMCP(
    "EnterpriseTools",
    version="2.1.0",
    description="企业文档搜索与工单管理 MCP Server"
)

# ── 数据模型 ──

class TicketCreate(BaseModel):
    title: str = Field(description="工单标题")
    description: str = Field(description="详细描述")
    priority: str = Field(default="normal", description="优先级: low/normal/high/urgent")
    assignee: Optional[str] = Field(default=None, description="指派人员")

class SearchRequest(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=10, ge=1, le=50)
    doc_type: Optional[str] = Field(default=None, description="文档类型: wiki/design/api/report")

# ── Tools ──

@mcp.tool()
async def search_docs(params: SearchRequest) -> str:
    """搜索企业文档库

    支持按关键词和文档类型搜索，返回相关文档列表。
    """
    logger.info(f"搜索文档: {params.query} (类型: {params.doc_type})")

    # 模拟文档搜索
    results = await document_search_engine.search(
        query=params.query,
        limit=params.max_results,
        filters={"type": params.doc_type} if params.doc_type else None
    )

    if not results:
        return f"未找到与「{params.query}」相关的文档"

    output = [f"## 搜索结果：{params.query}\n"]
    for i, doc in enumerate(results, 1):
        output.append(f"### {i}. {doc['title']}")
        output.append(f"- **类型**: {doc['type']}")
        output.append(f"- **更新时间**: {doc['updated_at']}")
        output.append(f"- **摘要**: {doc['summary'][:200]}")
        output.append(f"- **链接**: {doc['url']}\n")

    return "\n".join(output)

@mcp.tool()
async def create_support_ticket(ticket: TicketCreate) -> str:
    """创建技术支持工单"""
    logger.info(f"创建工单: {ticket.title}")

    ticket_id = await ticket_system.create({
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "assignee": ticket.assignee,
        "created_at": datetime.now().isoformat(),
        "status": "open"
    })

    return f"""✅ 工单已创建
- **工单号**: {ticket_id}
- **标题**: {ticket.title}
- **优先级**: {ticket.priority}
- **状态**: 待处理"""

@mcp.tool()
async def check_ticket_status(ticket_id: str) -> str:
    """查询工单处理状态"""
    ticket = await ticket_system.get(ticket_id)
    if not ticket:
        return f"工单 {ticket_id} 不存在"

    return f"""## 工单 {ticket_id}
- **标题**: {ticket['title']}
- **状态**: {ticket['status']}
- **优先级**: {ticket['priority']}
- **处理人**: {ticket.get('assignee', '未分配')}
- **创建时间**: {ticket['created_at']}
- **最后更新**: {ticket.get('updated_at', 'N/A')}"""

# ── Resources ──

@mcp.resource("system://status")
def get_system_status() -> str:
    """系统运行状态"""
    return json.dumps({
        "status": "healthy",
        "uptime_hours": 720,
        "tools_count": len(mcp._tool_manager.list_tools()),
        "version": "2.1.0"
    }, indent=2)

@mcp.resource("docs://categories")
def get_doc_categories() -> str:
    """文档分类列表"""
    return json.dumps({
        "wiki": "内部知识库",
        "design": "设计文档",
        "api": "API 文档",
        "report": "分析报告",
        "guide": "操作指南"
    }, indent=2, ensure_ascii=False)

# ── Prompts ──

@mcp.prompt()
def document_review(content: str) -> str:
    """文档评审提示"""
    return f"""请对以下文档进行评审，关注：
1. 内容准确性
2. 结构清晰度
3. 术语一致性
4. 改进建议

文档内容：
{content}"""

# ── 启动 ──

if __name__ == "__main__":
    logger.info("启动 EnterpriseTools MCP Server")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

## 测试 MCP Server

### 使用 MCP Inspector

```bash
# 安装
npm install -g @modelcontextprotocol/inspector

# 启动调试
mcp dev server.py
```

### 使用 MCP CLI

```bash
# 测试 Tool 调用
mcp call-tool server.py search_docs '{"query": "微服务架构", "max_results": 5}'

# 读取资源
mcp read-resource server.py "system://status"

# 列出所有工具
mcp list-tools server.py
```

## 最佳实践

| 实践 | 说明 |
|------|------|
| **描述即文档** | Tool 的 docstring 是 Agent 理解工具的唯一途径，务必清晰描述功能、参数和返回值 |
| **安全第一** | 任何写操作都需要输入校验；只读工具也要做权限检查 |
| **错误友好** | 返回用户可理解的错误信息，不要直接抛出异常堆栈 |
| **大输出截断** | 超过 4000 字符的输出应截断或分页，避免撑爆上下文 |
| **结构化输出** | 返回 Markdown 或 JSON 格式，便于 Agent 理解 |
| **审计日志** | 所有 Tool 调用记录日志（调用时间、参数、结果摘要） |

## 实践练习

1. 用 FastMCP 创建一个"天气查询" MCP Server，包含至少 3 个 Tool
2. 为你的 Server 添加动态 Resource（如 `weather://{city}`）
3. 使用 MCP Inspector 测试你的 Server，观察 Agent 如何发现和调用工具
