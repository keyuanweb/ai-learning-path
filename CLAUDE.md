# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库概览

这是 AI 学习路径文档合集，包含 11 个学习路径，全部内容为中文章节化 Markdown 文档。仓库本身没有构建/测试/lint 命令，是纯文档仓库。

## 目录结构

```
11 个学习路径目录/         每个路径按阶段分目录，每阶段含编号文档
agent-harmess/            Harness 原始导图笔记（4篇），供 harness-learning-path 速记参考
code/                     四个参考源码仓库（vllm, vllm-omni, hermes-agent, agency-agents-zh），被 .gitignore 忽略
README.md                 学习路径总索引、11条路径对比表格、学习顺序建议
.gitignore                忽略 code/、node_modules/、dist/、package*.json、.env、scripts/ 等
```

## 文档编写约定

每个学习路径遵循统一的结构模式：
- **阶段目录**：用 `XX-中文名/` 命名（如 `00-入口/`、`01-入门/`）
- **文档文件**：阶段内用 `XX-中文名.md` 命名（如 `01-LangChain核心概念.md`）
- **入口文档**：每个路径第一个阶段必含 `学习路线总览.md`，提供前置要求、阶段 Mermaid 流程图、建议学时
- **环境搭建**：语言/框架类路径必含 `环境搭建.md`，给出 pip 安装命令和虚拟环境配置
- **代码引用**：引用 `code/` 目录下的源文件时使用相对路径（如 `../../code/vllm/vllm/__init__.py`）
- **表格**：用 GitHub 风格表格展示阶段/内容/学时信息

## 新增学习路径时的步骤

1. 创建 `XX-learning-path/` 顶级目录
2. 创建 `00-入口/` 起始阶段目录，内含 `01-学习路线总览.md`
3. 按序创建后续阶段目录和文档
4. 在 [README.md](README.md) 中：
   - 在全景图中添加新路径条目
   - 添加路径详情表格（阶段/内容/学时）
   - 更新学习顺序建议部分的 Mermaid 流程图

## 引用代码目录

- `code/vllm/` — vLLM v0.20.0 源码，供 [vllm-learning-path](vllm-learning-path/) 引用
- `code/vllm-omni/` — vLLM-Omni 源码，供 [vllm-omni-learning-path](vllm-omni-learning-path/) 引用
- `code/hermes-agent/` — Hermes Agent 源码，供 [hermes-learning-path](hermes-learning-path/) 引用
- `code/agency-agents-zh/` — Agency Agents 中文参考源码

这些目录已在 .gitignore 中排除，不纳入版本控制。文档通过相对路径引用其中的源文件（README 中 Hermes 路径简写为 `code/hermes/`，实际目录为 `code/hermes-agent/`）。
