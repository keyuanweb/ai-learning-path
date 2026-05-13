# 11 - Kanban 看板系统

## 这一章讲什么？

第 10 章的 `delegate_task` 适合单次对话中的临时并行拆分——父 Agent 等子 Agent 返回结果，对话结束一切消失。但实际生产中还有另一种需求：**跨会话、跨时间的长期多 Agent 协作**。比如一个复杂任务需要拆成 4 个子任务分布在几个小时内完成，中途需要人来审批，失败了要自动重试，所有操作要有审计轨迹。

Hermes 的 Kanban 看板系统就是为此设计的：一个基于 SQLite 的持久化多 Agent 任务调度系统。

核心文件:
- [tools/kanban_tools.py](../code/hermes-agent/tools/kanban_tools.py) (874行) — 7 个看板工具定义、Schema、注册
- [hermes_cli/kanban_db.py](../code/hermes-agent/hermes_cli/kanban_db.py) (4000+行) — SQLite 数据库层、状态机、调度器、Worker 上下文构建
- [hermes_cli/kanban.py](../code/hermes-agent/hermes_cli/kanban.py) — CLI 子命令（`hermes kanban ...`）
- [agent/prompt_builder.py](../code/hermes-agent/agent/prompt_builder.py#L188) — KANBAN_GUIDANCE 自动注入块
- [skills/devops/kanban-orchestrator/SKILL.md](../code/hermes-agent/skills/devops/kanban-orchestrator/SKILL.md) — 编排者角色技能
- [skills/devops/kanban-worker/SKILL.md](../code/hermes-agent/skills/devops/kanban-worker/SKILL.md) — 执行者角色技能

---

## 第一部分: Kanban vs delegate_task

两个系统解决不同的问题：

| 维度 | `delegate_task` | Kanban 看板 |
|------|----------------|------------|
| **持久化** | 临时，API 返回即消失 | SQLite 持久存储，跨会话留存 |
| **调度方式** | 父 Agent 同步等待子 Agent | Dispatcher 守护进程异步轮询调度 |
| **生命周期** | 单次工具调用内完成 | 任务状态机，跨多个进程/时间段 |
| **人的参与** | 无人参与，Agent 间自协调 | 人可随时 block/unblock/comment |
| **故障恢复** | 子 Agent 崩溃则整个调用失败 | 自动回收 stale claim，断路器重试 |
| **审计轨迹** | 无 | 完整的 events / runs / comments 永久记录 |
| **并行策略** | ThreadPoolExecutor 并行 | Dispatcher 独立 spawn 多个进程 |
| **依赖管理** | 无 | 父任务完成 → 子任务自动就绪 |
| **适用场景** | 单次对话中的快速并行推理 | 跨会话长期工作流、多人审批、审计合规 |

简单判断：需要跨会话持久化、人参与审批、故障自动恢复、审计追踪 → 用 Kanban。否则用 `delegate_task`。

---

## 第二部分: 架构全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ~/.hermes/kanban.db (SQLite + WAL)                │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │    tasks     │  │  task_links  │  │ task_comments│  │task_events│ │
│  │  核心任务表   │  │  依赖关系表   │  │  评论线程     │  │  事件日志   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘ │
│  ┌──────────────┐                                                     │
│  │  task_runs   │  每次 Worker 执行的完整记录                          │
│  └──────────────┘                                                     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Dispatcher   │  │   Worker 1    │  │   Worker 2    │
│  守护进程      │  │  subprocess   │  │  subprocess   │
│               │  │               │  │               │
│  每 60s tick: │  │ $HERMES_      │  │ $HERMES_      │
│  1.回收stale  │  │  KANBAN_TASK  │  │  KANBAN_TASK  │
│    claims     │  │  =t_xxx       │  │  =t_yyy       │
│  2.提升就绪   │  │               │  │               │
│    任务       │  │ kanban_show() │  │ kanban_show() │
│  3.匹配worker │  │ → work        │  │ → work        │
│  → spawn      │  │ → heartbeat   │  │ → complete    │
└───────────────┘  └───────────────┘  └───────────────┘
```

### Dispatcher（调度器）

Dispatcher 是一个长期运行的守护进程（systemd 管理），每个 tick（默认 60 秒）执行：

1. **回收 stale claims**：`release_stale_claims()` 扫描所有 `running` 状态且 `claim_expires < now` 的任务，重置为 `ready`，并记录 `timed_out` 或 `reclaimed` outcome
2. **提升就绪任务**：`recompute_ready()` 检查所有 `todo` 任务，如果所有父任务都是 `done`，自动提升为 `ready`
3. **匹配并 spawn**：对每个 `ready` 任务，根据 `assignee` 匹配对应的 profile，调用 `_default_spawn()` 启动 `hermes -p <profile> chat` 子进程

Dispatcher 通过 **CAS（Compare-And-Swap）** 原子操作抢占任务——SQLite WAL 模式 + `BEGIN IMMEDIATE`，只有一个 Dispatcher 能抢到每个任务。

### Worker（执行者）

每个 Worker 是 Dispatcher spawn 的一个**独立子进程**：

```bash
hermes -p researcher chat -q "work kanban task t_a1b2c3d4"
```

Worker 进程的环境变量：

| 环境变量 | 含义 |
|---------|------|
| `HERMES_KANBAN_TASK` | 当前任务 ID |
| `HERMES_KANBAN_WORKSPACE` | 工作空间路径 |
| `HERMES_KANBAN_RUN_ID` | 本次运行的 run_id |
| `HERMES_KANBAN_CLAIM_LOCK` | claim 锁 token（用于 heartbeat 续期） |
| `HERMES_KANBAN_DB` | 数据库文件路径（防御性 pin） |
| `HERMES_KANBAN_BOARD` | 看板 slug（多看板隔离） |
| `HERMES_PROFILE` | Worker 的 profile 名（用于 comment 署名） |

---

## 第三部分: 任务状态机

```
                  ┌─────────┐
                  │ triage  │  ← 用户丢了一个粗略想法（只有标题）
                  └────┬────┘
                       │ specify (kanban_specify.py 用 LLM 充实 body)
                       ▼
                  ┌─────────┐
          ┌───────│  todo   │  ← 等待父任务完成
          │       └────┬────┘
          │            │ 所有父任务 done → Dispatcher 自动提升
          │            ▼
          │       ┌─────────┐
          │  ┌───▶│  ready  │  ← 等待被 Dispatcher 认领
          │  │    └────┬────┘
          │  │         │ claim_task() CAS 原子操作
          │  │         ▼
          │  │    ┌─────────┐
          │  │    │ running │  ← Worker 正在执行
          │  │    └────┬────┘
          │  │         │
          │  │   ┌─────┼──────────┐
          │  │   ▼     ▼          ▼
          │  │ ┌────┐ ┌────────┐ ┌──────────┐
          │  │ │done│ │blocked │ │reclaimed │ ← claim 超时 / PID 消失
          │  │ └────┘ └───┬────┘ └────┬─────┘
          │  │      ▲     │           │
          │  │      │     │ unblock   │
          │  │      │     ▼           │
          │  │      │  ┌─────────┐    │
          │  └──────┴──│  todo   │◀───┘
          │            └─────────┘
          │
          ▼
     ┌─────────┐
     │archived │  ← 手动归档（不自动删除）
     └─────────┘
```

7 种状态：

| 状态 | 含义 | 谁操作 |
|------|------|-------|
| `triage` | 草稿状态，只有标题待充实 | 人工 via `kanban_create(triage=True)` |
| `todo` | 等待父任务全部完成 | 自动（依赖未满足） |
| `ready` | 等待 Dispatcher 调度 | Dispatcher 自动提升 |
| `running` | Worker 正在执行 | Dispatcher CAS 认领 |
| `blocked` | Worker 需要人工输入 | Worker 调用 `kanban_block()` |
| `done` | 任务成功完成 | Worker 调用 `kanban_complete()` |
| `archived` | 手动归档 | 人工 via CLI |

### CAS 认领机制

[kanban_db.py:1826](code/hermes-agent/hermes_cli/kanban_db.py#L1826) `claim_task()` 是唯一的认领入口：

```sql
UPDATE tasks
   SET status = 'running',
       claim_lock = ?,
       claim_expires = ?
 WHERE id = ?
   AND status = 'ready'
   AND claim_lock IS NULL
```

只有同时满足 `status='ready'` 且 `claim_lock IS NULL` 的行才会被更新。SQLite WAL 序列化写者，最多一个 Dispatcher tick 能成功认领。失败的 tick 观察到 `rowcount=0`，静默跳过。

认领前还有一项安全检查——如果发现任何父任务尚未 `done`，拒绝认领并降级回 `todo`：

```python
undone = conn.execute(
    "SELECT 1 FROM task_links l "
    "JOIN tasks p ON p.id = l.parent_id "
    "WHERE l.child_id = ? AND p.status != 'done' LIMIT 1",
    (task_id,),
).fetchone()
if undone:
    conn.execute(
        "UPDATE tasks SET status = 'todo' "
        "WHERE id = ? AND status = 'ready'",
        (task_id,),
    )
    return None
```

这是**唯一强制点**——无论哪个代码路径把任务变成了 `ready`，只要父任务未完成，`claim_task()` 就会拒绝。

---

## 第四部分: 7 个 Kanban 工具

Kanban 工具**只在两种情况下**注册到 Agent 的工具 Schema 中（[kanban_tools.py:42](code/hermes-agent/tools/kanban_tools.py#L42)）：

1. `HERMES_KANBAN_TASK` 环境变量存在（Worker 被 Dispatcher spawn）
2. 当前 Profile 的 `toolsets` 配置包含 `"kanban"`（Orchestrator profile）

普通 `hermes chat` 会话看不到任何 kanban 工具。

### 1. kanban_show — 读取任务完整状态

```python
kanban_show()
# 或指定任务 ID（Orchestrator 查看子任务）
kanban_show(task_id="t_a1b2c3d4")
```

返回内容包括:
- **task**: 任务行（title, body, assignee, status, workspace 配置等）
- **parents**: 父任务 ID 列表
- **children**: 子任务 ID 列表
- **comments**: 评论线程
- **runs**: 历史执行记录（含 outcome, summary, error, metadata）
- **events**: 最近 50 条事件日志
- **worker_context**: 预格式化的 Worker 上下文文本（可直接纳入推理）

### 2. kanban_complete — 完成任务并结构化交付

```python
kanban_complete(
    summary="实现了速率限制器 — token bucket 算法，按 user_id + IP 回退，14 测试通过",
    metadata={
        "changed_files": ["rate_limiter.py", "tests/test_rate_limiter.py"],
        "tests_run": 14,
        "tests_passed": 14,
        "decisions": ["user_id 主键，IP 作为未认证请求的回退"],
    },
    # 如果在本轮执行中创建了子任务，必须列出：
    created_cards=[c1["task_id"], c2["task_id"]],
)
```

`created_cards` 会被**严格验证**——每个 ID 必须在数据库中存在，且必须由当前 Worker 的 profile 创建。任何幻觉 ID 会触发 `HallucinatedCardsError`，completion 被拒绝。

### 3. kanban_block — 阻塞任务等待人介入

```python
kanban_block(reason="速率限制键选择: IP (简单但 NAT 不安全) 还是 user_id (需认证但精确)?")
```

Worker 遇到无法自行决策的歧义时调用。原因会展示在 Dashboard 上，人通过 `/unblock` 回应后 Dispatcher 重新 spawn Worker。

### 4. kanban_heartbeat — 长任务心跳

```python
kanban_heartbeat(note="已处理 47/120 视频，当前速率 3.2/s")
```

两个作用：
1. 延长 claim TTL（通过 `heartbeat_claim()`）——不加这步，即使 Worker 仍在执行，15 分钟后 Dispatcher 也会回收
2. 记录 heartbeat 事件到任务日志

好的心跳写进度（"已处理 47/120 视频"），坏的心跳写废话（"还在工作"）。

### 5. kanban_comment — 追加评论

```python
kanban_comment(
    task_id="t_a1b2c3d4",
    body="完整上下文: 用户 IP 来自 Cloudflare header，但部分用户位于 NAT 后..."
)
```

评论会注入到下一个 Worker 的 `build_worker_context()` 中。评论作者**不可由调用者指定**——从 `HERMES_PROFILE` 环境变量读取，防止 Worker 伪造系统指令。

### 6. kanban_create — 创建子任务（Orchestrator 核心工具）

```python
c1 = kanban_create(
    title="研究: Postgres 成本 vs 现状",
    assignee="researcher",
    body="对比 3 年窗口内的基础设施、迁移和运维成本...",
    parents=[],                   # 无依赖，可立即执行
    priority=5,                   # Dispatcher 优先级
    workspace_kind="scratch",     # 工作空间类型
    skills=["database-research"], # 强制加载的技能
    max_runtime_seconds=900,      # 15 分钟超时上限
)
```

完整参数（[kanban_tools.py:673](../code/hermes-agent/tools/kanban_tools.py#L673)）：

| 参数 | 必需 | 说明 |
|------|------|------|
| `title` | 是 | 任务标题 |
| `assignee` | 是 | 执行任务的 profile 名 |
| `body` | 否 | 任务规格、验收标准 |
| `parents` | 否 | 父任务 ID 列表，全部 done 后才就绪 |
| `tenant` | 否 | 多项目隔离命名空间 |
| `priority` | 否 | Dispatcher 优先级（高的先调度） |
| `workspace_kind` | 否 | scratch / dir / worktree |
| `workspace_path` | 否 | dir 或 worktree 的绝对路径 |
| `triage` | 否 | True = 放到 triage 列，等待 specifier 充实 |
| `idempotency_key` | 否 | 幂等键，重复创建返回已有任务 ID |
| `max_runtime_seconds` | 否 | 超时上限 |
| `skills` | 否 | 任务级强制加载的技能列表 |

### 7. kanban_link — 事后添加依赖

```python
kanban_link(parent_id="t_aaa", child_id="t_bbb")
```

在任务已创建后添加依赖关系。会检测环路和自链接并拒绝。

---

## 第五部分: Worker 生命周期

每个被 Dispatcher spawn 的 Worker 在 System Prompt 中自动注入 `KANBAN_GUIDANCE` 块（[prompt_builder.py:188](code/hermes-agent/agent/prompt_builder.py#L188)），定义了 6 步生命周期：

```
1. ORIENT → 2. WORK → 3. HEARTBEAT(可选) → 4. BLOCK → 5. COMPLETE → 6. 创建后续工作
```

**注入点**在 [run_agent.py:5376](code/hermes-agent/run_agent.py#L5376)：

```python
if "kanban_show" in self.valid_tool_names:
    tool_guidance.append(KANBAN_GUIDANCE)
```

只有当 `kanban_show` 工具在 Agent 的 Schema 中时才注入（即只在 Worker/Orchestrator 上下文中）。

### 详细步骤

**Step 1 — Orient（定位）**

首先调用 `kanban_show()` 无参数（自动使用 `HERMES_KANBAN_TASK`）。返回内容包括：任务标题/正文、父任务的手递信息（summary + metadata）、所有历史执行记录（如果是重试）、评论线程、预格式化的 `worker_context`。

```python
# Worker 第一件事
result = kanban_show()
# 返回: task, parents, children, comments, events, runs, worker_context
```

**Step 2 — Work（执行）**

在 `$HERMES_KANBAN_WORKSPACE` 内执行工作。不要修改工作空间外的文件（除非任务明确要求）。

**Step 3 — Heartbeat（心跳）**

长操作期间每隔几分钟调用 `kanban_heartbeat(note=...)`，短任务跳过。

**Step 4 — Block（阻塞等待）**

遇到真正需要人决策的歧义时调用 `kanban_block(reason="...")` 然后停止。**不要猜测**。

**Step 5 — Complete（结构化交付）**

```python
kanban_complete(
    summary="1-3 句人类可读的交付描述（具体产出物名称）",
    metadata={"changed_files": [...], "tests_run": N, "decisions": [...]},
)
```

`summary` 是给人看的，`metadata` 是给下游 Worker 的程序化接口。不要在两者中放 secrets/tokens/PII——运行记录永久保存。

**Step 6 — 创建后续工作**

如果发现了新工作需要做，用 `kanban_create()` 创建子任务分配给正确的 specialist，而不是自己越界去做。

### Worker 上下文构建

[kanban_db.py:3933](code/hermes-agent/hermes_cli/kanban_db.py#L3933) `build_worker_context()` 为 Worker 构建完整的任务上下文，按顺序包含：

1. 任务标题（必含）
2. 任务正文（上限 8KB）
3. 本任务的历史执行记录（最近 10 次，每次有 summary/error/metadata，单字段上限 4KB）
4. 每个已完成父任务的结构化手递结果
5. 同 assignee 的跨任务角色历史（最近 5 次已完成运行）
6. 评论线程（最近 30 条，每条上限 2KB）

这些上限确保即使极端情况（重试密集型任务、评论风暴）也不超出 LLM 上下文窗口。

---

## 第六部分: Orchestrator（编排者）角色

Orchestrator 是特殊的 Kanban 参与者——它的 job 是**拆解和路由，不亲自执行**。

### 核心规则（来自 kanban-orchestrator 技能）

- **不要亲自执行工作。** 如果有实现冲动，停下来为合适的 specialist 创建任务
- **任何具体工作都必须创建 Kanban 任务并分配**
- **拆分多路请求再建卡。** 用户一句话可能包含多个独立工作流，先拆分
- **独立路并行跑。** 不互相依赖的卡片不加 parents 链接
- **如果没有合适的 specialist，问用户。** 不要自己凑合

### 标准 Specialist 角色

| Profile | 做什么 | 典型工作空间 |
|---------|-------|------------|
| `researcher` | 读资料、收集事实、写调研发现 | scratch |
| `analyst` | 综合多个 researcher 输出、排名、去重 | scratch |
| `writer` | 按用户文风撰写文件 | scratch 或 dir: |
| `reviewer` | 读输出、标记问题、质量门 | scratch |
| `backend-eng` | 写服务端代码 | worktree |
| `frontend-eng` | 写客户端代码 | worktree |
| `ops` | 跑脚本、管理服务、部署 | dir: |

### 编排流程

```
Step 1: 理解目标（有歧义就问，问错比 spawn 错代价低）
    │
    ▼
Step 2: 画出任务图（在回复中口头描述，等用户确认）
    │
    ▼
Step 3: 创建任务并链接依赖
    │  c1 = kanban_create(title="...", assignee="researcher")
    │  c2 = kanban_create(title="...", assignee="researcher")
    │  c3 = kanban_create(title="...", assignee="analyst", parents=[c1, c2])
    │
    ▼
Step 4: 完成自己的编排任务
    │  kanban_complete(summary="拆分为 T1-T3: 2 researcher 并行, 1 analyst 综合")
    │
    ▼
Step 5: 向用户汇报创建了什么
```

---

## 第七部分: 依赖引擎

### 父→子自动提升

任务的初始状态由父任务决定：

```python
# create_task() 中的逻辑 [kanban_db.py:1214]
if parents and any parent not done:
    status = "todo"   # 等待父任务
else:
    status = "ready"  # 直接可用
```

Dispatcher 每个 tick 调用 `recompute_ready()` 检查所有 `todo` 任务——如果所有父任务都 `done`，自动提升为 `ready`。不需要手动协调。

### 环路检测

`link_tasks()` 在添加依赖边之前检查环路：

```python
# 沿 parent 链向上搜索，确保 child_id 不会成为 parent_id 的祖先
def _would_create_cycle(conn, parent_id, child_id):
    visited = {child_id}
    stack = [parent_id]
    while stack:
        pid = stack.pop()
        if pid in visited:
            return True  # 环路!
        visited.add(pid)
        stack.extend(parent_ids(conn, pid))
    return False
```

自链接（`parent_id == child_id`）同样被拒绝。

### 认领时的防御性检查

`claim_task()` 是**唯一的执行前强制检查点**——即使某个代码路径错误地把 `todo`（父任务未完成）的任务设为了 `ready`，`claim_task()` 也会在 CAS 之前验证父任务状态：

```python
undone = conn.execute(
    "SELECT 1 FROM task_links l "
    "JOIN tasks p ON p.id = l.parent_id "
    "WHERE l.child_id = ? AND p.status != 'done' LIMIT 1",
    (task_id,),
).fetchone()
if undone:
    # 降回 todo，等待下一次 recompute_ready()
    conn.execute("UPDATE tasks SET status = 'todo' WHERE id = ? AND status = 'ready'", (task_id,))
    return None
```

---

## 第八部分: 工作空间类型

每个任务可以指定一种工作空间类型（`workspace_kind`）：

| 类型 | 路径 | 行为 |
|------|------|------|
| `scratch` | 自动生成的临时目录 | 可自由读写；任务归档后 GC |
| `dir:<path>` | 指定的绝对路径 | 共享持久目录，其他 run 可以读取 |
| `worktree` | Git worktree 路径 | 如果 `.git` 不存在，先 `git worktree add`；代码需 commit |

```python
# scratch — 默认，适合研究/分析任务
kanban_create(title="调研报告", assignee="researcher")

# dir: — 适合写入特定项目目录
kanban_create(
    title="更新运维文档",
    assignee="writer",
    workspace_kind="dir",
    workspace_path="/home/user/project/docs/",
)

# worktree — 适合编码任务
kanban_create(
    title="修复 SQL 注入漏洞",
    assignee="backend-eng",
    workspace_kind="worktree",
)
```

相对路径的 `workspace_path` 在 Dispatcher spawn 阶段被拒绝（只接受绝对路径）。

---

## 第九部分: 多看板支持

单一看板（`default`）的数据库在 `~/.hermes/kanban.db`。多个看板可以隔离不同项目：

```
~/.hermes/kanban/
├── kanban.db                  ← default 看板（向后兼容）
├── workspaces/                ← default 看板的工作空间
├── logs/                      ← default 看板的日志
├── current                    ← 当前激活的看板 slug
└── boards/
    └── <slug>/                ← 每个额外看板的目录
        ├── kanban.db
        ├── workspaces/
        ├── logs/
        └── board.json         ← 显示元数据（名称、描述、图标、颜色）
```

看板解析优先级（从高到低）：

1. `HERMES_KANBAN_DB` 环境变量（直接 pin 数据库路径）
2. `HERMES_KANBAN_BOARD` 环境变量（Dispatcher 注入给 Worker）
3. `~/.hermes/kanban/current` 文件（`hermes kanban boards switch <slug>` 写入）
4. 默认看板 `default`

Worker 进程被 Dispatcher spawn 时会收到上述所有环境变量，确保即使 profile 切换改变了 `HERMES_HOME`，Worker 的 kanban 路径仍然与 Dispatcher 一致。

### board.json 元数据

```json
{
    "slug": "atm10-server",
    "name": "ATM10 Server",
    "description": "All tasks for the ATM10 game server migration",
    "icon": "🎮",
    "color": "#ff6b6b",
    "created_at": 1747123456,
    "archived": false
}
```

---

## 第十部分: 故障恢复

### Claim 超时回收

每个 `running` 任务的 claim 有效期为 **15 分钟**（`DEFAULT_CLAIM_TTL_SECONDS`）。Dispatcher 的 `release_stale_claims()` 在每个 tick 清理超时 claim：

```python
# 伪代码
stale = SELECT * FROM tasks
        WHERE status = 'running'
        AND claim_expires < now()
for task in stale:
    → task.status = 'ready'  (可被重新认领)
    → task_runs 记录 'timed_out' outcome
```

Worker 通过 `kanban_heartbeat()` 延长 claim TTL，避免长时间运行的任务被误回收。

### 断路器

每个任务有一个 `consecutive_failures` 计数器（重命名为 `spawn_failures`）。任何非成功结局（spawn 失败、超时、崩溃）都会递增。成功完成时重置为 0。

```python
# 断路器逻辑
failure_limit = task.max_retries or config.kanban.failure_limit or 3
if task.consecutive_failures >= failure_limit:
    # 自动 block，不再重试
    block_task(conn, task_id, reason=f"Circuit breaker: {n} consecutive failures")
```

### 恢复操作（Dashboard / CLI）

当 Worker 反复崩溃、幻觉或卡住时：

1. **Reclaim** — 立即中止运行中的 Worker，重置任务为 `ready`
   ```bash
   hermes kanban reclaim <task_id>
   ```
2. **Reassign** — 切换任务到不同 profile
   ```bash
   hermes kanban reassign <task_id> <new-profile> --reclaim
   ```
3. **Change profile model** — 修改 profile 的模型配置后 Reclaim 重试

### 幻觉卡片检测

`kanban_complete(created_cards=[...])` 中的每个 ID 都经过验证：
- 任务必须存在于数据库中
- 任务必须由当前 Worker 的 profile 创建

任何不满足条件的 ID 触发 `HallucinatedCardsError`，completion 被拒绝，事件记录到 task_events 日志。

此外，free-form summary 中的 `t_<hex>` 引用也会被扫描（advisory 级别，不阻塞 completion），在 Dashboard 上标记为警告。

---

## 第十一部分: 完整执行流程示例

以一个"研究是否应迁移到 Postgres"的场景为例，展示 fan-out → fan-in 的完整流程。

### 1. 用户触发

```
用户: 帮我研究是否应该把当前数据库迁移到 Postgres
```

### 2. Orchestrator 拆解

Orchestrator profile 收到任务，进行拆解：

```
T1  researcher  research: Postgres 成本 vs 现状
T2  researcher  research: Postgres 性能 vs 现状
T3  analyst     综合迁移推荐                parents: [T1, T2]
T4  writer      撰写决策备忘录              parents: [T3]
```

### 3. 创建任务

```python
# Orchestrator 调用
t1 = kanban_create(
    title="research: Postgres 成本 vs 现状",
    assignee="researcher",
    body="对比 3 年窗口内的基础设施、迁移和运维成本...",
)
t2 = kanban_create(
    title="research: Postgres 性能 vs 现状",
    assignee="researcher",
    body="对比查询延迟、吞吐量和扩展特性，在预期数据量(~500GB, 10k QPS)下...",
)
t3 = kanban_create(
    title="综合迁移推荐",
    assignee="analyst",
    body="读取 T1(成本)和 T2(性能)的发现，产出 1 页推荐及明确权衡和 go/no-go 建议",
    parents=[t1["task_id"], t2["task_id"]],
)
t4 = kanban_create(
    title="撰写决策备忘录",
    assignee="writer",
    body="将 analyst 的推荐转化为面向 CTO 的 2 页备忘录，匹配团队历史风格",
    parents=[t3["task_id"]],
)
```

### 4. Orchestrator 完成自己的任务

```python
kanban_complete(
    summary="拆分为 T1-T4: 2 researcher 并行调研，1 analyst 综合，1 writer 撰写最终备忘录",
    metadata={
        "task_graph": {
            "T1": {"assignee": "researcher", "parents": []},
            "T2": {"assignee": "researcher", "parents": []},
            "T3": {"assignee": "analyst", "parents": ["T1", "T2"]},
            "T4": {"assignee": "writer", "parents": ["T3"]},
        },
    },
)
```

### 5. Dispatcher 调度执行

```
Tick 1 (T=0):
  → T1 (researcher): claim → spawn worker → running
  → T2 (researcher): claim → spawn worker → running (与 T1 并行!)

Tick 2 (T=60s):
  → T1 worker 完成: summary="Postgres 成本比当前方案高 15%..."
  → T1: done ✓

Tick 3 (T=120s):
  → T2 worker 完成: summary="Postgres 吞吐量在当前负载下高 40%..."
  → T2: done ✓
  → T3: 所有父任务 done → recompute_ready → ready
  → T3 (analyst): claim → spawn worker → running

Tick 4 (T=180s):
  → T3 worker 完成: summary="推荐迁移: 性能收益 > 成本增加..."
  → T3: done ✓
  → T4: 所有父任务 done → ready
  → T4 (writer): claim → spawn worker → running

Tick 5 (T=240s):
  → T4 worker 完成: summary="已撰写 2 页 CTO 备忘录..."
  → T4: done ✓
  → 所有任务完成。Gateway 推送给用户。
```

### 6. 中间有人介入的场景

如果在 T3 执行时，analyst 遇到决策歧义：

```python
# T3 worker 调用的
kanban_block(reason="成本和性能数据互相矛盾——Postgres 成本高 15% 但性能高 40%，权衡取决于预算优先级。请指示。")
```

用户看到 Dashboard 通知 → 打开任务 → 写评论 "优先性能，预算可放宽至 +20%" → `/unblock T3` → Dispatcher 在下一个 tick 重新 spawn analyst Worker → Worker 读取上下文继续执行。

---

## Kanban 工具 vs CLI

Kanban 工具（`kanban_*` 函数调用）和 CLI（`hermes kanban ...`）的设计边界：

| | Kanban 工具 | CLI |
|--|-----------|-----|
| **使用者** | Worker Agent（自动） | 人类操作员 |
| **环境** | 任何后端（Docker/Modal/SSH） | 本地终端 |
| **数据库** | Agent 进程内 Python 直连 | 独立进程连接 |
| **优势** | 跨后端可移植，无 shell 引用问题 | 脚本化、管道化 |

Worker **必须**使用工具而非 CLI——因为 Worker 的 terminal backend 可能指向 Docker/SSH，容器内没有 `hermes` 二进制文件。

---

## 与 delegate_task / 第 10 章的关系

```
delegate_task                         Kanban 看板
─────────────                         ──────────
单次对话中的快速推理                   跨会话持久化工作流
同步等待子 Agent                      异步调度 + 自动重试
无状态                                完整审计轨迹
适合: "读3个文件并总结"                 适合: "研究→分析→撰写→审核" 流水线
```

Kanban 内部也可以使用 `delegate_task`——一个 Worker 在执行自己的任务时，可以将部分推理工作 delegate 出去。但反之不行——`delegate_task` 的临时子 Agent 不应该创建 Kanban 任务（kanban-worker 技能明确禁止了这一点）。

---

## 下一步

Kanban 看板系统覆盖了 Hermes 多 Agent 协作的另一半——持久化、可恢复、带人工审批的工作流。回到 [00-概述与架构总览](00-概述与架构总览.md) 复习整体结构，或回顾 [10-多Agent协作模式](10-多Agent协作模式.md) 对比 `delegate_task` 和 Kanban 的选用场景。
