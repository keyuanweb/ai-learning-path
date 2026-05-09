# Swarm 多 Agent 模式

## 模式概述

Swarm（蚁群）模式是一种**去中心化**的多 Agent 架构。没有中心 Supervisor，Agent 之间通过 **Handoff 直接交接**控制权。State 中跟踪 "current_agent" 来决定谁在处理。

```
User → Support Agent → (handoff) → Billing Agent → (handoff) → Tech Agent → User
                        ← (handoff)               ← (handoff)
```

### 三种多 Agent 模式对比

| 维度 | Supervisor | Hierarchical | Swarm |
|------|-----------|-------------|-------|
| 控制方式 | 中心化 | 层级中心化 | 去中心化 |
| 路由决策 | Supervisor | 各级 Supervisor | 各 Agent 自主 |
| 适用场景 | 项目协作 | 大型组织 | 客服、服务台 |
| 优势 | 可控性好 | 可扩展 | 延迟低、灵活 |
| 劣势 | 瓶颈风险 | 复杂度高 | 可能循环 |

## LangGraph Swarm 实现

### 核心要素

```python
from typing import TypedDict, Annotated, Literal
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_openai import ChatOpenAI

# State 中追踪当前活跃的 Agent
class SwarmState(MessagesState):
    current_agent: str
    handoff_history: Annotated[list[str], operator.add]

llm = ChatOpenAI(model="gpt-4o-mini")
```

### 定义 Agent 及其 Handoff 工具

```python
# 每个 Agent 定义为返回 Command 的函数

AGENT_PROMPTS = {
    "triage": """你是客服分流员（Triage Agent）。
根据用户问题决定转交给谁：
- 账单/付款/退款 → transfer_to_billing
- 技术问题/Bug/报错 → transfer_to_technical
- 账号/登录/密码 → transfer_to_account
- 简单问题直接回答""",

    "billing": """你是账单专员（Billing Agent）。
处理账单、付款、退款、订阅相关问题。
如果问题不属于账单范畴，转回 triage。""",

    "technical": """你是技术支持（Technical Agent）。
处理产品 Bug、报错信息、功能使用问题。
如果问题涉及账户操作，转交 account agent。""",

    "account": """你是账户专员（Account Agent）。
处理账号设置、登录问题、密码重置、权限管理。
如果问题不在你的范围内，转回 triage。"""
}

def make_agent(name: str):
    """创建 Agent 节点函数"""

    # 为每个 Agent 创建到其他 Agent 的 handoff 工具
    other_agents = [a for a in AGENT_PROMPTS.keys() if a != name]

    handoff_tools = []
    for other in other_agents:
        # 使用闭包创建 handoff 函数
        def make_handoff(target: str):
            def handoff(reason: str) -> str:
                """将对话转交给另一个 Agent。"""
                return f"HANDOFF_TO_{target}: {reason}"
            handoff.__name__ = f"transfer_to_{target}"
            return handoff
        handoff_tools.append(make_handoff(other))

    def agent_node(state: SwarmState) -> Command:
        # 构建带 handoff 工具的 LLM
        agent_llm = llm.bind_tools(handoff_tools)
        system_prompt = AGENT_PROMPTS[name]

        response = agent_llm.invoke([
            {"role": "system", "content": system_prompt},
            *state["messages"]
        ])

        # 检查是否有 handoff 请求
        if response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc["name"]
                if tool_name.startswith("transfer_to_"):
                    target = tool_name.replace("transfer_to_", "")
                    return Command(
                        goto=target,
                        update={
                            "messages": [response],
                            "current_agent": target,
                            "handoff_history": [f"{name} → {target}: {tc['args'].get('reason', 'N/A')}"]
                        }
                    )

        # 没有 handoff → 返回给用户
        return Command(
            goto=END,
            update={
                "messages": [response],
                "current_agent": name
            }
        )

    return agent_node

# ── 构建 Swarm Graph ──
builder = StateGraph(SwarmState)

# 注册所有 Agent 节点
agents = {}
for name in AGENT_PROMPTS:
    agents[name] = make_agent(name)
    builder.add_node(name, agents[name])

# 所有 Agent 都可以路由到其他 Agent 或 END
# 使用条件边检查 current_agent
builder.add_edge(START, "triage")  # 入口总是 triage

# 每个 Agent 通过 Command(goto=...) 动态路由
# 所以只需要声明可能存在边即可（LangGraph 允许动态 goto）

swarm_app = builder.compile()
```

## 简化的 Swarm 实现（使用 Handoff 函数）

```python
def create_swarm(agents: dict[str, callable], entry_agent: str = "triage"):
    """创建 Swarm 多 Agent 系统

    agents: {"agent_name": agent_function, ...}
    每个 agent 返回 Command(goto=target, update=...)
    """

    builder = StateGraph(SwarmState)

    for name, agent_fn in agents.items():
        builder.add_node(name, agent_fn)

    builder.add_edge(START, entry_agent)
    # 所有 agent 可以到达任何其他 agent（通过 Command）
    # 也可以到达 END

    return builder.compile()
```

## 避免死循环

```python
MAX_HANDOFFS = 5

def agent_with_loop_guard(name: str, max_handoffs: int = MAX_HANDOFFS):
    def wrapped(state: SwarmState) -> Command:
        handoff_count = len(state.get("handoff_history", []))

        if handoff_count >= max_handoffs:
            # 强制终止，要求人工介入
            return Command(
                goto=END,
                update={
                    "messages": [{
                        "role": "assistant",
                        "content": "抱歉，我需要将您的问题升级给人工客服处理。请稍候。"
                    }],
                    "current_agent": "human_escalation"
                }
            )

        return original_agent(state)
    return wrapped
```

## Swarm vs Supervisor 选择指南

```
你的 Agent 之间是否有清晰的职责边界？
├── 是 → 任务是否通常由单个 Agent 完成？
│   ├── 是 → 使用 Swarm 模式
│   └── 否 → 是否需要一个中心协调者来保证质量？
│       ├── 是 → 使用 Supervisor 模式
│       └── 否 → 使用 Swarm + 简单路由
└── 否 → 是否需要多轮协作？
    ├── 是 → 使用 Supervisor 模式
    └── 否 → 使用 Router Agent（单 Agent 多分支）
```

## 实践练习

1. 实现一个 4 Agent 的客服 Swarm（triage、billing、technical、account）
2. 为 Swarm 添加"最多 5 次 handoff"的防循环机制
3. 对比同一个客服场景在 Swarm 和 Supervisor 模式下的延迟和用户满意度
