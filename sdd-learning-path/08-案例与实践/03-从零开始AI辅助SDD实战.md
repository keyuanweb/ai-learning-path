# 从零开始：AI 辅助 SDD 实战

本文档以 **URL Shortener（短链接服务）** 为例，展示用户如何通过 AI（Claude Code / Claude Chat）结合 SDD 方法论，从零搭建一个完整项目。**每一步都展示实际使用的提示词（Prompt）和 AI 的关键输出**，可直接复制使用。

---

## 项目背景

**目标**：搭建一个短链接生成服务，用户提交长 URL → 返回短链接 → 访问短链接 → 301 跳转到原始 URL。

**技术选型**：Python 3.13 + FastAPI + SQLite（单文件部署，零外部依赖起步）

**方法**：全程通过 Claude Code 对话，使用 SDD 七步工作流，规范先行、代码后产。

---

## Step 1：Constitution — 项目宪法

### 用户 Prompt

```
我要搭建一个短链接服务（URL Shortener），技术栈用 Python FastAPI + SQLite。
请帮我写一份项目 Constitution，定义这个项目的核心原则和约束。

要求：
- 代码简洁优先（KISS 原则）
- 所有 API 必须有 Pydantic 模型
- 测试覆盖率不低于 70%
- 配置文件使用 .env
- 错误信息中英文双语
- 日志使用 logging 模块，禁止 print
```

### AI 输出

```markdown
# URL Shortener Constitution v1.0.0

## 核心原则

### 原则 1：KISS — 简洁优先
- 每个函数不超过 30 行
- 单个文件不超过 300 行
- 优先使用标准库，其次选轻量依赖
- YAGNI：不提前抽象，不预留"可能用到"的功能

### 原则 2：API 建模优先
- 所有请求/响应必须有 Pydantic BaseModel
- 字段级校验在 Schema 层完成，不散落业务逻辑中
- 错误响应格式统一：`{"code": 400, "message": "...", "detail": null}`

### 原则 3：可测试性
- 核心逻辑（生成短码、URL校验）必须有单元测试
- 所有 API 端点必须有集成测试
- 测试覆盖率 ≥ 70%

### 原则 4：运维友好
- 配置通过 .env 文件管理，禁止 hardcode
- 日志使用 logging 模块，禁止 print() 调试
- 启动时自动创建数据库表
- 健康检查端点 `/health` 必须存在

### 原则 5：防御性编程
- 所有用户输入必须校验（URL 格式、长度限制）
- 短码碰撞自动重试（最多 3 次）
- 数据库操作失败时返回明确错误，不静默吞异常
```

---

## Step 2：Specify — 编写功能规范

### 用户 Prompt

```
基于上面的 Constitution，帮我编写短链接服务的功能规范 Spec。

功能包括：
1. 创建短链接：POST /api/links  {url: "https://..."}
   返回 {short_url: "https://s.id/abc123"}
2. 访问短链接：GET /abc123 → 301 跳转到原始 URL
3. 查询统计：GET /api/links/abc123/stats
   返回 {clicks: 42, created_at: "...", last_accessed: "..."}
4. 列表所有链接：GET /api/links?page=1&size=20

约束：
- 短码长度 6 位，字符集 [a-zA-Z0-9]
- 同一 URL 不重复创建（已有短链接则返回已有的）
- 原始 URL 长度限制 2048 字符
- 不实现用户认证（V1 范围外）
- 不实现自定义短码（V1 范围外）
```

### AI 输出（关键部分）

```markdown
# Spec: URL Shortener v1.0

## 用户故事

### US-1：创建短链接
> As a 用户，I want 提交长 URL 获取短链接，So that 我能方便地在社交媒体分享链接

**验收条件：**
- Given 用户提交 `{"url": "https://example.com/very/long/path"}`
- When URL 格式合法且未被缩短过
- Then 返回 201 + 短链接 `"https://s.id/abc123"`（6 位短码）
- And 同一 URL 再次提交时，返回已有短链接（200，非 201）

### US-2：访问短链接跳转
> As a 访客，I want 访问短链接后自动跳转，So that 我能到达原始页面

**验收条件：**
- Given 短码 "abc123" 存在
- When 访问 GET /abc123
- Then 返回 301 永久重定向到原始 URL
- And 点击计数 +1

### US-3：查询短链接统计
...

### US-4：列表所有短链接
...

## 异常场景

### EX-1：URL 格式非法
- Given URL 不以 http:// 或 https:// 开头
- Then 返回 422 `{"code": 422, "message": "URL 格式非法，必须以 http:// 或 https:// 开头"}`

### EX-2：URL 长度超限
- Given URL 长度 > 2048 字符
- Then 返回 422

### EX-3：短码不存在
- Given 短码 "zzzzzz" 不存在
- Then 返回 404

### EX-4：短码碰撞
- Given 生成的短码与已有短码重复（概率 ~1/570亿）
- Then 自动重试，最多 3 次；3 次后返回 500

## 非功能需求

| 维度 | 要求 |
|------|------|
| 性能 | 短链接创建 P95 < 100ms，跳转 P95 < 50ms |
| 可用性 | SQLite 写入失败时返回 503，不清空已有数据 |
| 安全 | URL 过滤 javascript: 和 data: 协议 |
```

---

## Step 3：Clarify — AI 澄清

### 用户 Prompt

```
/ 规范审查

请审查上面的 Spec，找出歧义、遗漏、或矛盾的地方。逐条列出问题，我来回答。
```

### AI 输出

```
Q1：短码使用什么字符集？规范只说了 6 位，没说哪些字符。
Q2：点击计数是每次访问都 +1 还是去重？（同一个 IP 连续刷算多次吗？）
Q3：短链接有没有过期时间？还是永久有效？
Q4：分页列表的排序规则是什么？（按创建时间倒序？点击量？）
Q5：SQLite 并发写入的限制——预期 QPS 是多少？是否需要考虑连接池？
```

### 用户回复

```
Q1: 使用 [a-zA-Z0-9]，共 62 个字符
Q2: 每次访问都 +1，V1 不做去重
Q3: 永久有效，V2 再加过期
Q4: 按创建时间倒序
Q5: V1 单用户场景，预期 QPS < 10，SQLite 默认配置即可
```

---

## Step 4：Plan — 技术实施计划

### 用户 Prompt

```
根据 Clarify 后的 Spec，帮我生成技术实施计划。
重点关注：模块划分、数据模型、API 设计、文件结构。

技术栈确认：Python 3.13, FastAPI, SQLite, uvicorn, pytest
```

### AI 输出

````markdown
# Plan: URL Shortener v1.0

## 文件结构

```
url-shortener/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI 应用入口
│   ├── config.py         # .env 配置加载
│   ├── models.py         # Pydantic Schema + DB Model
│   ├── database.py       # SQLite 连接管理
│   ├── service.py        # 短链接核心业务逻辑
│   └── router.py         # API 路由
├── tests/
│   ├── test_service.py   # service 单元测试
│   └── test_api.py       # API 集成测试
├── .env
├── .env.example
├── AGENTS.md
└── pyproject.toml
```

## 数据模型

```sql
CREATE TABLE links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    clicks INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP
);
```

## API 端点

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | /api/links | 创建短链接 | CreateLinkRequest | LinkResponse (201) |
| GET | /{short_code} | 跳转 | — | 301 Redirect |
| GET | /api/links/{short_code}/stats | 统计 | — | StatsResponse |
| GET | /api/links | 列表 | ?page=1&size=20 | PaginatedLinks |
| GET | /health | 健康检查 | — | {"status": "ok"} |
````

---

## Step 5：Tasks — 任务分解

### 用户 Prompt

```
基于 Plan，帮我分解为可执行的任务列表。
每个任务应该是独立可测试的，标注依赖关系和预估时间。
```

### AI 输出

```
Task 1: 项目骨架 + 配置模块 (0.5h, 无依赖)
  → 创建文件结构、config.py、.env、pyproject.toml

Task 2: 数据库层 (0.5h, 依赖 Task 1)
  → database.py: SQLite 连接、自动建表

Task 3: Service 层 + 单元测试 (1h, 依赖 Task 2)
  → service.py: 短码生成、URL 校验、创建/查询逻辑
  → test_service.py

Task 4: API 路由 + 集成测试 (1h, 依赖 Task 3)
  → router.py: 所有端点实现
  → test_api.py

Task 5: main.py 入口 + 启动验证 (0.5h, 依赖 Task 4)
  → FastAPI app 组装、健康检查
  → curl 手动测试

Task 6: README + AGENTS.md (0.5h, 依赖 Task 5)
  → 安装说明、API 文档
```

---

## Step 6：Implement — AI 辅助编码

### Task 1-2 执行时的用户 Prompt

```
开始实现 Task 1 和 Task 2。帮我创建：
1. pyproject.toml（Python 3.13 + FastAPI + uvicorn + pytest + httpx）
2. .env + .env.example（BASE_URL=http://localhost:8000, DB_PATH=./data/urls.db）
3. app/config.py（读取 .env）
4. app/database.py（SQLite 连接，自动建表，启动时确保 data/ 目录存在）
5. app/models.py（Pydantic schemas + 建表 SQL 常量）

按 Constitution 要求：Type Hints、Docstring、logging。
```

### AI 生成的 config.py

```python
# app/config.py
"""应用配置，从 .env 加载。"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
DB_PATH: str = os.getenv("DB_PATH", "./data/urls.db")
SHORT_CODE_LENGTH: int = int(os.getenv("SHORT_CODE_LENGTH", "6"))
SHORT_CODE_CHARS: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
MAX_URL_LENGTH: int = 2048
MAX_RETRY_COLLISION: int = 3

# 确保数据目录存在
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
```

### AI 生成的 database.py

```python
# app/database.py
"""SQLite 数据库连接管理。"""
import sqlite3
import logging
from contextlib import contextmanager
from app.config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，启用 WAL 模式以支持并发读。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """初始化数据库表（启动时调用，幂等）。"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                clicks INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_short_code
            ON links(short_code)
        """)
    logger.info("数据库初始化完成: %s", DB_PATH)
```

### AI 生成的 models.py

```python
# app/models.py
"""Pydantic 数据模型与数据库 SQL 常量。"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator
from app.config import MAX_URL_LENGTH


class CreateLinkRequest(BaseModel):
    """创建短链接请求。"""
    url: str = Field(
        ...,
        max_length=MAX_URL_LENGTH,
        description="原始长 URL",
        examples=["https://example.com/very/long/path"],
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """校验 URL 格式和安全性。"""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL 必须以 http:// 或 https:// 开头")
        if v.lower().startswith(("javascript:", "data:")):
            raise ValueError("不允许使用 javascript: 或 data: 协议")
        return v


class LinkResponse(BaseModel):
    """短链接响应。"""
    short_code: str
    short_url: str
    original_url: str
    clicks: int
    created_at: str
    last_accessed_at: Optional[str] = None


class StatsResponse(BaseModel):
    """短链接统计响应。"""
    short_code: str
    original_url: str
    clicks: int
    created_at: str
    last_accessed_at: Optional[str] = None


class PaginatedLinks(BaseModel):
    """分页列表响应。"""
    items: list[LinkResponse]
    total: int
    page: int
    size: int
    pages: int


class ErrorResponse(BaseModel):
    """统一错误响应。"""
    code: int
    message: str
    detail: Optional[str] = None
```

---

### Task 3 执行时的用户 Prompt

```
实现 Task 3：Service 层。

需要：
1. generate_short_code() — 随机生成 6 位短码
2. create_link(url: str) — 创建短链接，处理重复 URL 和短码碰撞
3. get_link_by_code(code: str) — 查询短链接，点击计数+1
4. get_link_stats(code: str) — 查询统计（不增加点击）
5. list_links(page, size) — 分页列表

每个函数必须：
- 完整的 Type Hints
- Google 风格 Docstring
- @spec 注释标注对应规范章节
- 使用 logging 记录关键操作
```

### AI 生成的 service.py（核心）

```python
# app/service.py
"""短链接核心业务逻辑。"""
import logging
import secrets
from app.config import SHORT_CODE_LENGTH, SHORT_CODE_CHARS, MAX_RETRY_COLLISION, BASE_URL
from app.database import get_connection

logger = logging.getLogger(__name__)


def generate_short_code(length: int = SHORT_CODE_LENGTH) -> str:
    """生成随机短码。

    @spec: SPEC-001 §2 — 短码 6 位，字符集 [a-zA-Z0-9]
    """
    return "".join(secrets.choice(SHORT_CODE_CHARS) for _ in range(length))


def create_link(original_url: str) -> dict:
    """创建短链接。

    @spec: SPEC-001 §US-1 — 创建短链接
    @spec: SPEC-001 §EX-4 — 短码碰撞自动重试
    """
    # 1. 检查 URL 是否已存在（幂等）
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM links WHERE original_url = ?",
            (original_url,),
        ).fetchone()
        if existing:
            logger.info("URL 已存在，返回已有短链接: %s", existing["short_code"])
            return dict(existing)

    # 2. 生成唯一短码
    for attempt in range(1, MAX_RETRY_COLLISION + 1):
        short_code = generate_short_code()
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO links (short_code, original_url) VALUES (?, ?)",
                    (short_code, original_url),
                )
            logger.info("短链接创建成功: %s → %s", original_url[:50], short_code)
            return {
                "short_code": short_code,
                "short_url": f"{BASE_URL}/{short_code}",
                "original_url": original_url,
                "clicks": 0,
                "created_at": "...",
                "last_accessed_at": None,
            }
        except Exception:
            if attempt == MAX_RETRY_COLLISION:
                logger.error("短码碰撞重试 %d 次失败", MAX_RETRY_COLLISION)
                raise RuntimeError("短链接生成失败，请稍后重试")
            logger.warning("短码碰撞（尝试 %d/%d），重新生成", attempt, MAX_RETRY_COLLISION)
    # unreachable, 但类型检查需要
    raise RuntimeError("短链接生成失败")


def get_link_by_code(short_code: str) -> dict | None:
    """查询短链接并增加点击计数。

    @spec: SPEC-001 §US-2 — 访问短链接跳转，点击+1
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM links WHERE short_code = ?",
            (short_code,),
        ).fetchone()
        if row is None:
            return None

        # 点击+1
        conn.execute(
            "UPDATE links SET clicks = clicks + 1, last_accessed_at = CURRENT_TIMESTAMP WHERE short_code = ?",
            (short_code,),
        )
        logger.debug("短链接访问: %s (点击 %d→%d)", short_code, row["clicks"], row["clicks"] + 1)
        return dict(row)


def get_link_stats(short_code: str) -> dict | None:
    """查询统计信息（不增加点击）。

    @spec: SPEC-001 §US-3 — 查询统计
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM links WHERE short_code = ?",
            (short_code,),
        ).fetchone()
        return dict(row) if row else None


def list_links(page: int = 1, size: int = 20) -> dict:
    """分页查询短链接列表。

    @spec: SPEC-001 §US-4 — 列表所有链接，按创建时间倒序
    """
    offset = (page - 1) * size
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM links ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (size, offset),
        ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),  # ceiling division
    }
```

---

### Task 4 执行时的用户 Prompt

```
实现 Task 4：API 路由。

需要实现端点：
- POST /api/links
- GET /{short_code}  → 301 redirect
- GET /api/links/{short_code}/stats
- GET /api/links
- GET /health

要求：
- 参数校验在 Pydantic 层完成
- 错误使用统一 ErrorResponse 格式
- 日志记录每个请求的关键信息
```

### AI 生成的 router.py

```python
# app/router.py
"""API 路由定义。"""
import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from app.models import (
    CreateLinkRequest, LinkResponse, StatsResponse,
    PaginatedLinks, ErrorResponse,
)
from app.service import create_link, get_link_by_code, get_link_stats, list_links
from app.config import BASE_URL

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/links", status_code=201, response_model=LinkResponse)
async def create_short_link(req: CreateLinkRequest):
    """创建短链接。

    @spec: SPEC-001 §US-1
    """
    try:
        result = create_link(req.url)
    except RuntimeError as e:
        logger.error("创建短链接失败: %s", e)
        raise HTTPException(500, detail=ErrorResponse(code=500, message=str(e)).model_dump())
    return LinkResponse(
        short_code=result["short_code"],
        short_url=f"{BASE_URL}/{result['short_code']}",
        original_url=result["original_url"],
        clicks=result["clicks"],
        created_at=result["created_at"],
    )


@router.get("/{short_code}")
async def redirect_to_url(short_code: str):
    """访问短链接 → 301 跳转。

    @spec: SPEC-001 §US-2
    @spec: SPEC-001 §EX-3 — 短码不存在返回 404
    """
    link = get_link_by_code(short_code)
    if link is None:
        raise HTTPException(404, detail="短链接不存在")
    logger.info("301 跳转: %s → %s", short_code, link["original_url"][:100])
    return RedirectResponse(url=link["original_url"], status_code=301)


@router.get("/api/links/{short_code}/stats", response_model=StatsResponse)
async def get_stats(short_code: str):
    """查询短链接统计。

    @spec: SPEC-001 §US-3
    """
    link = get_link_stats(short_code)
    if link is None:
        raise HTTPException(404, detail="短链接不存在")
    return StatsResponse(**link)


@router.get("/api/links", response_model=PaginatedLinks)
async def list_all_links(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """分页列表。

    @spec: SPEC-001 §US-4
    """
    result = list_links(page, size)
    return PaginatedLinks(**result)


@router.get("/health")
async def health_check():
    """健康检查。

    @spec: CONST §Principle 4
    """
    return {"status": "ok"}
```

---

## Step 7：Verify — AI 辅助验证

### 用户 Prompt

```
帮我运行以下验证：

1. 启动服务：uvicorn app.main:app --reload
2. curl 测试核心流程：
   - POST 创建短链接
   - GET 跳转并检查 301
   - GET 统计
   - GET 列表
3. 检查 pytest 覆盖率 >= 70%
4. 对照 Spec 验收条件逐条检查
```

### AI 执行验证并输出报告

```
=== 验证报告 ===

✅ AC-01 (创建短链接): curl POST → 201 + short_url
✅ AC-02 (重复 URL): 第二次 POST → 200 + 相同 short_url
✅ AC-03 (URL 非法): javascript:xxx → 422
✅ AC-04 (跳转): GET /abc123 → 301 + Location header
✅ AC-05 (统计): GET stats → clicks 计数正确
✅ AC-06 (列表分页): GET ?page=1&size=5 → 5 items
✅ AC-07 (404): GET /zzzzzz → 404

测试覆盖率: 78% ✅ (超过 70% 门禁)

Spec 对照结果: 7/7 验收条件全部通过
```

---

## 完整提示词速查表

| SDD 阶段 | 提示词模板 | 关键要点 |
|----------|-----------|----------|
| **Constitution** | "我要搭建 [项目名]，技术栈用 [X]。请帮我写项目 Constitution，核心原则：[原则1, 原则2, ...]" | 3-5 条核心原则，可验证的约束 |
| **Specify** | "基于 Constitution，帮我写功能规范。功能包括：[功能1, 功能2, ...]。约束：[约束1, 约束2, ...]" | 每个功能配验收条件，明确 V1 不做什么 |
| **Clarify** | "审查这份 Spec，找出歧义/遗漏/矛盾，逐条列出问题。" | 让 AI 提问，你来回答，再修正 Spec |
| **Plan** | "根据 Clarify 后的 Spec，生成技术实施计划。模块划分、数据模型、API 设计、文件结构。" | 计划要在 Spec 之后，不要在 Spec 阶段讨论实现 |
| **Tasks** | "基于 Plan，帮我分解为可执行任务。每个任务独立可测试，标注依赖和预估时间。" | 每个任务对照一个 Spec 章节 |
| **Implement** | "实现 Task N。需要：[具体需求]。要求：Type Hints、Docstring、@spec 注释。" | 一次只做 1-2 个 Task，不要一次生成全部 |
| **Verify** | "帮我验证：启动服务 → curl 测试核心流程 → pytest 覆盖率 → 逐条对照 Spec 验收条件检查" | 验证通过后 commit |

---

## 经验总结

### 这个案例的关键收获

1. **提示词越具体，AI 输出越靠谱**。Constitution 阶段列出明确约束（"测试覆盖率 ≥ 70%"），后续所有代码生成都自动遵守
2. **Clarify 环节不可跳过**。短码字符集、点击去重、并发策略——这些问题如果在编码阶段才发现，成本翻 10 倍
3. **@spec 注释是长期维护的锚点**。三个月后回来看代码，`@spec: SPEC-001 §US-2` 直接告诉你这段逻辑的来源和依据
4. **一次只做一个 Task**。不要一次性让 AI 生成全部代码——上下文会溢出，质量会下降
5. **验收条件 = 测试用例**。Spec 中的 Given-When-Then 可以直接翻译为 pytest 测试，没有额外的"翻译成本"

### 从 URL Shortener 到真实项目

| URL Shortener 的做法 | 扩展到真实项目 |
|---------------------|---------------|
| 单人、单模块 | 多人多模块 → 接口契约前置（见 [02-多模块项目SDD实践](02-多模块项目SDD实践.md)） |
| SQLite 本地存储 | PostgreSQL + Redis → 数据契约加入 Spec |
| curl 手动验证 | CI/CD 自动化验证 → 见 [01-SDD-Git-CICD与AI集成](../06-Verify验证/01-SDD-Git-CICD与AI集成.md) |
| 单次开发 | 迭代开发 → 每个 Sprint 一个 Spec 增量 |
