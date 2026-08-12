# Skill 生产模式与案例

## 常见编排模式

### 1. Fan-out / Fan-in（扇出/扇入）

将一个任务分解为多个并行的子任务，完成后聚合结果。

```python
from langgraph.types import Send

class FanOutState(TypedDict):
    task: str
    subtasks: Annotated[list[dict], operator.add]
    results: Annotated[list[str], operator.add]
    final_output: str

def create_subtasks(state: FanOutState) -> dict:
    """将大任务分解为子任务"""
    llm = ChatOpenAI(model="gpt-4o-mini")
    prompt = f"""将以下任务分解为 3-6 个独立的子任务，每个子任务可由专门的 Skill 处理：

任务：{state['task']}

返回 JSON 列表：[{{"skill": "skill-name", "subtask": "子任务描述"}}]"""

    subtasks = json.loads(llm.invoke(prompt).content)
    return {"subtasks": subtasks}

def dispatch_to_skills(state: FanOutState) -> list[Send]:
    """Fan-out：每个子任务发送到对应的 Skill"""
    return [
        Send("execute_skill", {"subtask": st})
        for st in state["subtasks"]
    ]

def aggregate_results(state: FanOutState) -> dict:
    """Fan-in：聚合所有 Skill 的执行结果"""
    llm = ChatOpenAI(model="gpt-4o")
    results_text = "\n\n---\n\n".join(state.get("results", []))

    prompt = f"""基于以下并行执行的结果，生成一个综合分析报告：

原始任务：{state['task']}

子任务结果：
{results_text}

请整合信息，消除重复，解决矛盾，生成最终输出。"""

    return {"final_output": llm.invoke(prompt).content}
```

### 2. Map-Reduce

对大量数据逐一应用同一 Skill，然后汇总分析。

```python
class MapReduceState(TypedDict):
    documents: list[str]
    skill_name: str
    mapped: Annotated[list[str], operator.add]
    reduced: str

def map_documents(state: MapReduceState) -> list[Send]:
    """Map：对每篇文档应用同一 Skill"""
    return [
        Send("apply_skill", {
            "document": doc,
            "skill": state["skill_name"]
        })
        for doc in state["documents"]
    ]

def reduce(state: MapReduceState) -> dict:
    """Reduce：汇总所有文档的分析结果"""
    all_analyses = "\n\n---\n\n".join(state.get("mapped", []))

    llm = ChatOpenAI(model="gpt-4o-mini")
    prompt = f"""汇总以下 {len(state['mapped'])} 篇文档的分析结果：

{all_analyses[:8000]}

生成汇总报告，包含：
1. 共同主题和趋势
2. 独特发现
3. 矛盾或争议点"""

    return {"reduced": llm.invoke(prompt).content}
```

### 3. Chain with Fallback

链式执行 Skill，每个步骤有降级策略。

```python
class ChainWithFallbackState(TypedDict):
    query: str
    current_step: str
    step_results: dict
    fallback_triggered: bool
    final_output: str

SKILL_CHAIN = [
    {"name": "classify_intent", "fallback": "default_classifier"},
    {"name": "fetch_data", "fallback": "cached_data_fallback"},
    {"name": "analyze_data", "fallback": "basic_analysis"},
    {"name": "format_output", "fallback": "simple_format"},
]

def execute_with_fallback(state: ChainWithFallbackState) -> dict:
    """执行当前步骤，失败时使用降级 Skill"""
    step = SKILL_CHAIN[state["current_step"]]

    try:
        result = invoke_skill(step["name"], state["query"])
        if result["success"]:
            return {"step_results": {step["name"]: result}}

    except Exception as e:
        logger.warning(f"Skill {step['name']} 失败: {e}, 使用降级方案")

    # Fallback
    fallback_result = invoke_skill(step["fallback"], state["query"])
    return {
        "step_results": {step["name"]: fallback_result},
        "fallback_triggered": True
    }
```

### 4. Human-in-the-Loop Gate

在关键步骤插入人工审批。

```python
def skill_with_approval(state: dict) -> dict:
    """执行 Skill 前检查是否需要审批"""
    skill_name = state["skill_name"]

    # 需要审批的 Skill 列表
    APPROVAL_REQUIRED = {"send_email", "create_refund", "delete_record", "publish_content"}
    HIGH_RISK = {"database_migration", "bulk_update"}

    if skill_name in HIGH_RISK:
        return {
            "status": "blocked",
            "message": f"⚠️ 高风险 Skill [{skill_name}] 需要双人审批",
            "requires_dual_approval": True,
        }

    if skill_name in APPROVAL_REQUIRED:
        return {
            "status": "pending_approval",
            "message": f"🔔 Skill [{skill_name}] 需要人工审批",
            "approval_details": {
                "skill": skill_name,
                "parameters": state.get("parameters", {}),
                "context": state.get("context", ""),
                "timestamp": datetime.now().isoformat(),
            }
        }

    # 安全 Skill，直接执行
    return {"status": "approved", "proceed": True}
```

## 跨团队 Skill 目录

### 组织结构

```
skills/
├── platform/                    # 平台团队维护的共享 Skill
│   ├── pii-redaction/           #   PII 信息脱敏
│   │   └── SKILL.md
│   ├── gdpr-export/             #   GDPR 数据导出
│   │   ├── SKILL.md
│   │   └── scripts/export.py
│   └── audit-logging/           #   审计日志格式
│       └── SKILL.md
├── support/                     # 客服团队 Skill
│   ├── refund-escalation/
│   │   └── SKILL.md
│   ├── billing-dispute/
│   │   └── SKILL.md
│   └── account-recovery/
│       └── SKILL.md
├── engineering/                 # 工程团队 Skill
│   ├── code-review/
│   │   ├── SKILL.md
│   │   └── references/checklist.md
│   ├── incident-response/
│   │   ├── SKILL.md
│   │   └── scripts/runbook.py
│   └── deployment/
│       └── SKILL.md
└── sales/                       # 销售团队 Skill
    ├── lead-qualification/
    │   └── SKILL.md
    └── contract-review/
        └── SKILL.md
```

### 共享 Skill 的引用模式

```markdown
---
name: refund-escalation
description: 处理退款升级请求。当标准退款流程被拒绝或用户要求升级时使用。
version: "1.1.0"
allowed-tools:
  - query_order
  - create_refund
  - send_email
---

# 退款升级处理

## 注意
此 Skill 依赖平台 Skill：
- [[pii-redaction]]：输出前对所有用户数据执行脱敏
- [[audit-logging]]：记录所有退款操作用于合规审计
```

## 行业案例

### 案例 1：电商客服 Skill 目录

**场景**：某电商平台为 AI 客服 Agent 构建了 15 个 Skill，覆盖售前、售中、售后全流程。

| Skill | 触发条件 | 核心流程 |
|-------|----------|----------|
| `order-tracking` | "我的订单到哪了" | 查单号 → 查物流 → 格式化状态 |
| `return-request` | "我要退货" | 检查退货条件 → 生成退货单 → 发送指引 |
| `price-match` | "别家更便宜" | 验证价格 → 对比政策 → 决定是否补偿 |
| `product-recommend` | "有什么推荐" | 查历史 → 偏好分析 → 推荐 Top 5 |

**效果**：
- Skill 激活准确率：94%（从初始的 78% 经过 5 轮迭代提升）
- 一次解决率：从 61% 提升到 82%
- 平均对话轮次：从 8.3 降到 4.1

### 案例 2：SRE 故障响应 Skill

**场景**：某 SaaS 公司的 SRE 团队构建了故障自动诊断 Skill 套件。

```yaml
# 故障响应 Skill 链
alert-triggered:
  → triage-alert (Skill: 告警分级)
    → severity-1: escalate-to-human (直接通知人工)
    → severity-2: diagnostic-runbook (Skill: 自动诊断)
      → check-metrics (Skill: 检查指标)
      → check-logs (Skill: 检查日志)
      → check-recent-deploys (Skill: 检查部署)
      → suggest-fix (Skill: 建议修复)
    → severity-3: auto-remediation (Skill: 自动修复，受限操作)
```

**效果**：
- MTTR（平均修复时间）：从 45 分钟降到 12 分钟
- 40% 的告警完全自动处理，无需人工介入
- 夜间 on-call 页面减少 65%

### 案例 3：金融合规审查

**场景**：某银行合规部门构建了交易审查 Skill，用于识别可疑交易。

```markdown
---
name: transaction-review
description: 审查金融交易是否符合反洗钱(AML)和 KYC 规定。触发条件包括大额交易、跨境转账、异常交易模式。
version: "2.3.0"
allowed-tools:
  - query_transaction
  - check_customer_profile
  - check_sanctions_list
---

# 交易合规审查

## 审查流程

### 步骤 1：获取交易上下文
使用 `query_transaction` 获取交易详情，包括：
- 金额、币种、时间
- 发起方和接收方信息
- 交易类型和用途说明

### 步骤 2：客户尽职调查
使用 `check_customer_profile` 验证：
- 客户 KYC 状态是否为"已完成"
- 交易金额是否与客户风险等级匹配
- 近期交易频率是否异常

### 步骤 3：制裁名单检查
使用 `check_sanctions_list` 检查交易双方是否在制裁名单中。

### 步骤 4：生成审查结论
根据上述检查结果，生成以下结论之一：
- ✅ **通过**：无异常，自动放行
- 🔔 **关注**：存在轻微异常，标注后放行并抄送合规官
- ⛔ **升级**：存在严重异常，冻结交易并通知合规团队

## 升级条件
以下任一条件触发升级：
- 交易金额 > $10,000 且客户风险等级为"高"
- 制裁名单命中（任何一方）
- 7 天内同类交易 > 5 笔
- 交易用途描述包含敏感关键词

## 合规记录
所有审查结果记录到审计日志，包含：
- 审查时间戳
- 审查人（Agent ID）
- 决策依据
- 处理结果
```

## Skill 运营指标

```python
SKILL_KPIS = {
    "activation": {
        "precision": "触发准确率（触发且正确 / 所有触发）",
        "recall": "应触发召回率（触发且正确 / 所有应触发）",
        "avg_tokens": "Skill 正文的平均 Token 数",
    },
    "quality": {
        "task_success_rate": "Skill 激活后任务成功率",
        "avg_steps": "完成任务的平均步骤数",
        "human_escalation_rate": "需要人工介入的比例",
    },
    "cost": {
        "tokens_per_invocation": "每次激活的平均 Token 消耗",
        "cost_per_invocation": "每次激活的成本",
        "monthly_activations": "月激活次数",
    },
}
```

## 实践练习

1. 为你的项目设计一个跨团队 Skill 目录结构，至少包含 3 个团队的 Skill
2. 实现 Fan-out/Fan-in 模式：用 3 个不同 Skill 并行分析同一段文本的不同维度
3. 设计一个"自动降级"的 Skill Chain：主 Skill 失败时自动切换到备用 Skill
