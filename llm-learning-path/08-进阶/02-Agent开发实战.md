# Agent 开发实战

Agent 是大模型从"聊天工具"进化为"自主行动系统"的跳跃。它让模型不只是说，还能做——调 API、查数据库、发邮件、运行代码。

---

## 1. Agent 解决什么问题

### 传统 LLM 的局限

- 不能获取实时信息（不知道今天的天气）
- 不能执行操作（不能发邮件、不能改数据库）
- 回答可能过时或错误（幻觉）

### Agent 的核心思路

> 给 LLM 一个工具箱，让它自己决定什么时候用哪个工具、怎么用，观察结果后决定下一步。

```
用户: "帮我查一下今天北京的天气，如果下雨就给我发邮件提醒"
  ↓
Agent 思考: 需要先查天气 → 调用天气 API → 结果: 晴 → 不需要发邮件 → 回复用户
```

---

## 2. ReAct 模式：思考 + 行动

### 核心范式

ReAct = Reasoning（思考）+ Action（行动），交替进行。这是目前最广泛使用的 Agent 模式。

```
Thought: 我需要知道今天的日期和北京天气
Action: get_weather(city="北京")
Observation: 2026-05-09, 晴, 25°C

Thought: 天气是晴，不需要发邮件
Action: 不需要
Final Answer: 今天北京是晴天，25°C，不需要带伞，也不需要发邮件提醒。
```

### 为什么叫 ReAct

传统方法是先思考完再行动（思考→计划→执行→完成）。ReAct 是**边想边做**——每一步观察结果，调整下一步行动。这让 Agent 能应对不确定性。

### 最简单的 ReAct Agent 实现

```python
def react_agent(user_query, tools, llm, max_steps=10):
    prompt = f"用户: {user_query}\n请逐步解决。"
    for step in range(max_steps):
        response = llm.generate(prompt)
        
        if "Final Answer:" in response:
            return response.split("Final Answer:")[1]

        if "Action:" in response:
            action = parse_action(response)
            result = execute_tool(action, tools)
            prompt += f"\nObservation: {result}\n下一步:"
    
    return "达到最大步数，未能完成任务"
```

---

## 3. Tool Calling (Function Calling)

### 跟 ReAct 的关系

ReAct 是一种**提示策略**，教 LLM 怎么思考和行动。Tool Calling 是一种**底层机制**——LLM 输出的不是文本而是结构化的函数调用请求。

```python
# 定义工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"}
                },
                "required": ["city"]
            }
        }
    }
]

# LLM 直接输出函数调用
response = llm.chat(
    messages=[{"role": "user", "content": "北京天气怎么样？"}],
    tools=tools,
    tool_choice="auto"
)
# response: {"name": "get_weather", "arguments": {"city": "北京"}}

# 执行工具并回传结果
result = execute(response.function)
llm.chat(messages=... + [{"role": "tool", "content": result}])
```

**Tool Calling vs ReAct**：Tool Calling 依赖模型本身的函数调用能力（需要模型在训练时见过这类格式）。ReAct 是纯 prompt 驱动的，不依赖特殊训练。

---

## 4. 多 Agent 协作

### 单 Agent 的局限

一个 Agent 处理所有事情 → 上下文太长、容易分心、一个任务变复杂就开始出错。

### 多 Agent 模式

```
编排 Agent (Orchestrator)
  ├── 搜索 Agent: 专门做信息检索
  ├── 代码 Agent: 专门写和执行代码  
  ├── 分析 Agent: 专门做数据分析和总结
  └── 写作 Agent: 专门写最终报告
```

### LLM 生态的主要多 Agent 框架

| 框架 | 特点 |
|------|------|
| **AutoGen** (Microsoft) | 多 Agent 对话，Agent 间可以相互调用 |
| **CrewAI** | 角色定义清晰，适合固定分工的团队 |
| **LangGraph** | 图结构定义 Agent 协作流程，最灵活 |
| **Swarm** (OpenAI) | 轻量级，Agent 间可以 transfer |

---

## 5. Agent 的关键挑战

### 可靠性

Agent 每一步都可能出错——工具调用格式错误、选了错误的工具、陷入循环。需要防御措施：
- **最大步数限制**：防无限循环
- **超时机制**：单个工具调用超时
- **验证层**：检查工具输出是否合理再传给 LLM

### 成本

每次 ReAct 循环意味着额外一次 LLM 调用。如果平均 5 步完成任务，成本是单次调用的 5 倍。

### 安全

Agent 能执行操作 → 需要权限控制：
- 只读工具（搜索、查数据库）→ 低风险
- 写入工具（发邮件、改库）→ 高风险，需要 Human-in-the-Loop 确认

---

## 6. 从 Demo 到生产

| 阶段 | 关键 |
|------|------|
| **Demo** | ReAct + 少量工具，能跑就行 |
| **MVP** | 加错误恢复 + 重试 + 降级 |
| **生产** | 多 Agent 协作 + 权限控制 + 监控 + 成本追踪 |

**2025 年的共识**：单 Agent + Tool Calling 已经足够解决 80% 的问题。多 Agent 只在确实有必要分拆任务时使用——不要过度设计。

---

## 本章速查

| 概念 | 一句话 |
|------|--------|
| **Agent** | LLM + 工具箱 + 自主决策 |
| **ReAct** | 思考→行动→观察→循环 |
| **Tool Calling** | LLM 输出结构化的函数调用 |
| **多 Agent** | 分拆任务给专门的 Agent 协作完成 |
| **核心框架** | LangGraph、AutoGen、CrewAI |
