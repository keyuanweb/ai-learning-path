# GraphRAG 与知识图谱

传统 RAG 检索孤立的文本块——它不理解文本块之间的关系。GraphRAG 将知识组织成图结构，发现跨越多个文档的隐含关联。

---

## 1. 传统 RAG 的盲区

### 场景

你的知识库有 3 篇文档：
- 文档 A：张三在 2024 年收购了 X 公司
- 文档 B：X 公司发明了 Y 技术
- 文档 C：Y 技术被 Z 实验室进一步改良

用户问："Z 实验室改良了什么技术？" 向量检索可能找到文档 C，但不知道 Y 技术与张三的关系。它丢失了**实体之间的关系链**。

### GraphRAG 的解决思路

> 从文档中抽取实体（人、技术、公司、事件），构建知识图谱，用图的遍历来发现关联。

---

## 2. GraphRAG 的完整流程

```
文档集
  ↓ 1. 实体抽取 (LLM)
实体 + 关系列表
  ↓ 2. 图构建
知识图谱 (节点=实体, 边=关系)
  ↓ 3. 社区检测 (Leiden 算法)
实体分组 (社区=主题)
  ↓ 4. 社区摘要 (LLM)
每个社区生成一段文字摘要
  ↓ 5. 多阶段检索
用户问题 → 匹配社区摘要 → 检索相关实体/关系 → 汇总答案
```

### 步骤 1：实体抽取

```python
# 输入文本
text = "张三于 2024 年收购了 X 公司，这是一家专注于 AI 芯片的初创企业。"

# LLM 抽取
entities = llm.extract(text, schema={
    "entities": [
        {"name": "张三", "type": "PERSON"},
        {"name": "X 公司", "type": "ORGANIZATION"},
        {"name": "AI 芯片", "type": "TECHNOLOGY"}
    ],
    "relationships": [
        {"source": "张三", "target": "X 公司", "relation": "收购", "time": "2024"}
    ]
})
```

### 步骤 2：图构建

```python
import networkx as nx

G = nx.Graph()
for entity in all_entities:
    G.add_node(entity.name, type=entity.type)
for rel in all_relationships:
    G.add_edge(rel.source, rel.target, relation=rel.relation)
```

### 步骤 3：社区检测

将图划分成紧密连接的子群——每个子群代表一个主题（如"AI 芯片行业并购"、"自动驾驶技术链"）。

```python
from graspologic.partition import hierarchical_leiden
community_map = hierarchical_leiden(G)
# 为每个社区调用 LLM 生成摘要
```

### 步骤 4-5：检索与回答

```python
def graphrag_query(question):
    # 第 1 层：匹配社区
    relevant_communities = vector_search(question, community_summaries, top_k=2)
    
    # 第 2 层：在匹配的社区中提取实体和关系
    entities = [e for c in relevant_communities for e in c.entities]
    relationships = [r for c in relevant_communities for r in c.relationships]
    
    # 第 3 层：构造结构化上下文
    context = f"相关实体: {entities}\n关系链: {relationships}"
    
    # 第 4 层：生成答案
    return llm.generate(f"{context}\n\n问题: {question}")
```

---

## 3. 什么时候用 GraphRAG

### 适合

- 需要跨文档关联的复杂查询（"A 和 B 之间有什么关系？"）
- 知识之间有大量关系链（供应链、投资链、技术渊源）
- 需要全局视角而非局部检索（"总结这个领域的核心玩家"）

### 不适合

- 简单事实查询（"X 是什么？"）—— Naive RAG 足够
- 知识之间没有丰富的关系——图构建成本白花了
- 文档量很小——建的图太稀疏，没有社区结构

---

## 4. GraphRAG 的成本

| 步骤 | 成本 | 频率 |
|------|------|------|
| 实体抽取 | 每文档 N 次 LLM 调用 | 建索引时一次性 |
| 社区检测 | 计算成本，非 LLM | 建索引时一次性 |
| 社区摘要 | 每社区 1 次 LLM 调用 | 建索引时一次性 |
| 查询时检索 | 向量检索 + 图遍历 | 每次查询 |

**建索引的 LLM 调用量巨大**——1000 篇文档 × 每篇 3 次调用 = 3000 次 LLM 调用。小规模知识库（<100 篇文档）传统 RAG 更经济。

---

## 5. 与向量 RAG 的结合

实践中 GraphRAG 和向量 RAG 可以互补：

```python
def hybrid_rag(question):
    # 向量检索引擎，擅长找"相似的句子"
    vector_results = vector_rag(question, top_k=5)
    
    # GraphRAG 检索引擎，擅长找"有关联的实体链"
    graph_results = graphrag_query(question)
    
    # 用 LLM 融合两种结果
    final = llm.generate(
        f"基于以下两个信息源回答：\n"
        f"来源 1（文本检索）: {vector_results}\n"
        f"来源 2（知识图谱）: {graph_results}\n"
        f"问题: {question}"
    )
    return final
```

---

## 本章速查

| 概念 | 核心 |
|------|------|
| **GraphRAG 解决的问题** | 发现跨文档的实体关系链 |
| **核心流程** | 实体抽取 → 图构建 → 社区检测 → 社区摘要 → 多阶段检索 |
| **与向量 RAG 的区别** | 向量 RAG 匹配"相似句子"，GraphRAG 匹配"关联实体" |
| **适用场景** | 复杂关联查询、全局总结 |
| **主要成本** | 建索引时的海量 LLM 调用 |
| **框架** | 微软 GraphRAG、Neo4j + LangChain |
