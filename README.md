# AI 学习路径合集

AI 技术学习文档，涵盖 Claude Code 工具链、大模型原理、推理引擎源码、Agent 框架、多模态推理等方向。

## 学习路径总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                         AI 学习路径全景                                │
├────────────────┬─────────────────────────────────────────────────────┤
│   LLM 理论基础  │  Transformer 原理 → 训练/微调 → 推理优化 → 进阶       │
│   vLLM 推理引擎 │  引擎入口 → 主循环 → 调度/KV缓存 → Attention 后端      │
│   vLLM-Omni    │  多阶段流水线 → AR/Diffusion 双引擎 → OmniConnector   │
│   Agent 框架    │  LangChain → LangGraph → RAG → 多Agent → 生产部署     │
│   Hermes Agent │  Agent 核心循环 → 工具系统 → 记忆/技能 → 多平台接入    │
│   Claude Code  │  CLI 交互 → Tools/Skills/Hooks → MCP → Agent SDK     │
└────────────────┴─────────────────────────────────────────────────────┘
```

---

## 各学习路径详情

### 1. [LLM 理论基础](llm-learning-path/)

从零开始系统学习大语言模型原理，覆盖数学基础到工业级案例。

| 阶段 | 内容 | 阶段 | 内容 |
|------|------|------|------|
| 00 | Python、线代、概率、PyTorch 前置 | 05 | 推理优化技术 |
| 01 | Transformer 核心原理 | 06 | 量化/蒸馏/加速 |
| 02 | GPT/LLaMA 等大模型架构 | 07 | 主流模型对比分析 |
| 03 | 预训练全流程 | 08 | 前沿进阶主题 |
| 04 | SFT/RLHF/DPO 微调 | 09 | 高级专题 |

### 2. [vLLM 源码学习](vllm-learning-path/)

通读 vLLM (v0.20.0) 源码，理解生产级 LLM 推理引擎的内部实现。

| 阶段 | 内容 | 学时 |
|------|------|------|
| 00 | [入口 — 找到正确入口，避开废弃代码](vllm-learning-path/00-入口/) | 15min |
| 01 | [用户API到引擎 — 从 LLM.generate() 追到引擎入口](vllm-learning-path/01-用户API到引擎/) | 2~3h |
| 02 | [V1引擎主循环 — EngineCore.step() 紧循环](vllm-learning-path/02-V1引擎主循环/) | 3~5h |
| 03 | [调度与KV缓存 — 调度器算法与 KV 块管理](vllm-learning-path/03-调度与KV缓存/) | 4~6h |
| 04 | [模型执行与采样 — GPUModelRunner 前向+采样](vllm-learning-path/04-模型执行与采样/) | 3~5h |
| 05 | [模型实现 — LLaMA/Qwen 等具体模型适配](vllm-learning-path/05-模型实现/) | 3~4h |
| 06 | [Attention后端 — FlashAttention/FlashInfer 等](vllm-learning-path/06-Attention后端/) | 2~3h |
| 07 | [高级特性 — Prefix Caching/Spec Decode/多模态](vllm-learning-path/07-高级特性/) | 3~5h |

> 源码位置：`code/vllm/`

### 3. [vLLM-Omni 源码学习](vllm-omni-learning-path/)

通读 vLLM-Omni 源码，理解多模态（文本/图像/视频/音频）推理引擎的多阶段流水线架构。

| 阶段 | 内容 | 学时 |
|------|------|------|
| 00 | [前置知识 — vLLM基础、全模态概念、扩散模型](vllm-omni-learning-path/00-前置知识/) | 1~2h |
| 01 | [项目总览与入口 — 符号地图、配置系统](vllm-omni-learning-path/01-项目总览与入口/) | 1~2h |
| 02 | [多阶段流水线核心 — Orchestrator、StagePool](vllm-omni-learning-path/02-多阶段流水线核心/) | 3~5h |
| 03 | [入口与API层 — Omni/AsyncOmni、OpenAI API](vllm-omni-learning-path/03-入口与API层/) | 2~3h |
| 04 | [自回归执行(AR Worker) — 文本生成调度与采样](vllm-omni-learning-path/04-自回归执行(AR%20Worker)/) | 3~4h |
| 05 | [扩散模型执行 — Diffusion Engine 图像/音频生成](vllm-omni-learning-path/05-扩散模型执行(Diffusion%20Engine)/) | 4~5h |
| 06 | [模型实现 — Qwen-Omni 等具体模型适配](vllm-omni-learning-path/06-模型实现/) | 2~3h |
| 07 | [分布式与OmniConnector — 跨Stage KV传输](vllm-omni-learning-path/07-分布式与OmniConnector/) | 2~3h |
| 08 | [高级特性 — 流式输出/批处理/性能调优](vllm-omni-learning-path/08-高级特性/) | 2~3h |

> 源码位置：`code/vllm-omni/`

### 4. [Agent 学习路径](agent-learning-path/)

系统掌握 LangChain + LangGraph 构建 AI Agent 的完整技术栈，从基础到工业级多 Agent 系统。

| 阶段 | 内容 | 学时 |
|------|------|------|
| 00 | [入口 — 学习路线总览](agent-learning-path/00-入口/) | 15min |
| 01 | [基础入门 — LangChain 核心概念、LCEL](agent-learning-path/01-入门/) | 3~5h |
| 02 | [LangGraph 核心 — StateGraph、条件分支、Checkpoint](agent-learning-path/02-图核心/) | 5~8h |
| 03 | [Agent 实战 — Tool Calling、create_agent、HITL](agent-learning-path/03-Agent/) | 5~8h |
| 04 | [Skill — SKILL.md 格式、Deep Agent、渐进式披露](agent-learning-path/04-Skill/) | 5~8h |
| 05 | [RAG + Agent 融合 — Corrective RAG、Agentic RAG](agent-learning-path/05-RAG/) | 5~8h |
| 06 | [多 Agent — Supervisor、Hierarchical、Swarm](agent-learning-path/06-多Agent/) | 8~12h |
| 07 | [生产部署 — LangSmith、LangGraph Platform、安全](agent-learning-path/07-生产部署/) | 5~8h |
| 08 | [工业级案例 — Kensho、Grab、Remote](agent-learning-path/08-案例/) | 3~5h |

### 5. [Hermes Agent 源码学习](hermes-learning-path/)

通读 Nous Research 的 Hermes Agent 源码，理解自进化 AI Agent 的完整架构——从 Agent 核心循环、工具系统、记忆/技能系统到多平台接入。

| 章节 | 内容 |
|------|------|
| [00-概述与架构总览](hermes-learning-path/00-概述与架构总览.md) | 项目定位、技术栈、结构总览 |
| [01-Agent核心循环](hermes-learning-path/01-Agent核心循环.md) | 主循环、模型交互、决策流 |
| [02-工具调用系统](hermes-learning-path/02-工具调用系统.md) | 内置工具、自定义工具、沙箱执行 |
| [03-多传输层适配](hermes-learning-path/03-多传输层适配.md) | 18+ 平台统一接入层 |
| [04-System Prompt构建](hermes-learning-path/04-System%20Prompt构建.md) | Prompt 组装、上下文注入 |
| [05-上下文压缩](hermes-learning-path/05-上下文压缩.md) | 自动摘要、对话修剪 |
| [06-记忆与技能系统](hermes-learning-path/06-记忆与技能系统.md) | FTS5 搜索、技能自进化 |
| [07-网关与多平台接入](hermes-learning-path/07-网关与多平台接入.md) | Telegram/Discord/Slack 等 |
| [08-高级特性](hermes-learning-path/08-高级特性.md) | 定时任务、语音、会话管理 |

> 源码位置：`code/hermes/`

### 6. [Claude Code 学习路径](claude-code-learning-path/)

系统掌握 Claude Code 的完整技术栈，从 CLI 交互式开发到企业级多 Agent 生产部署。

| 阶段 | 内容 |
|------|------|
| 00 | [入口 — 学习路线、环境搭建、核心概念、常用命令](claude-code-learning-path/00-入口/) |
| 01 | [项目记忆与配置 — CLAUDE.md、自定义命令、权限安全](claude-code-learning-path/01-项目记忆与配置/) |
| 02 | [Tools 工具系统 — 内置工具、任务管理、子代理](claude-code-learning-path/02-Tools工具系统/) |
| 03 | [Skills 技能系统 — Skill 格式、渐进式披露、Plugins](claude-code-learning-path/03-Skills技能系统/) |
| 04 | [Hooks 钩子系统 — 生命周期事件、命令/Prompt钩子](claude-code-learning-path/04-Hooks钩子系统/) |
| 05 | [MCP 协议集成 — MCP 原理、常用 Server、自定义开发](claude-code-learning-path/05-MCP协议集成/) |
| 06 | [Agent SDK 开发 — SDK 架构、交互式/自动化会话](claude-code-learning-path/06-Agent-SDK开发/) |
| 07 | [生产实践 — 多Agent协作、CI/CD、企业级治理](claude-code-learning-path/07-生产实践/) |

---

## 学习顺序建议

```
LLM 理论基础 (必学基础)
        │
        ├──→ vLLM 源码 ──→ vLLM-Omni 源码    (推理引擎路线)
        │
        ├──→ Agent 学习路径                     (Agent 应用路线)
        │
        ├──→ Hermes Agent 源码                  (Agent 框架路线)
        │
        └──→ Claude Code 学习路径               (Claude Code 工具路线)
```

- **推理引擎方向**：LLM 基础 → vLLM → vLLM-Omni
- **Agent 方向**：LLM 基础 → Agent → Hermes（想深挖框架实现）
- **工具方向**：已有开发经验 → Claude Code → Agent SDK 开发
