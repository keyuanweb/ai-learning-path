# Hierarchical 多 Agent 模式

## 模式概述

Hierarchical（层级化）模式是 Supervisor 模式的自然扩展。当任务规模大到单一 Supervisor 难以管理时，引入**多层级管理结构**。

```
                     ┌──→ Research Supervisor ──→ [Web 搜索, 数据分析]
Top Supervisor ──────┤
                     ├──→ Engineering Supervisor → [前端, 后端, 架构]
                     │
                     └──→ Quality Supervisor ────→ [代码审查, 测试]
```

### 与平级 Supervisor 的对比

| 维度 | 平级 Supervisor | 层级化 Supervisor |
|------|----------------|-------------------|
| Agent 数量 | 3-7 | 10+（分组管理） |
| 路由复杂度 | 低 | 高（需要分层路由） |
| 上下文管理 | 所有 Worker 平级 | 各团队独立上下文 |
| 可扩展性 | 线性扩展 | 树状扩展 |
| 适用场景 | 中小团队 | 大型企业系统 |

## 模型分层策略

```python
from langchain_openai import ChatOpenAI

# 模型分层：越上层用越强的模型
models = {
    "top_supervisor": ChatOpenAI(model="gpt-4o"),           # 战略决策
    "team_supervisor": ChatOpenAI(model="gpt-4o-mini"),     # 团队协调
    "worker": ChatOpenAI(model="gpt-4o-mini"),              # 具体执行
}
```

推荐的分层策略（搭配 LiteLLM 可灵活切换）：

| 层级 | 推荐模型 | 责任 |
|------|----------|------|
| **Top Supervisor** | gpt-4o / claude-sonnet-4-6 | 总体策略、任务分解、最终质量把关 |
| **Team Supervisor** | gpt-4o-mini | 团队内部任务分配、结果汇总 |
| **Worker Agent** | gpt-4o-mini | 执行具体任务（搜索/编码/分析） |

## LangGraph 实现

```python
from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor
from langchain_openai import ChatOpenAI

# ── 模型分层 ──
top_model = ChatOpenAI(model="gpt-4o")
team_model = ChatOpenAI(model="gpt-4o-mini")
worker_model = ChatOpenAI(model="gpt-4o-mini")

# ── Worker Agent 层 ──
web_search_agent = create_agent(
    model=worker_model, tools=[web_search],
    name="web_searcher",
    system_prompt="你是 Web 搜索专家。使用 web_search 工具搜索信息。"
)

data_analyst_agent = create_agent(
    model=worker_model, tools=[python_repl, database_query],
    name="data_analyst",
    system_prompt="你是数据分析师。编写代码分析数据并可视化。"
)

frontend_dev_agent = create_agent(
    model=worker_model, tools=[file_writer, npm_runner],
    name="frontend_dev",
    system_prompt="你是前端开发者。使用 React 实现 UI 组件。"
)

backend_dev_agent = create_agent(
    model=worker_model, tools=[file_writer, api_designer],
    name="backend_dev",
    system_prompt="你是后端开发者。设计 REST API 和数据库模型。"
)

# ── Team Supervisor 层 ──
research_team = create_supervisor(
    agents=[web_search_agent, data_analyst_agent],
    model=team_model,
    prompt="你是研究团队主管。将研究问题分派给 web_searcher 或 data_analyst。",
    output_mode="last"
)

engineering_team = create_supervisor(
    agents=[frontend_dev_agent, backend_dev_agent],
    model=team_model,
    prompt="你是工程团队主管。协调前端和后端开发工作。",
    output_mode="last"
)

# ── Top Supervisor ──
class ProjectState(MessagesState):
    research_output: str
    engineering_output: str
    final_deliverable: str

def research_pipeline(state: ProjectState) -> dict:
    """将研究任务交给研究团队"""
    result = research_team.invoke({
        "messages": [{"role": "user", "content": state["messages"][-1].content}]
    })
    return {"research_output": result["messages"][-1].content}

def engineering_pipeline(state: ProjectState) -> dict:
    """将开发任务交给工程团队（基于研究成果）"""
    prompt = f"基于以下研究成果，实现技术方案：\n{state.get('research_output', '')}"
    result = engineering_team.invoke({
        "messages": [{"role": "user", "content": prompt}]
    })
    return {"engineering_output": result["messages"][-1].content}

def top_supervisor_router(state: ProjectState) -> str:
    """Top Supervisor 决定先做研究还是先开发"""
    query = state["messages"][-1].content

    prompt = f"""用户需求：{query}

决定执行顺序：
- 如果需求不明确或需要市场调研 → research_first
- 如果需求明确，可以直接开发 → engineering_first
- 如果研究和开发都已完成 → synthesize"""

    response = top_model.invoke(prompt).content.strip().lower()

    if "synthesize" in response:
        return "synthesize"
    if "engineering" in response:
        return "engineering"
    return "research"

def synthesize(state: ProjectState) -> dict:
    """最终综合：将研究成果和工程输出合并"""
    prompt = f"""研究成果：{state.get('research_output', 'N/A')}
工程输出：{state.get('engineering_output', 'N/A')}

生成最终项目交付文档，包括技术方案、架构设计和实现要点。"""

    deliverable = top_model.invoke(prompt).content
    return {"final_deliverable": deliverable}

# ── 构建 Top-level Graph ──
builder = StateGraph(ProjectState)
builder.add_node("research", research_pipeline)
builder.add_node("engineering", engineering_pipeline)
builder.add_node("synthesize", synthesize)

builder.add_edge(START, "research")
builder.add_edge("research", "engineering")
builder.add_edge("engineering", "synthesize")
builder.add_edge("synthesize", END)

hierarchical_app = builder.compile()
```

## 子图嵌套技术

除了通过函数调用嵌套，也可以使用 LangGraph 的 Subgraph 机制：

```python
# 将团队编译为子图
research_subgraph = research_team.compile()

# 在主图中作为子图节点引用
builder.add_node("research_team", research_subgraph)
```

## 上下文隔离策略

层级化架构的优势是**上下文隔离**：

```python
def run_isolated_team(team, task: str, parent_context: str) -> str:
    """在隔离的上下文中运行团队任务

    团队只看到：
    1. 任务描述
    2. 必要的父级上下文摘要（而非完整对话历史）
    """
    # 压缩父级上下文
    summary_prompt = f"将以下上下文压缩为关键信息：\n{parent_context}"
    condensed = top_model.invoke(summary_prompt).content

    # 团队在隔离上下文中运行
    result = team.invoke({
        "messages": [{
            "role": "user",
            "content": f"任务：{task}\n\n背景信息：{condensed}"
        }]
    })
    return result["messages"][-1].content
```

## 实践练习

1. 设计一个电商平台的层级 Agent 架构（Top → 商品/订单/用户三个团队）
2. 实现上下文隔离：Worker 只接收压缩后的任务描述
3. 对比平级 Supervisor 和层级化架构在处理 6+ Worker 时的效率
