# 案例 2：Grab 数据分析仓库多 Agent 客服系统

## 背景

**公司**：Grab（东南亚超级 App，提供打车、外卖、支付等服务）
**部门**：Analytics Data Warehouse (ADW) 团队
**场景**：为 1000+ 内部用户（数据分析师、产品经理、运营）提供 15000+ 张数据表的自助查询支持
**技术栈**：FastAPI + LangGraph + Redis + PostgreSQL

## 业务挑战

ADW 团队面临典型的数据平台支撑困境：

1. **重复问题海量**：每月收到数百个"这个表怎么用""XX 数据在哪查"的基础问题
2. **上下文膨胀**：数据仓库 15000+ 张表，常规 Agent 无法在上下文中容纳所有表 Schema
3. **安全性要求**：不同用户对不同表有不同的查询权限
4. **工程师疲劳**：大量重复工作消耗工程团队的生产力

## 架构设计

### 系统全景

```
┌──────────────────────────────────────────┐
│              FastAPI 网关                  │
│  /chat  /query  /schema  /health         │
└─────────────┬────────────────────────────┘
              │
    ┌─────────┴──────────┐
    │   LangGraph Agent   │
    │                     │
    │  ┌───────────────┐  │
    │  │ Intent Router │  │
    │  └───┬───┬───┬───┘  │
    │      │   │   │      │
    │  ┌───┘   │   └───┐  │
    │  ▼       ▼       ▼  │
    │ Schema  Query   FAQ  │
    │ Agent   Agent   Agent│
    │  │       │       │   │
    │  └───────┴───────┘   │
    │          │           │
    │     Supervisor       │
    └─────────┬────────────┘
              │
    ┌─────────┴──────────┐
    │  数据层             │
    │  Redis (缓存+状态)  │
    │  PostgreSQL (元数据)│
    │  Data Warehouse     │
    └─────────────────────┘
```

### Supervisor + Worker 模式

```python
from langgraph_supervisor import create_supervisor
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

# ── Worker Agent 定义 ──

schema_agent = create_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[search_table_catalog, get_table_schema, get_table_lineage],
    name="schema_expert",
    system_prompt="""你是数据表 Schema 专家。

能力：
- 搜索数据仓库中 15000+ 张表
- 解释表结构、字段含义
- 说明表之间的血缘关系

当用户询问"XX 数据在哪张表"或"这个字段是什么意思"时，由你处理。"""
)

query_agent = create_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[execute_sql, validate_sql, estimate_query_cost],
    name="query_expert",
    system_prompt="""你是 SQL 查询专家。

能力：
- 帮助编写和优化 SQL 查询
- 预估查询成本（扫描数据量）
- 确保查询安全（只读、无注入）

规则：
- 只允许 SELECT 语句
- 大查询（>1TB 扫描）需要用户确认"""
)

faq_agent = create_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[search_faq, search_docs],
    name="faq_expert",
    system_prompt="""你是数据平台 FAQ 专家。

能力：
- 回答常见问题（"如何申请数据权限""数据更新频率"等）
- 引导用户查看相关文档
- 处理非技术性的平台使用问题"""
)

# ── Supervisor ──
supervisor = create_supervisor(
    agents=[schema_agent, query_agent, faq_agent],
    model=ChatOpenAI(model="gpt-4o"),
    prompt="""你是 ADW 数据平台助手的主管。

路由规则：
- 用户询问表结构/字段/血缘 → schema_expert
- 用户需要写 SQL/查数据 → query_expert
- 用户询问平台使用/权限/文档 → faq_expert
- 复杂问题可能需要多个 Agent 协作

当用户的问题被充分解答后，回复 FINISH。""",
    output_mode="last"
)
```

## 关键工程实践

### 1. 表 Schema 的分层缓存

15000 张表无法全部放入上下文。Grab 使用分层检索策略：

```python
class SchemaCache:
    """分层 Schema 缓存"""

    def __init__(self):
        self.l1 = Redis()     # 热门表（~100 张），TTL 1h
        self.l2 = PostgreSQL()  # 全量表元数据

    def get_schema(self, table_name: str) -> dict:
        # L1: 热门表缓存
        cached = self.l1.get(f"schema:{table_name}")
        if cached:
            return json.loads(cached)

        # L2: 数据库查询
        schema = self.l2.query(
            "SELECT * FROM table_catalog WHERE name = %s",
            [table_name]
        )

        # 写入 L1 缓存
        self.l1.setex(f"schema:{table_name}", 3600, json.dumps(schema))
        return schema
```

### 2. SQL 安全校验链

```python
from langgraph.graph import StateGraph
from langgraph.types import interrupt

class SQLValidationChain:
    """SQL 执行前的多层校验"""

    @staticmethod
    def syntax_check(sql: str) -> bool:
        """语法校验"""
        try:
            sqlparse.parse(sql)
            return True
        except:
            return False

    @staticmethod
    def read_only_check(sql: str) -> bool:
        """只读校验"""
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]
        sql_upper = sql.upper()
        return not any(kw in sql_upper for kw in forbidden)

    @staticmethod
    def cost_estimate(sql: str) -> int:
        """预估扫描数据量（GB）"""
        # EXPLAIN 查询计划
        ...

    @staticmethod
    def permission_check(user: str, tables: list[str]) -> bool:
        """权限校验"""
        # 检查用户对涉及的所有表是否有只读权限
        ...
```

### 3. 断点恢复与人工介入

```python
def execute_query_node(state: QueryState) -> dict:
    """查询执行节点（大查询暂停）"""
    cost_gb = SQLValidationChain.cost_estimate(state["sql"])

    if cost_gb > 100:  # 超过 100GB 扫描
        # 暂停等待用户确认
        confirm = interrupt(
            f"查询将扫描约 {cost_gb}GB 数据，预计耗时 5-10 分钟。是否继续？"
        )
        if not confirm:
            return {"status": "cancelled", "message": "用户取消了高成本查询"}

    result = execute_sql(state["sql"])
    return {"status": "completed", "result": result}
```

## 成果与数据

- **服务规模**：支持 1000+ 内部用户
- **覆盖范围**：15000+ 张数据表
- **效率提升**：每月回收数百小时工程生产力（减少重复答疑）
- **用户满意度**：自助查询比例大幅提升

## 可复用的设计模式

1. **Schema 分层缓存**：热门数据 L1 缓存，全量数据 L2 数据库
2. **SQL 校验链**：语法 → 只读 → 成本 → 权限，多层保障
3. **大查询人工确认**：超过阈值的数据扫描需要人工审批
4. **Supervisor + 3 Worker**：按问题类型分为 Schema、Query、FAQ

## 实践练习

1. 设计一个数据平台 Agent 的 Schema 缓存策略（你的场景下热门数据是什么）
2. 实现 SQL 校验链的前两层（语法校验 + 只读校验）
3. 为你的数据平台设计 Supervisor 的路由 Prompt
