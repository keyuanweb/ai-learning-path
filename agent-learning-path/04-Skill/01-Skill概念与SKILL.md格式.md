# Skill 概念与 SKILL.md 格式

## 什么是 Skill

Skill 是 LangChain/LangGraph 2026 年的核心新范式。它封装了**可复用的操作知识**——不只定义"能做什么"（Tool），更定义了"怎么做"（方法流程）。

### Tool → Skill → Agent 三层架构

| 层级 | 角色 | 类比 | 自主性 |
|------|------|------|--------|
| **Tool** | 被动执行器，单一功能 | 厨师的刀具、锅 | 零自主 |
| **Skill** | 可复用的方法，编排多个 Tool | 厨师的烹饪技法（爆炒、清蒸） | 简单流程 |
| **Agent** | 全局决策者，拆解目标、调度 Skill | 厨师的大脑 | 完全自主 |

```python
# Tool：单一功能
@tool
def web_search(query: str) -> str:
    """搜索互联网"""
    return search_api.search(query)

# Skill：编排多个 Tool 完成特定任务的方法
# arxiv_research_skill:
#   1. web_search("site:arxiv.org {query}")
#   2. fetch_paper_details(urls)
#   3. summarize_findings(papers)

# Agent：决策调度
# "帮我调研 X 领域" → 分解 → 调用 arxiv_research_skill + data_analysis_skill
```

## SKILL.md 标准格式

Skill 由 `SKILL.md` + 可选的 `scripts/`、`references/`、`assets/` 组成。它已成为行业标准格式（CrewAI、Claude Agent SDK、LangChain 均支持）。

### 目录结构

```
skills/arxiv-research/
├── SKILL.md              # 核心定义（YAML frontmatter + Markdown 正文）
├── scripts/
│   └── fetch_papers.py   # 辅助脚本
└── references/
    └── arxiv_api.md      # 参考资料
```

### SKILL.md 完整示例

```markdown
---
name: arxiv-research
description: |
  在 ArXiv 上搜索最新学术论文，获取详情并生成结构化摘要。
  当用户需要查找学术文献、进行文献综述时使用此 Skill。
allowed-tools:
  - web_search
  - fetch_url
parameters:
  - name: query
    type: string
    description: 搜索关键词
    required: true
  - name: max_results
    type: integer
    description: 最大结果数
    default: 5
output:
  type: json
  description: 包含标题、作者、摘要、链接的论文列表
---

# ArXiv 论文研究 Skill

## 执行流程

### 步骤 1：搜索论文
使用 `web_search` 工具在 arxiv.org 搜索，查询格式：
```
site:arxiv.org {query}
```

### 步骤 2：获取详情
对搜索结果中的每个链接，使用 `fetch_url` 获取论文详情页。

### 步骤 3：生成摘要
对每篇论文提取：
- 标题
- 作者列表
- 发表时间
- 核心方法（1-2 句话）
- 主要发现（1-2 句话）

## 输出格式

返回 JSON 数组：
```json
[
  {
    "title": "...",
    "authors": ["..."],
    "published": "YYYY-MM-DD",
    "method": "...",
    "findings": "...",
    "url": "..."
  }
]
```

## 注意事项
- 如果搜索结果为空，尝试用英文关键词重试
- 优先返回 2024-2026 年的论文
- 摘要需要翻译为中文
```

### Frontmatter 字段说明

| 字段 | 必须 | 说明 |
|------|------|------|
| `name` | ✅ | Skill 唯一标识，必须小写，用 `-` 连接 |
| `description` | ✅ | 何时使用此 Skill，评估相关性的依据 |
| `allowed-tools` | 推荐 | 此 Skill 可用的工具白名单 |
| `parameters` | 可选 | 入参 Schema，会转为 JSON Schema 传给 LLM |
| `output` | 可选 | 输出格式说明 |
| `version` | 可选 | 语义化版本号 |

## Skill vs Agent vs MCP 选型

```
你的需求是什么？
├── 单一功能（搜索/计算/读文件） → Tool
├── 固定流程的多步骤任务 → Skill
│   ├── 需要外部服务连接 → Skill + MCP Server
│   └── 纯内部逻辑 → Skill
├── 需要自主决策的开放任务 → Agent
│   ├── 单一领域 → 单 Agent + Skills
│   └── 多领域协作 → 多 Agent + Skills
└── 工具/服务标准化接入 → MCP Server
```

## 实践练习

1. 为你常用的一个工具编写 SKILL.md（如 SQL 查询、文件处理）
2. 对比一个操作在 Tool 形式 vs Skill 形式下的实现差异
3. 设计一个包含 3 个步骤以上的 Skill 流程
