# Skill 自动化创建流程

## 为什么需要自动化创建

手动编写 `SKILL.md` 容易遗漏关键信息（参数、错误处理、边界条件），且难以保证质量一致性。LangChain 社区在 2026 年提出了**用 Graph 来生成 Skill** 的模式。

## Skill Creation Graph

```
START → capture_intent → write_skill → validate
                ↑              ↑            ↓ (未通过且未超限)
                │              └── fix_validate ←─────┘
                │                        ↓ (通过)
                │                   run_tests
                │              ↑      ↓ (未全通过且未超限)
                │              └── refine_tests ←─────┘
                │                        ↓ (全部通过)
                │                   persist → verify → finalize_ok → END
                │
                └── 失败重试（最多 3 次）
```

## LangGraph 实现

```python
from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# ── 数据模型 ──
class SkillIntent(BaseModel):
    """用户意图的结构化表达"""
    suggested_name: str = Field(description="建议的 Skill 名称")
    description: str = Field(description="何时使用")
    triggers: list[str] = Field(description="触发场景关键词")
    steps: list[str] = Field(description="执行步骤列表")
    required_tools: list[str] = Field(description="需要的工具")
    test_cases: list[dict] = Field(description="测试用例")

class SkillCreateState(TypedDict):
    user_request: str
    intent: dict
    skill_md: str
    validation_errors: list[str]
    test_results: list[dict]
    persist_path: str
    max_retries: int
    current_retry: int

model = ChatOpenAI(model="gpt-4o")

# ── 节点实现 ──
def capture_intent(state: SkillCreateState) -> dict:
    """步骤 1：捕获用户意图，转为结构化描述"""

    prompt = f"""用户想创建一个 Skill："{state['user_request']}"

请分析并输出 JSON：
```json
{{
  "suggested_name": "小写英文，用-连接词",
  "description": "1-2 句话描述何时使用",
  "triggers": ["触发关键词1", "触发关键词2"],
  "steps": ["步骤1", "步骤2", "步骤3"],
  "required_tools": ["工具1", "工具2"],
  "test_cases": [{{"input": "...", "expected_output": "..."}}]
}}
```"""

    response = model.invoke(prompt)
    import json
    intent = json.loads(response.content)
    return {"intent": intent, "current_retry": 0}

def write_skill(state: SkillCreateState) -> dict:
    """步骤 2：根据意图生成完整的 SKILL.md"""

    intent = state["intent"]

    prompt = f"""根据以下意图生成完整的 SKILL.md 文件：

```json
{json.dumps(intent, indent=2, ensure_ascii=False)}
```

生成格式要求：
---
name: {intent['suggested_name']}
description: |
  {intent['description']}
allowed-tools:
{chr(10).join(f'  - {t}' for t in intent['required_tools'])}
---

# {intent['suggested_name']} Skill

## 执行流程
{chr(10).join(f'### 步骤 {i+1}：{s}' for i, s in enumerate(intent['steps']))}

## 错误处理
- 每步失败时的回退策略
- 超时处理

## 输出格式
（描述输出结构）
"""

    response = model.invoke(prompt)
    return {"skill_md": response.content}

def validate(state: SkillCreateState) -> dict:
    """步骤 3：验证 SKILL.md 格式和质量"""

    errors = []
    content = state["skill_md"]

    # 检查 YAML frontmatter
    if not content.strip().startswith("---"):
        errors.append("缺少开头的 --- YAML frontmatter")
    else:
        parts = content.split("---", 2)
        if len(parts) < 3:
            errors.append("YAML frontmatter 格式错误：需要以 --- 开头和结尾")

    # 检查必填字段
    checks = [
        ("name:", "缺少 name 字段"),
        ("description:", "缺少 description 字段"),
        ("## 执行流程", "缺少执行流程章节"),
        ("## 错误处理", "缺少错误处理章节"),
    ]
    for keyword, error_msg in checks:
        if keyword not in content:
            errors.append(error_msg)

    # 检查名称规范
    if '"name"' in content or "'name'" in content:
        errors.append("name 不应使用引号")

    return {"validation_errors": errors}

def fix_validate(state: SkillCreateState) -> dict:
    """修复验证错误"""

    prompt = f"""以下 SKILL.md 存在验证错误，请修复：

当前内容：
```
{state['skill_md'][:3000]}
```

错误列表：
{chr(10).join(f'- {e}' for e in state['validation_errors'])}

输出修复后的完整 SKILL.md。"""

    response = model.invoke(prompt)
    retry = state.get("current_retry", 0) + 1
    return {"skill_md": response.content, "current_retry": retry}

def run_tests(state: SkillCreateState) -> dict:
    """步骤 4：执行测试用例"""

    intent = state["intent"]
    test_cases = intent.get("test_cases", [])
    results = []

    for tc in test_cases:
        # 模拟执行：用 LLM as Judge 评估 Skill 能否处理该输入
        judge_prompt = f"""你是质量评审。评估以下 Skill 能否处理给定的测试输入。

Skill:
{state['skill_md'][:2000]}

测试输入：{tc.get('input', '')}
预期输出：{tc.get('expected_output', '')}

评分（0-100）：Skill 能否按预期处理此输入？
只输出数字。"""

        score = model.invoke(judge_prompt).content.strip()
        try:
            score_num = int(score)
        except:
            score_num = 0

        results.append({
            "input": tc.get("input"),
            "expected": tc.get("expected_output"),
            "score": score_num,
            "passed": score_num >= 70
        })

    return {"test_results": results}

def refine_tests(state: SkillCreateState) -> dict:
    """修复未通过的测试"""

    failed = [r for r in state.get("test_results", []) if not r["passed"]]

    prompt = f"""以下 Skill 有 {len(failed)} 个测试未通过。改进 Skill 使其能通过所有测试。

当前 Skill：
```
{state['skill_md'][:3000]}
```

失败测试：
{json.dumps(failed, indent=2, ensure_ascii=False)}

输出改进后的完整 SKILL.md。"""

    response = model.invoke(prompt)
    retry = state.get("current_retry", 0) + 1
    return {"skill_md": response.content, "current_retry": retry}

def persist(state: SkillCreateState) -> dict:
    """步骤 5：持久化到 Skill 库"""

    import os
    intent = state["intent"]
    skill_name = intent["suggested_name"]

    skill_dir = f"skills_library/{skill_name}"
    os.makedirs(skill_dir, exist_ok=True)

    path = f"{skill_dir}/SKILL.md"
    with open(path, "w") as f:
        f.write(state["skill_md"])

    return {"persist_path": path}

def verify(state: SkillCreateState) -> dict:
    """最终验证：确保文件可被加载"""

    import yaml

    with open(state["persist_path"]) as f:
        content = f.read()

    # 再次解析 frontmatter
    parts = content.split("---", 2)
    if len(parts) >= 3:
        metadata = yaml.safe_load(parts[1])
        assert "name" in metadata, "缺少 name"
        assert "description" in metadata, "缺少 description"

    return {"status": "verified"}

# ── 路由函数 ──
def route_validate(state: SkillCreateState) -> str:
    errors = state.get("validation_errors", [])
    if not errors:
        return "run_tests"
    if state.get("current_retry", 0) >= state.get("max_retries", 3):
        return "run_tests"  # 放弃修复，直接继续
    return "fix_validate"

def route_tests(state: SkillCreateState) -> str:
    results = state.get("test_results", [])
    if not results:
        return "persist"
    all_passed = all(r["passed"] for r in results)
    if all_passed:
        return "persist"
    if state.get("current_retry", 0) >= state.get("max_retries", 3):
        return "persist"
    return "refine_tests"

# ── 构建 Graph ──
builder = StateGraph(SkillCreateState)

builder.add_node("capture_intent", capture_intent)
builder.add_node("write_skill", write_skill)
builder.add_node("validate", validate)
builder.add_node("fix_validate", fix_validate)
builder.add_node("run_tests", run_tests)
builder.add_node("refine_tests", refine_tests)
builder.add_node("persist", persist)
builder.add_node("verify", verify)

builder.add_edge(START, "capture_intent")
builder.add_edge("capture_intent", "write_skill")
builder.add_edge("write_skill", "validate")
builder.add_conditional_edges("validate", route_validate, {
    "run_tests": "run_tests",
    "fix_validate": "fix_validate",
})
builder.add_edge("fix_validate", "validate")
builder.add_conditional_edges("run_tests", route_tests, {
    "persist": "persist",
    "refine_tests": "refine_tests",
})
builder.add_edge("refine_tests", "run_tests")
builder.add_edge("persist", "verify")
builder.add_edge("verify", END)

skill_creator = builder.compile()
```

## 使用 Skill Creation Graph

```python
# 创建 Skill
result = skill_creator.invoke({
    "user_request": "我需要一个 Skill，可以搜索 StackOverflow 上的编程问题，提取最佳答案，并格式化为 Markdown",
    "max_retries": 3,
    "current_retry": 0
})

print(f"Skill 已创建: {result['persist_path']}")
print(f"验证: {result.get('status', 'unknown')}")

# 加载到 Agent
agent = create_deep_agent(
    model=model,
    backend=LocalShellBackend(root_dir="."),
    skills=["./skills_library/"],  # ← 指向刚创建的 Skill 库
)
```

## 与 CI/CD 集成

```python
# .github/workflows/skill-test.yml
"""
name: Skill Validation

on:
  pull_request:
    paths: ['skills_library/**']

jobs:
  validate-skills:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate SKILL.md files
        run: |
          for skill_dir in skills_library/*/; do
            echo "Validating $skill_dir"
            python validate_skill.py "$skill_dir/SKILL.md"
          done
      - name: Run Skill Tests
        run: |
          python run_skill_tests.py --all
"""
```

## 质量保证清单

| 检查项 | 说明 |
|--------|------|
| ✅ YAML 格式 | frontmatter 以 `---` 包裹，合法 YAML |
| ✅ name 规范 | 全小写，`-` 连接，描述性强 |
| ✅ description 精确 | 明确何时使用、适用场景 |
| ✅ 执行步骤清晰 | 每步有明确的输入/输出 |
| ✅ 错误处理覆盖 | 每步定义了失败的回退策略 |
| ✅ 测试用例完整 | 至少 2 个正常路径 + 1 个异常路径 |
| ✅ 可独立运行 | Skill 不依赖全局状态 |

## 实践练习

1. 运行 Skill Creation Graph，为一个实际任务生成 SKILL.md
2. 添加一个自定义验证规则（如检查 description 长度 > 50 字符）
3. 将 Skill 创建流程集成到项目的 CI/CD pipeline 中
