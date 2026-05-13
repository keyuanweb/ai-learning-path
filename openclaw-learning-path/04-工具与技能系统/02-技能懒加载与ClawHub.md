# 技能懒加载与 ClawHub

OpenClaw 的技能系统采用**懒加载（Lazy Loading）**策略，这是它与传统 Agent 框架的重要区别之一。

## 为什么需要懒加载？

传统方式的问题：

```
传统方式（全量注入 Prompt）:
  System Prompt = 基础指令 + 技能1完整文档(3000 tokens)
                          + 技能2完整文档(2500 tokens)
                          + 技能3完整文档(4000 tokens)
                          ...
                          + 技能N完整文档(2000 tokens)
  → 200+ 技能全量注入会消耗 50万+ tokens，大部分永远不会被用到
```

OpenClaw 的懒加载方案：

```
懒加载方式:
  System Prompt = 基础指令 + 技能1元数据(50 tokens)
                          + 技能2元数据(50 tokens)
                          + 技能3元数据(50 tokens)
                          ...
  → 200 技能仅消耗 ~10K tokens（元数据）
  → 当 Agent 决定使用某技能时，通过 read 工具动态加载完整文档
```

## 懒加载机制

### 元数据注入

每个技能在 Prompt 中仅注入最精简的元数据：

```
可用技能:
- name: pdf_generator     desc: 生成 PDF 文档         triggers: 创建PDF/生成报告
- name: image_editor      desc: 编辑和转换图片         triggers: 裁剪/调整大小/格式转换
- name: data_analyzer     desc: 分析 CSV/JSON 数据     triggers: 分析数据/生成图表
- name: code_reviewer     desc: 审查代码质量          triggers: 审查代码/代码检查
...
```

### 动态加载

当 Agent 决策使用某技能时：

```
Agent: "用户需要生成 PDF 报告，我需要查看 pdf_generator 技能的完整用法"

1. Agent 调用: read("~/.openclaw/skills/pdf_generator/SKILL.md")
2. 系统返回:  完整的技能文档（参数、示例、注意事项）
3. Agent 现在知道了:
   - 具体参数格式
   - 依赖的 npm 包
   - 使用示例
   - 常见错误处理
4. Agent 执行: 正确的工具调用序列
```

### Token 节省效果

| 场景 | 全量注入 | 懒加载 | 节省 |
|------|---------|--------|------|
| 10 个技能 | ~25K tokens | ~3K + 按需加载 | ~85% |
| 50 个技能 | ~125K tokens | ~8K + 按需加载 | ~92% |
| 200 个技能 | ~500K tokens | ~12K + 按需加载 | ~97% |

节省的 tokens 可以用于更长的会话历史和更丰富的上下文，显著提升 Agent 的实际表现。

## ClawHub 技能市场

ClawHub 是 OpenClaw 的社区技能市场，类似于 VS Code 的扩展市场。

### 规模与生态

```
ClawHub (截至 2026.03):
  总技能数: 5700+
  分类:
    - 开发工具: ~1800 (Git 工作流、CI/CD、代码生成)
    - 数据处理: ~1200 (ETL、CSV/JSON、数据库)
    - 内容创作: ~900  (文档、图片、音视频)
    - 自动化:   ~800  (定时任务、Webhook、IoT)
    - 安全:     ~500  (漏洞扫描、密钥管理、合规)
    - 其他:     ~500  (游戏、教育、娱乐)
  周下载量: ~200万次
```

### 技能安装

```bash
# 搜索技能
openclaw skill search "pdf generator"

# 安装技能
openclaw skill install pdf_generator

# 查看已安装技能
openclaw skill list

# 卸载技能
openclaw skill uninstall pdf_generator

# 更新所有技能
openclaw skill update
```

### 技能目录结构

每个技能是一个包含标准化文件的目录：

```
skills/pdf_generator/
├── SKILL.md           # 技能主文档（LLM 按需读取）
├── MANIFEST.yaml      # 元数据（名称、描述、触发词、依赖）
├── index.ts           # 技能入口代码
├── tools/             # 技能暴露的工具
│   ├── generate.ts
│   └── template.ts
└── tests/             # 测试
    └── generate.test.ts
```

### MANIFEST.yaml 示例

```yaml
name: pdf_generator
version: 1.2.0
description: 从 Markdown 或 HTML 生成 PDF 文档
triggers:
  - "创建 PDF"
  - "生成 PDF"
  - "导出报告"
  - "pdf"
dependencies:
  npm:
    - puppeteer@21.x
    - marked@12.x
capabilities:
  - file_read
  - file_write
  - shell_exec
```

### 安全警示

ClawHub 的快速增长也带来了安全隐患。2026 年初的安全审计发现：

- **12% 的被审技能**（2,857 中的 ~343 个）包含恶意代码
- 常见恶意行为：凭证窃取、键盘记录、挖矿脚本、数据外泄
- 建议：仅安装**已验证（Verified）**标识的技能，审查技能源码后再使用

OpenClaw 的缓解措施：
- 技能默认在沙箱中运行
- 要求的权限在安装时显式展示
- 社区举报机制
- 定期自动安全扫描

## 与 Hermes 技能系统对比

| 维度 | OpenClaw ClawHub | Hermes Skills |
|------|-----------------|---------------|
| 技能数量 | 5700+ 社区技能 | 27 分类内置技能库 |
| 分发方式 | 中央市场 (ClawHub) | 内置 + 自进化创建 |
| 加载策略 | 懒加载（元数据注入） | 技能注入到 Prompt |
| 创建方式 | 手动编写 + 社区提交 | Agent 自动创建 + 管家族维护 |
| 安全模型 | 沙箱 + Verified 标识 + 审计 | 工具护栏 + 沙箱执行 |
| 更新机制 | 社区维护 + npm 版本管理 | 自修补（Agent 运行时改进） |

> Hermes 的"自进化技能"是独特优势——Agent 完成新任务后自动总结为技能。OpenClaw 则依赖社区生态和手动编写。
