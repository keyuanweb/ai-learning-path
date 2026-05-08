# 案例 3：Remote 客户数据迁移自动化 Agent

## 背景

**公司**：Remote（全球薪酬与合规平台）
**场景**：大批量客户薪酬数据迁移（CSV/Excel → Remote 平台）
**技术栈**：LangChain + LangGraph + WebAssembly 沙箱（Python/Pandas）

## 业务挑战

当客户从其他 HR/薪酬系统迁移到 Remote 时，需要将历史薪酬数据导入平台。这个过程极其复杂：

1. **文件巨大**：客户上传的薪酬电子表格常超过 50MB，包含数万行、上百列
2. **格式混乱**：每个客户的列名、日期格式、币种格式完全不同（如 "Jan Salary" vs "2024-01_SAL"）
3. **合规要求**：薪酬数据涉及多国税务法规，不能有任何错误
4. **上下文溢出**：即使是 GPT-4 的 128K 上下文也无法容纳完整的 50MB 电子表格

## 核心架构原则

> "Let models think, let code execute, keep the two cleanly separated."
> —— Remote 工程团队的架构原则

```
┌─────────────────────────────────────┐
│         LangGraph 编排层             │
│                                     │
│  Ingestion → Mapping → Validation   │
│     │           │           │        │
│     └───────────┴───────────┘        │
│                 │                    │
│            LLM Planner               │
│          (gpt-4o / claude)           │
│                 │                    │
│        生成 Python 转换脚本           │
│                 │                    │
│     ┌───────────┴───────────┐        │
│     │   WebAssembly 沙箱    │        │
│     │   Python + Pandas     │        │
│     │   执行转换脚本         │        │
│     └───────────────────────┘        │
│                 │                    │
│            Validation               │
│            + Output                  │
└─────────────────────────────────────┘
```

## LangGraph 工作流实现

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

class MigrationState(TypedDict):
    # 输入
    raw_file_path: str
    sample_data: str          # 采样的前 50 行
    column_mapping_rules: dict
    # 处理
    transformation_script: str
    execution_result: str
    validation_errors: list[str]
    # 输出
    migrated_data_path: str
    audit_log: str
    status: str               # pending / mapping / executing / validating / done / failed

# ── 节点实现 ──

def ingest(state: MigrationState) -> dict:
    """第一步：数据摄入。只读取文件结构和样本数据。"""
    import pandas as pd

    # 读取文件结构（不全量读入）
    df_sample = pd.read_csv(state["raw_file_path"], nrows=50)

    return {
        "sample_data": df_sample.to_csv(index=False),
        "status": "mapping"
    }

# Planner：生成转换脚本（不执行）
mapper = create_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[],
    system_prompt="""你是一个数据迁移专家。根据客户薪酬数据的样本，生成 Python 转换脚本。

## 要求
1. 使用 pandas 读取 CSV 文件
2. 识别并标准化列名（映射到标准 Schema）
3. 标准化日期格式（统一为 YYYY-MM-DD）
4. 标准化币种格式（去除货币符号，保留数值）
5. 处理缺失值和异常值
6. 脚本必须是纯 Python，不依赖 LLM

## 输出格式
```python
import pandas as pd
import numpy as np
from datetime import datetime

def transform(input_path: str, output_path: str):
    df = pd.read_csv(input_path)
    # 你的转换逻辑
    df.to_csv(output_path, index=False)
```

只输出 Python 代码，不要解释。"""
)

def generate_transformation(state: MigrationState) -> dict:
    """第二步：LLM 生成转换脚本"""
    sample = state["sample_data"][:3000]  # 只用样本，节省 token

    result = mapper.invoke({
        "messages": [{
            "role": "user",
            "content": f"根据以下薪酬数据样本，生成转换脚本：\n{sample}"
        }]
    })

    script = result["messages"][-1].content
    # 提取 Python 代码块
    import re
    code_match = re.search(r"```python\n(.*?)```", script, re.DOTALL)
    if code_match:
        script = code_match.group(1)

    return {
        "transformation_script": script,
        "status": "executing"
    }

def execute_in_sandbox(state: MigrationState) -> dict:
    """第三步：在 WebAssembly 沙箱中执行转换脚本（关键安全措施）"""
    import subprocess
    import tempfile
    import os

    script = state["transformation_script"]
    output_path = state["raw_file_path"].replace(".csv", "_migrated.csv")

    # 写入临时脚本文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(f"""
import sys
sys.path = ['/sandbox/lib']  # 限制模块路径

{script}

if __name__ == '__main__':
    transform('{state["raw_file_path"]}', '{output_path}')
""")
        script_path = f.name

    try:
        # 在受限环境中执行
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=300,  # 5 分钟超时
            env={"PYTHONPATH": "/sandbox/lib", "HOME": "/sandbox"}
        )

        os.unlink(script_path)

        if result.returncode == 0:
            return {"execution_result": "success", "status": "validating"}
        else:
            return {
                "execution_result": f"error: {result.stderr}",
                "status": "failed"
            }
    except subprocess.TimeoutExpired:
        return {"execution_result": "timeout", "status": "failed"}

def validate_migration(state: MigrationState) -> dict:
    """第四步：验证迁移结果"""
    import pandas as pd

    original = pd.read_csv(state["raw_file_path"], nrows=5)
    migrated = pd.read_csv(
        state["raw_file_path"].replace(".csv", "_migrated.csv"),
        nrows=5
    )

    errors = []

    # 检查行数是否匹配
    if len(original) != len(migrated):
        errors.append(f"行数不匹配: {len(original)} vs {len(migrated)}")

    # 检查必填列
    required_cols = ["employee_id", "salary_amount", "currency", "pay_date"]
    for col in required_cols:
        if col not in migrated.columns:
            errors.append(f"缺少必填列: {col}")

    # 检查空值比例
    null_pct = migrated.isnull().sum().sum() / (len(migrated) * len(migrated.columns))
    if null_pct > 0.1:
        errors.append(f"空值比例过高: {null_pct:.1%}")

    if errors:
        return {"validation_errors": errors, "status": "failed"}

    return {"validation_errors": [], "status": "done"}

# ── 构建 Graph ──
builder = StateGraph(MigrationState)

builder.add_node("ingest", ingest)
builder.add_node("map", generate_transformation)
builder.add_node("execute", execute_in_sandbox)
builder.add_node("validate", validate_migration)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "map")
builder.add_edge("map", "execute")
builder.add_edge("execute", "validate")
builder.add_edge("validate", END)

migration_graph = builder.compile()
```

## 关键工程实践

### 1. LLM 作为 Planner，代码作为 Executor

这是 Remote 案例最核心的架构决策。LLM 只负责"思考"（规划转换逻辑），代码只负责"执行"（处理数据）。

```python
# ❌ 错误做法：让 LLM 直接处理数据
response = llm.invoke(f"转换以下 50000 行数据：{all_data}")
# 问题：上下文溢出、幻觉风险、成本极高

# ✅ 正确做法：LLM 生成代码，沙箱执行
script = llm.invoke(f"根据以下 50 行写转换脚本：{sample}")
result = sandbox.execute(script, full_data)
# 优势：可审计、可重复、成本可控
```

### 2. 多阶段验证

```python
VALIDATION_STAGES = [
    "row_count_check",       # 行数是否匹配
    "column_existence",      # 必填列是否存在
    "data_type_check",       # 数据类型是否正确
    "null_threshold",        # 空值比例阈值
    "business_rule_check",   # 业务规则验证（如薪酬不可为负）
    "cross_field_check",     # 跨字段一致性（如总额 = 基本工资 + 补贴）
]
```

### 3. 审计日志

每次迁移生成完整审计日志，用于合规审查：

```python
def generate_audit_log(state: MigrationState) -> str:
    return json.dumps({
        "migration_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "input_file": state["raw_file_path"],
        "sample_rows": 50,
        "transformation_script": state["transformation_script"],
        "execution_duration_ms": state.get("execution_duration"),
        "validation_errors": state.get("validation_errors", []),
        "status": state["status"],
        "operator": "automated",  # or "human_reviewed"
    }, indent=2)
```

## 成果与数据

- **效率**：迁移时间从**天**级缩短到**小时**级
- **可靠性**：转换逻辑可审计、可重复执行
- **合规**：每个迁移都有完整的审计轨迹，满足多司法管辖区要求

## 可复用的设计模式

1. **LLM Planner + Code Executor 分离**：LLM 只处理逻辑推理，数据操作交给代码
2. **采样策略**：LLM 只看样本（前 50 行），代码处理全量数据
3. **沙箱执行**：WebAssembly/Podman 隔离执行环境，安全可控
4. **多阶段验证**：结构 → 类型 → 业务规则，逐层校验
5. **审计日志**：合规场景必须记录完整的转换逻辑和执行结果

## 实践练习

1. 设计一个 LLM 生成 + 沙箱执行的通用模式（可应用于哪些场景？）
2. 添加更多验证阶段：货币范围检查、日期合理性检查
3. 当验证失败时，如何让 Agent 自动修复转化脚本？
