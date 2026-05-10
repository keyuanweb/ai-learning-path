# 常用 MCP Server 实战

## GitHub MCP Server

最常用的 MCP Server，让 Claude Code 直接操作 GitHub Issues、PR、仓库等。

### 安装与配置

```bash
claude mcp add github -- npx -y @modelcontextprotocol/server-github
```

需要设置 `GITHUB_PERSONAL_ACCESS_TOKEN` 环境变量：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxx"
      }
    }
  }
}
```

### 典型使用

```bash
# 搜索 Issues
"找出所有标记为 bug 且分配给我的 issue"

# 创建 PR
"为当前分支创建一个 PR，标题描述这个重构"

# 代码审查
"审查 PR #123 的改动，重点看安全问题"

# 管理 Issues
"把 Issue #45 的状态更新为已关闭"
```

### 常用工具

| 工具 | 说明 |
|------|------|
| `search_issues` | 搜索 Issues |
| `create_issue` | 创建 Issue |
| `create_pull_request` | 创建 PR |
| `get_pull_request` | 获取 PR 详情 |
| `merge_pull_request` | 合并 PR |
| `search_code` | 搜索 GitHub 代码 |
| `get_file_contents` | 读取仓库文件 |

## Filesystem MCP Server

为 Claude 提供安全的文件系统访问能力，可用于项目目录之外的操作。

### 安装

```bash
claude mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem /path/to/allowed
```

### 配置（限制访问路径）

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/home/user/projects",
        "/home/user/documents"
      ]
    }
  }
}
```

### 使用场景

- 跨项目文件操作
- 读取日志文件
- 操作配置文件（不经过终端）

## Playwright MCP Server（浏览器自动化）

让 Claude 控制浏览器进行测试和抓取。

### 安装

```bash
claude mcp add playwright -- npx -y @anthropic/mcp-server-playwright
```

### 使用场景

- 截取网页截图
- 测试 Web 应用的交互流程
- 抓取 JavaScript 渲染的动态页面

```
"用 Playwright 打开 localhost:3000，截取首页并检查布局"
```

## Context7 MCP Server

提供实时、最新的库文档查询。

### 安装

```bash
claude mcp add context7 -- npx -y @upstash/context7-mcp
```

### 使用场景

```
"用 Context7 查一下 React 19 的 useOptimistic 最新用法"
"Next.js 15 的 Server Actions 有什么变化？"
```

## PostgreSQL MCP Server

直接查询数据库，理解数据结构和内容。

### 安装

```bash
claude mcp add postgres -- npx -y @anthropic/mcp-server-postgres
```

### 配置

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-postgres"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb"
      }
    }
  }
}
```

### 使用场景

```
"查看 users 表的 Schema 并解释各字段含义"
"找出最近一周创建的订单中金额最高的 10 个"
"帮我写一条迁移脚本：给 articles 表添加 tags 字段"
```

## 多 MCP Server 组合

实际项目中常需要多个 MCP Server 协同工作：

```mermaid
flowchart TD
    TASK["用户: 修复 Issue #42<br/>并部署到 staging"]
    TASK --> GH["GitHub MCP<br/>获取 Issue 详情"]
    TASK --> PG["PostgreSQL MCP<br/>查询相关数据"]
    TASK --> CTX["Context7 MCP<br/>查框架文档"]
    GH --> FIX["Claude 分析并修复"]
    PG --> FIX
    CTX --> FIX
    FIX --> PR["GitHub MCP<br/>创建 PR"]
    FIX --> TEST["Playwright MCP<br/>运行 E2E 测试"]
```

### 组合配置

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "..." }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-postgres"],
      "env": { "DATABASE_URL": "..." }
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-playwright"]
    }
  }
}
```

## MCP Server 性能考量

| 因素 | 影响 | 建议 |
|------|------|------|
| 工具数量 | 越多越消耗上下文 | 只安装需要的 Server |
| 响应时间 | 影响 Agent Loop 速度 | 设置合理超时 |
| 并发调用 | 多个 Server 可并行 | 独立 Server 互不阻塞 |
| 启动时间 | npm exec 有延迟 | 考虑使用 Python 实现的轻量 Server |

## 实践练习

1. 安装并配置 GitHub MCP Server，完成一个 Issue → PR 的完整流程
2. 安装 Playwright MCP Server，抓取一个 JS 渲染的页面
3. 配置 PostgreSQL MCP Server，通过对话分析数据库 Schema
4. 组合 3 个 MCP Server 完成一个完整的端到端任务
