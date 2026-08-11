# Constitution 项目宪章

在 SDD 工作流中，一切从 Constitution 开始。它不是你随手写的 README，而是项目的"最高法"——所有后续的 Spec、Plan、Code 都在它的约束下展开。本章深入讲解 Constitution 的定义、组成、编写方法和版本管理。

---

## 1. 什么是 Constitution

### 1.1 定义

**Constitution（项目宪章）** 是项目的"宪法"——它定义了一组不可变的核心原则和约束。项目中的每一项技术决策、每一行代码、每一次 Code Review，都必须以 Constitution 为准绳。

Constitution 回答的不是"这个功能怎么做"，而是"在这个项目里，**什么能做、什么不能做**"。

### 1.2 与"规范"的区别

初学者最容易混淆的概念就是 Constitution 和 Spec（规范）。两者有本质区别：

| 维度 | Constitution（宪章） | Spec（规范） |
|------|---------------------|-------------|
| **层级** | 项目级，全局生效 | 功能级，仅对该 Feature 生效 |
| **内容** | 核心原则与不可违反的约束 | 具体功能的输入/输出/行为描述 |
| **生命周期** | 长期稳定，极少变更 | 随功能迭代而更新 |
| **约束对象** | 所有人、所有代码、所有决策 | 当前功能的实现者 |
| **类比** | 宪法 | 具体法律条文 |

**举例**：Constitution 规定"所有 API 端点必须通过 JWT 认证"——这是全局约束。而 Spec 规定"用户登录接口接受 email + password，返回 access_token 和 refresh_token"——这是功能级描述。

### 1.3 宪法类比

这是一个有用的思维模型：

> 如果 Spec 是法律条文（描述具体行为规范），Constitution 就是宪法（描述根本原则）。法律条文可以改，但不能违宪。

在实际项目中，这意味着：

- Code Review 时发现代码违反 Constitution？直接打回，不需要讨论。
- 某个技术方案在 Constitution 的约束下走不通？换方案，而不是改 Constitution。
- 新人入职？先读 Constitution，再读 Spec。

### 1.4 在 SDD 工作流中的位置

Constitution 位于 SDD 工作流的最上游：

```
Constitution（宪章）
    ↓ 约束
Specify（规范编写）
    ↓ 约束
Clarify（澄清）
    ↓ 约束
Plan（实施计划）
    ↓ 约束
Tasks（任务分解）
    ↓ 约束
Implement（代码实现）
    ↓ 约束
Verify（验证）
```

它是所有下游活动的"上游约束"。没有 Constitution，Spec 就没有边界；没有边界，AI 生成的代码就会天马行空。

---

## 2. Constitution 的组成要素

一个完整的 Constitution 通常包含以下六大要素。不是每个项目都需要全部六项——根据项目规模和复杂度裁剪。

### 2.1 技术原则

定义项目的技术选型底线：

- **语言选择**：项目使用什么编程语言？是否允许多语言混用？
- **框架约束**：主框架是什么？是否允许引入替代框架？
- **库使用策略**：优先标准库还是优先社区库？第三方库的引入标准是什么？

**示例**：

> - 后端统一使用 Python 3.12+
> - Web 框架固定为 FastAPI，禁止引入 Django 或 Flask
> - 优先使用标准库；引入第三方库需在 PR 中说明理由

### 2.2 架构约束

定义项目的架构边界和设计模式：

- **设计模式要求**：如"所有业务逻辑必须通过 Service 层暴露"
- **模块划分规则**：模块间如何通信？循环依赖如何处理？
- **服务边界**：微服务场景下，服务间如何划分？是否允许共享数据库？

**示例**：

> - 每个微服务独立仓库，通过 REST API 或消息队列通信
> - 禁止服务间共享数据库——每个服务拥有自己的数据存储
> - 所有对外功能必须通过接口（Interface/Protocol）暴露

### 2.3 编码标准

定义代码层面的统一规范：

- **命名规范**：变量、函数、类、文件的命名规则
- **注释要求**：哪些地方必须有注释？Docstring 的语言和格式？
- **代码风格**：使用什么格式化工具？行宽限制？

**示例**：

> - 所有公开函数必须有 Docstring（Google Style）
> - 使用 ruff 进行格式化和 lint，配置纳入版本控制
> - 类型注解（Type Hints）强制要求，mypy 检查必须通过

### 2.4 质量门禁

定义代码合并的最低质量要求：

- **测试覆盖率**：最低覆盖率要求是多少？
- **Code Review 规则**：是否需要至少 X 人 Approve？
- **CI 检查项**：哪些 CI Step 失败会阻止合并？

**示例**：

> - 单元测试覆盖率不低于 80%（以 pytest-cov 报告为准）
> - 每个 PR 至少需要 1 位 Reviewer Approve
> - CI 必须通过 lint、type check、unit test 三项检查

### 2.5 安全规则

定义项目的安全底线——这是最不应该妥协的部分：

- **认证授权策略**：所有端点都需要认证吗？使用什么认证方案？
- **数据保护要求**：敏感数据如何存储和传输？
- **输入验证规则**：所有外部输入如何处理？

**示例**：

> - 所有 API 端点必须通过 JWT 认证，公开端点需显式声明
> - 密码使用 bcrypt 哈希存储，禁止明文或弱哈希
> - 所有用户输入必须经过 Pydantic 校验后再进入业务逻辑

### 2.6 性能基准

定义系统需要满足的性能指标：

- **响应时间上限**：P50/P95/P99 延迟目标
- **吞吐量要求**：最低 QPS/TPS？
- **资源限制**：CPU/内存/连接池的上限？

**示例**：

> - API 响应 P95 < 200ms（不含网络延迟）
> - 数据库连接池 ≤ 20 连接/服务实例
> - 单实例内存使用 ≤ 512MB

---

## 3. Constitution 的编写步骤

Constitution 不是一个人拍脑袋写的——它必须是团队的共同约定。以下是推荐的编写流程：

### Step 1：确定范围

明确这个 Constitution 管什么：

- 是一个微服务的 Constitution？还是整个项目的？
- 是后端专属还是前后端通用的？
- 在 SDD 工作流中，Constitution 约束到哪个环节？

**操作**：在白板或文档中写下"本项目 Constitution 的适用范围是 ________"。

### Step 2：列出核心原则

让团队成员各自写下"无论如何都要遵守的 3-5 件事"，合并去重后投票选出最重要的 5-10 条。

**技巧**：用"我们永远不 ________"或"我们必须 ________"的句式来表达，确保每一条都是可判断真假的陈述句。

### Step 3：细化每条原则

为每条核心原则补充：

1. **具体约束** —— "必须做什么"（可执行的检查项）
2. **反例/禁止** —— "绝对不能出现的情况"（Code Review 时一眼就能认出的模式）
3. **例外条件**（如果有）—— 什么情况下可以不遵守？谁有权批准例外？

### Step 4：团队评审

全员坐在一起（或异步 PR），逐条过：

- 这条原则你真的愿意遵守吗？还是"嘴上说遵守，实际做不到"？
- 如果 AI 生成的代码违反了这条，你愿意重构吗？

**原则**：宁缺毋滥。团队 80% 的人不认可的条款，直接删除。

### Step 5：版本化存储

将最终稿放入版本控制：

```
.specify/memory/constitution.md   # GitHub Spec Kit 约定路径
```

提交 commit，打上版本号。后续所有变更都必须走 PR。

---

## 4. Constitution 模板

以下是一个基于 GitHub Spec Kit 格式、可直接使用的 Constitution 模板。将 `[ ]` 替换为你项目的内容即可。

```markdown
# [PROJECT_NAME] Constitution

## 项目信息

| 字段 | 值 |
|------|-----|
| 项目名称 | [PROJECT_NAME] |
| 技术栈 | [TECH_STACK] |
| 版本 | 1.0.0 |
| 最后更新 | [DATE] |
| 适用范围 | [SCOPE] |

---

## 核心原则

### 原则 1：[原则名称]

**描述**：[一句话描述]

**必须遵守**：
- [具体约束 1]
- [具体约束 2]

**禁止**：
- [反模式 1]
- [反模式 2]

**例外**：[什么情况下可以豁免，谁有权批准]

---

### 原则 2：[原则名称]

**描述**：[一句话描述]

**必须遵守**：
- [具体约束 1]

**禁止**：
- [反模式 1]

---

## 技术原则

- [技术选型约束]

## 架构约束

- [架构与设计模式约束]

## 编码标准

- [代码风格与命名规范]

## 质量门禁

- [测试覆盖率与 CI 要求]

## 安全规则

- [认证授权与数据保护]

## 性能基准

- [延迟与吞吐量指标]

---

*本 Constitution 的变更需遵循语义化版本规范，MAJOR 变更需全团队投票通过。*
```

将此模板保存为 `.specify/memory/constitution.md`，Spec Kit 会自动识别并作为所有 AI Agent 的上下文加载。

---

## 5. 完整示例：一个微服务项目的 Constitution

以下是一个真实可用的微服务项目 Constitution。假设项目名为 "OrderFlow"，是一个订单处理系统。

```markdown
# OrderFlow Constitution

## 项目信息

| 字段 | 值 |
|------|-----|
| 项目名称 | OrderFlow |
| 技术栈 | Python 3.12+, FastAPI, PostgreSQL, Redis |
| 版本 | 1.0.0 |
| 最后更新 | 2026-08-11 |
| 适用范围 | OrderFlow 全部后端微服务 |

---

## 核心原则

### 原则 1：服务独立部署

**描述**：每个微服务拥有独立的代码仓库和数据库，通过 API 通信。

**必须遵守**：
- 每个服务独立仓库，独立 CI/CD 管线
- 服务间通过 REST API 或 RabbitMQ 消息队列通信
- 每个服务拥有自己的 PostgreSQL Schema（禁止跨服务 JOIN）

**禁止**：
- 服务间共享数据库
- 服务间直接导入对方代码模块
- 跨服务同步调用形成循环依赖

### 原则 2：安全优先

**描述**：所有外部输入不可信，所有 API 端点需认证。

**必须遵守**：
- 所有 API 端点通过 JWT 认证（`Authorization: Bearer <token>`）
- 公开端点（如 `/health`、`/metrics`）需显式声明 `PUBLIC_ENDPOINT = True`
- 所有用户输入经 Pydantic 模型校验
- 密码使用 bcrypt 哈希存储

**禁止**：
- 在日志中输出密码、token、个人身份信息
- 使用 MD5/SHA1 作为密码哈希
- SQL 字符串拼接（必须使用 ORM 或参数化查询）

### 原则 3：质量不可妥协

**描述**：测试覆盖率和类型检查是合并的前置条件。

**必须遵守**：
- 单元测试覆盖率 ≥ 80%（pytest-cov）
- 所有公开函数必须有 Type Hints + Docstring（Google Style）
- CI 必须通过：ruff check、mypy、pytest 三项

**禁止**：
- 跳过 CI 直接合并
- 提交包含 `# type: ignore` 的代码（除非有充分理由并在 PR 中说明）

### 原则 4：可观测性内建

**描述**：每个服务必须具备结构化日志、指标和健康检查。

**必须遵守**：
- 使用 `structlog` 输出 JSON 格式日志
- 暴露 `/health`（存活检查）和 `/ready`（就绪检查）端点
- 核心业务操作暴露 Prometheus 指标（请求数、延迟、错误率）

**禁止**：
- 使用 `print()` 替代日志
- 生产环境输出 DEBUG 级别日志

---

## 技术原则

- 后端统一 **Python 3.12+**，类型注解强制开启
- Web 框架固定 **FastAPI**，禁止引入 Django/Flask
- ORM 使用 **SQLAlchemy 2.0+**（async 模式）
- 缓存使用 **Redis**，消息队列使用 **RabbitMQ**
- 优先标准库；引入第三方库需在 PR 描述中说明理由

## 架构约束

- 分层架构：Router → Service → Repository，禁止跨层调用
- 每个服务独立 PostgreSQL Schema，禁止跨 Schema 查询
- 异步 IO 优先，避免在 async 上下文中使用同步阻塞调用

## 编码标准

- 格式化：`ruff format`，行宽 100
- Lint：`ruff check`，规则集 `[pyflakes, pycodestyle, isort]`
- 命名：`snake_case`（变量/函数），`PascalCase`（类），`UPPER_CASE`（常量）
- 所有公开函数必须有 Google Style Docstring

## 质量门禁

- 测试覆盖率 ≥ 80%
- 每个 PR 至少 1 位 Reviewer Approve
- CI 通过检查：ruff → mypy → pytest → coverage
- 覆盖率下降时 CI 告警（不阻止合并，但需要 Reviewer 关注）

## 安全规则

- JWT access_token 有效期 ≤ 15 分钟，refresh_token ≤ 7 天
- 密钥和数据库连接串从环境变量读取，禁止硬编码
- CORS 白名单显式配置，禁止 `allow_origins=["*"]`
- 依赖定期扫描（`pip-audit` 或 Dependabot）

## 性能基准

- API 响应 P95 < 200ms（不含网络延迟）
- 数据库查询单次 < 50ms（ORM 查询需加 `.limit()` 避免全表扫描）
- Redis 操作 < 5ms（本地网络）
- 数据库连接池 ≤ 20 连接/服务实例
- 单实例内存 ≤ 512MB
```

这是一个可以直接拿来做项目的 Constitution。你可以根据自己项目的实际情况增删原则。

---

## 6. 使用 GitHub Spec Kit 生成 Constitution

GitHub Spec Kit 提供了 `/speckit.constitution` 命令，可以用自然语言描述需求，让 AI 帮你生成 Constitution 初稿。

### 6.1 前提条件

已按 [环境搭建](../00-入口/02-环境搭建.md) 完成 Spec Kit 初始化，并且在 AI 编码助手（Claude Code / Cursor / Copilot）中加载了 Spec Kit 的 Agent 配置。

### 6.2 命令示例

在 AI 助手中执行：

```text
/speckit.constitution 创建一个安全优先的微服务项目 Constitution，
使用 Python 3.13、FastAPI、PostgreSQL。强制要求：
- 所有 API 端点需要 JWT 认证
- 测试覆盖率不低于 80%
- 使用 ruff 进行代码格式化
- P95 响应时间不超过 200ms
- 禁止共享数据库，服务间通过 API 通信
```

### 6.3 AI 生成的关键片段

AI 会根据你的需求生成 `constitution.md`。以下是 AI 可能输出的关键片段：

```markdown
# [MyService] Constitution

## 核心原则

### 原则 1：安全优先

**描述**：安全是不可协商的底线。

**必须遵守**：
- 所有 API 端点通过 JWT 认证，`Authorization: Bearer <token>`
- 公开端点需在路由装饰器中显式声明 `require_auth=False`
- 用户输入必须经过 Pydantic BaseModel 校验
- 密码使用 bcrypt（cost factor ≥ 12）哈希存储

**禁止**：
- 硬编码密钥、令牌、密码、连接串
- 在日志或错误消息中输出用户个人信息
- 使用 HTTP（生产环境强制 HTTPS）

...

### 原则 2：质量门禁

**描述**：测试覆盖率是合并的前置条件。

**必须遵守**：
- 单元测试覆盖率 ≥ 80%（pytest-cov --fail-under=80）
- 所有公开函数必须有 type hints + docstring
- CI 必须通过：ruff → mypy → pytest 三项检查

**禁止**：
- skipped/broken CI 状态下合并 PR
- 提交 `# type: ignore` 且无注释说明
```

### 6.4 生成后的操作

AI 生成的 Constitution 是**初稿**，不是终稿。你需要：

1. **审阅**：逐条检查是否符合团队实际——AI 可能过度保守或遗漏关键约束
2. **补充**：添加项目特有的约束（如特定的中间件、公司内部规范）
3. **评审**：走 Step 4 的团队评审流程
4. **提交**：将终稿 commit 到 `.specify/memory/constitution.md`

**经验之谈**：AI 擅长生成模板和常规约束，但对于"我们团队特有的技术债（比如那个祖传的 2000 行函数不能动）"这类上下文，必须人工补充。

---

## 7. Constitution 的版本管理与演进

Constitution 不是写完了就束之高阁的。随着项目发展，它需要演进——但演进必须受控。

### 7.1 语义化版本

采用 SemVer 规范管理 Constitution 版本：

| 版本变更 | 含义 | 示例 |
|---------|------|------|
| **MAJOR**（X.0.0） | 推翻或删除核心原则 | 从"微服务必须独立数据库"改为"允许共享数据库" |
| **MINOR**（0.X.0） | 新增原则或实质性扩展 | 新增一条"所有日志必须使用 structlog"的原则 |
| **PATCH**（0.0.X） | 措辞优化、示例补充、格式调整 | 将"覆盖率 80%"改为"覆盖率 ≥ 80%" |

### 7.2 变更流程

Constitution 的变更比普通代码变更更严格：

```
提出 PR（附变更理由）
    ↓
团队讨论（Slack/会议，所有成员必须参与）
    ↓
投票表决（MAJOR 变更需 2/3 多数通过）
    ↓
更新版本号 + 更新 CHANGELOG
    ↓
合并 PR，全员通知
```

**原则**：MAJOR 变更需要慎重——如果 Constitution 频繁推翻核心原则，说明它一开始就没想清楚。

### 7.3 回退策略

当 Constitution 约束过度时——比如"强制 90% 覆盖率"导致开发效率严重下降——如何处理？

1. **不要直接无视**：违反 Constitution 的代码不应该被合并
2. **提出降级 PR**：将约束调整到合理水平，如 90% → 80%
3. **记录原因**：在 PR 中说明为什么旧约束不可行，数据支持
4. **版本提升为 MINOR**：降低约束也是变更

### 7.4 关键原则：少即是多

> **5-10 条核心原则远好于 30 条没人看的规则。**

这是 Constitution 编写中最重要的经验法则。一个过长的 Constitution 必然导致：

- 成员记不住，Code Review 时不参考
- 约束过多，开发效率下降
- 维护成本高，更新不及时

**实用建议**：写完初稿后，强制删减到 10 条以内。每删一条，问自己："没有这条，项目会出大问题吗？"如果答案是否定的，删掉它。

---

## 8. Constitution 与 AGENTS.md 的关系

在 SDD 工作流中，你可能同时遇到 Constitution 和 AGENTS.md 两个概念。它们有重叠，但定位不同。

### 8.1 定位差异

| 维度 | Constitution | AGENTS.md |
|------|-------------|-----------|
| **面向对象** | 人类开发者 + AI Agent | 主要为 AI Agent |
| **内容性质** | 约束与原则（"什么能做/不能做"） | 上下文信息（"这个项目怎么构建/测试/部署"） |
| **存储位置** | `.specify/memory/constitution.md` | 项目根目录 `AGENTS.md` |
| **变更频率** | 低，团队共识驱动 | 中，随项目结构变化而更新 |
| **工具依赖** | Spec Kit 识别 | sdd-flow 强制要求 |

### 8.2 实际做法

推荐做法：**AGENTS.md 包含 Constitution 的摘要 + 需要 Agent 每次加载的项目上下文。**

```markdown
# AGENTS.md

## 项目概述
...

## 核心约束（摘自 Constitution v1.0.0）

> 完整版见 .specify/memory/constitution.md

- Python 3.12+ / FastAPI / PostgreSQL
- 所有 API 端点需要 JWT 认证
- 测试覆盖率 ≥ 80%
- ruff 格式化，mypy 类型检查
- P95 响应 < 200ms
- 禁止共享数据库

## 构建与测试
...
```

这样的好处：

- AI Agent 每次对话都会加载 AGENTS.md，核心约束自动生效
- Constitution 详细版保持独立，人类详细阅读
- 两者不重复维护——AGENTS.md 引用 Constitution，而不是复制全文

### 8.3 sdd-flow 的特殊要求

如果使用 sdd-flow 插件，项目根目录必须存在 `AGENTS.md`，否则会报错：

```text
FAIL — AGENTS.md missing
```

解决方案：
1. 先写 Constitution（`.specify/memory/constitution.md`）
2. 创建 AGENTS.md，写入项目上下文 + Constitution 核心原则摘要
3. 在 AGENTS.md 中引用 Constitution 路径

---

## 9. 小结

Constitution 是 SDD 的基础约束层。它不是摆设——它决定了"在这个项目里，什么是可能的，什么是不可能的"。

**三个核心要点**：

1. **少即是多**：5-10 条核心原则足矣。没人愿意读 30 条的 Constitution，也不会有人在 Code Review 时参考它。
2. **团队共识 > 文档完备性**：一个完美但没人遵守的 Constitution 毫无价值。反之，一个粗糙但全团队认可的 Constitution 能切实提升代码质量。
3. **先有后优**：不要追求一次性写出完美的 Constitution。写一个基本版本，在项目推进中迭代——但每次迭代都要走正式的变更流程。

**下一步**：Constitution 写好后，就可以进入 SDD 工作流的第二步——[Specify（规范编写）](02-Specify规范编写.md)，学习如何为具体功能编写可执行的规范文档。

---

*Constitution 是一部"活文档"——它需要随着项目演进，但每次演进都必须审慎。就像宪法修正案一样，每一次修改都应该被认真对待。*
