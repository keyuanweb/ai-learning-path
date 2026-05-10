# 自定义 MCP Server 开发

## 为什么需要自定义 MCP Server？

当现有的 300+ 个 MCP Server 不能满足需求时，你可以开发自己的 MCP Server 来暴露内部工具、API 或数据源。

## 协议基础

MCP 使用 **JSON-RPC 2.0** 协议。一个 MCP Server 需要实现三个核心方法：

| 方法 | 方向 | 说明 |
|------|------|------|
| `tools/list` | Client → Server | 返回可用工具列表 |
| `tools/call` | Client → Server | 执行特定工具 |
| `resources/list` | Client → Server | 返回可用资源列表 |

## Python 实现

### 安装

```bash
pip install mcp
```

### 最小示例

```python
#!/usr/bin/env python3
"""自定义 MCP Server — 天气查询工具"""
import json
import sys
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent


app = Server("weather-server")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_weather",
            description="Get current weather for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    }
                },
                "required": ["city"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_weather":
        city = arguments["city"]
        # 实际项目中这里调用天气 API
        return [TextContent(
            type="text",
            text=f"Weather in {city}: Sunny, 22°C"
        )]
    raise ValueError(f"Unknown tool: {name}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(stdio_server(app))
```

### 配置使用

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["path/to/weather_server.py"]
    }
  }
}
```

## 进阶示例：数据库查询 Server

```python
#!/usr/bin/env python3
"""自定义 MCP Server — 内部业务数据查询"""
import os
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent
import psycopg2

app = Server("business-data")
DB_URL = os.environ["DATABASE_URL"]


def query_db(sql: str, params: tuple = ()) -> list[dict]:
    """执行只读查询"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(sql, params)
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="search_customers",
            description="Search customers by name or email pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_order_summary",
            description="Get order summary for a date range",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "format": "date"},
                    "end_date": {"type": "string", "format": "date"}
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="get_table_schema",
            description="Get the schema of a database table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"}
                },
                "required": ["table_name"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "search_customers":
        query = f"%{arguments['query']}%"
        limit = arguments.get("limit", 10)
        rows = query_db(
            "SELECT id, name, email FROM customers WHERE name ILIKE %s OR email ILIKE %s LIMIT %s",
            (query, query, limit)
        )
        return [TextContent(type="text", text=json.dumps(rows, indent=2, default=str))]

    if name == "get_order_summary":
        rows = query_db(
            """SELECT date(created_at) as date, COUNT(*) as orders, SUM(amount) as revenue
               FROM orders WHERE created_at BETWEEN %s AND %s
               GROUP BY date(created_at) ORDER BY date""",
            (arguments["start_date"], arguments["end_date"])
        )
        return [TextContent(type="text", text=json.dumps(rows, indent=2, default=str))]

    if name == "get_table_schema":
        rows = query_db(
            """SELECT column_name, data_type, is_nullable
               FROM information_schema.columns WHERE table_name = %s
               ORDER BY ordinal_position""",
            (arguments["table_name"],)
        )
        return [TextContent(type="text", text=json.dumps(rows, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


if __name__ == "__main__":
    import asyncio, json
    asyncio.run(stdio_server(app))
```

## Node.js 实现

```javascript
#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new McpServer({
  name: "my-custom-server",
  version: "1.0.0"
});

server.tool("get_time", "Get current server time", {}, async () => {
  return {
    content: [{ type: "text", text: new Date().toISOString() }]
  };
});

server.tool("calculate", "Perform a calculation", {
  expression: { type: "string", description: "Math expression" }
}, async ({ expression }) => {
  try {
    const result = eval(expression);
    return {
      content: [{ type: "text", text: `${expression} = ${result}` }]
    };
  } catch (e) {
    return {
      content: [{ type: "text", text: `Error: ${e.message}` }],
      isError: true
    };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

## 设计最佳实践

### 1. 工具命名

```
好: search_customers, get_order_summary, create_issue
差: f1, do_thing, helper
```

### 2. 清晰的 Description

description 是 Claude 决定是否使用该工具的关键信息：

```python
# 好
Tool(
    name="get_error_logs",
    description="Get recent error logs from the production server for debugging. Use when investigating production incidents or errors.",
    ...
)

# 差
Tool(
    name="logs",
    description="Get logs",
    ...
)
```

### 3. 错误处理

```python
@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        # ... tool logic ...
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error executing {name}: {str(e)}"
        )]
```

### 4. 安全原则

- **输入验证**：检查所有用户输入
- **权限最小化**：工具只做必要的事
- **SQL 参数化**：永远不要拼接 SQL
- **敏感信息**：不记录凭据和 token
- **网络访问**：只访问预期的内部服务

### 5. 响应格式

```python
# 结构化文本，便于 Claude 理解
text = json.dumps({
    "status": "success",
    "data": rows,
    "count": len(rows)
}, indent=2)
```

## 调试

```bash
# 测试 MCP Server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python my_server.py

# 测试工具调用
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_weather","arguments":{"city":"Beijing"}}}' | python my_server.py
```

## 实践练习

1. 用 Python 编写一个天气查询 MCP Server
2. 实现一个包含 3 个自定义工具的业务数据查询 Server
3. 在 Claude Code 中配置并使用你编写的 Server
4. 为你的 Server 添加错误处理和输入验证
