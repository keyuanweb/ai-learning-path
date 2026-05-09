# Deep Agent 与 Skills 集成

## 什么是 Deep Agent

Deep Agent 是 LangChain v1.0 推出的**高级智能体运行框架**，内建对 Skills 的一等支持。解决传统 Agent 在长任务中容易出错或卡住的问题。

### 核心能力

- **自动规划**：将大任务拆解为子任务
- **多步推理**：理解 → 计划 → 执行 → 调整 的迭代模式
- **Skill 调度**：主 Agent 可按需加载和调用多个 Skill
- **中间件扩展**：通过 Middleware 拦截和定制模型调用

## 安装

```bash
pip install langchain-core langchain langchain-community deepagents
```

## create_deep_agent 基础用法

```python
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

model = init_chat_model(model="gpt-4o")

agent = create_deep_agent(
    model=model,
    backend=LocalShellBackend(
        root_dir=".",
        virtual_mode=True       # True: 模拟执行, False: 真实执行
    ),
    skills=["./skills"],        # 指向 Skill 目录
    checkpointer=InMemorySaver(),
    system_prompt="你是一个科研助手，能帮用户查找学术论文。",
)

# 调用
result = agent.invoke(
    {"messages": [{"role": "user", "content": "找三篇关于 LangGraph Agent 的最新论文"}]},
    config={"configurable": {"thread_id": "session-1"}}
)

print(result["messages"][-1].content)
```

## 关键参数详解

| 参数 | 说明 | 示例 |
|------|------|------|
| `skills` | Skill 目录路径列表，支持多来源 | `["./skills", "/shared/skills"]` |
| `backend` | 本地执行后端，`LocalShellBackend` 是加载本地 Skill 的核心 | `LocalShellBackend(root_dir=".")` |
| `checkpointer` | 持久化记忆，生产环境用 PostgresSaver | `InMemorySaver()` |
| `middleware` | 自定义中间件列表 | `[SummarizationMiddleware()]` |
| `system_prompt` | 系统提示词 | 描述 Agent 的角色和能力 |
| `tools` | 除 Skills 外的全局工具 | `[web_search, calculator]` |

## 完整实战：科研助手 Agent

### 项目结构

```
research-assistant/
├── agent.py
├── skills/
│   ├── arxiv-search/
│   │   ├── SKILL.md
│   │   └── search.py
│   ├── paper-analyzer/
│   │   └── SKILL.md
│   └── citation-formatter/
│       └── SKILL.md
└── data/
    └── papers.json
```

### agent.py

```python
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import SummarizationMiddleware

model = init_chat_model(model="gpt-4o")

agent = create_deep_agent(
    model=model,
    backend=LocalShellBackend(
        root_dir="./data",
        virtual_mode=False
    ),
    skills=["./skills"],
    checkpointer=InMemorySaver(),
    middleware=[
        SummarizationMiddleware(max_tokens=8000),  # 长对话自动摘要
    ],
    system_prompt="""你是一个专业的科研助手。

能力：
1. 搜索 ArXiv 上的最新学术论文
2. 分析论文的方法、创新点和局限性
3. 格式化引用（APA/MLA/Chicago）

工作流程：
- 先搜索相关论文
- 逐一分析关键论文
- 最后输出格式化的文献综述和引用列表""",
)

# 交互式使用
config = {"configurable": {"thread_id": "research-1"}}

while True:
    query = input("\n> ")
    if query.lower() in ("exit", "quit"):
        break

    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config=config
    )
    print(f"\n{result['messages'][-1].content}")
```

## Skills 与常规 Tool 的混合使用

```python
from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """安全计算数学表达式"""
    return str(eval(expression))

@tool
def get_current_date() -> str:
    """获取当前日期"""
    from datetime import date
    return date.today().isoformat()

agent = create_deep_agent(
    model=model,
    backend=LocalShellBackend(root_dir="."),
    skills=["./skills"],
    tools=[calculator, get_current_date],   # 全局工具 + Skills
    system_prompt="你是一个全能助手，可以搜索论文、计算和分析数据。",
)
```

## Backend 配置

### LocalShellBackend

```python
from deepagents.backends import LocalShellBackend

backend = LocalShellBackend(
    root_dir="./workspace",     # 工作根目录
    virtual_mode=True,           # True: 只模拟，不真执行
    allowed_commands=[           # 允许的命令白名单
        "python", "pip", "ls", "cat", "mkdir"
    ],
    timeout=300,                 # 命令超时（秒）
)
```

### 自定义 Backend

```python
from deepagents.backends import BaseBackend

class SandboxBackend(BaseBackend):
    """在 Docker 沙箱中执行"""

    def run_command(self, cmd: str) -> str:
        # 在隔离容器中执行
        ...

    def read_file(self, path: str) -> str:
        # 从沙箱读取文件
        ...

    def write_file(self, path: str, content: str):
        # 写入沙箱文件系统
        ...
```

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| Skill 未被加载 | `SKILL.md` 格式错误 | 确保 YAML frontmatter 以 `---` 包裹 |
| 调用 Skill 报错 | 参数名与定义不一致 | 检查 `parameters` 字段与脚本参数匹配 |
| **大写文件夹不识别** | Deep Agent 限制 | **Skill 文件夹名必须全小写** |
| 执行超时 | 任务耗时过长 | 增大 `timeout` 或拆分 Skill |

## 成果数据

### LangChain 官方基准测试（2026.3）

| 指标 | 无 Skills | 有 Skills | 提升 |
|------|-----------|-----------|------|
| Claude Code 任务通过率 | 29% | **95%** | +66% |
| 平均 Token 消耗 | 基准 | -40% | 渐进式披露 |
| 工具选择准确率 | 基准 | +50% | 上下文更聚焦 |

## 实践练习

1. 用 `create_deep_agent` 创建一个带 2 个以上 Skill 的 Agent
2. 对比 `virtual_mode=True` vs `False` 的行为差异
3. 为一个 Deep Agent 添加 `SummarizationMiddleware`，测试长对话稳定性
