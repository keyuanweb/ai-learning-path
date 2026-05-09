# RAG 基础流水线

## 什么是 RAG

RAG（Retrieval-Augmented Generation）是在 LLM 生成回答之前，先从外部知识库检索相关文档，将文档内容注入 Prompt 中，使 LLM 能够基于最新、特定的知识回答。

```
用户提问 → 检索相关文档 → 拼接 Prompt → LLM 生成 → 回答
```

## 完整 RAG 流水线

### 步骤 1：文档加载

```python
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader

# 文本文件
loader = TextLoader("docs/product_manual.txt")
documents = loader.load()

# PDF
loader = PyPDFLoader("docs/report.pdf")
documents = loader.load()

# 网页
loader = WebBaseLoader("https://example.com/docs")
documents = loader.load()
```

### 步骤 2：文本分割

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,        # 每块 500 字符
    chunk_overlap=50,      # 块间重叠 50 字符（保持上下文连贯）
    separators=["\n\n", "\n", "。", "，", " "]  # 优先按段落分，逐渐降级
)

chunks = splitter.split_documents(documents)
print(f"分割为 {len(chunks)} 个文本块")
```

### 步骤 3：Embedding 与向量存储

```python
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# Embedding 模型
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 向量化并存储到 Chroma
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db",  # 持久化目录
    collection_name="product_docs"
)

# 之后可以直接加载已有向量库
# vectorstore = Chroma(
#     persist_directory="./chroma_db",
#     embedding_function=embeddings,
#     collection_name="product_docs"
# )
```

### 步骤 4：检索

```python
# 创建检索器
retriever = vectorstore.as_retriever(
    search_type="similarity",   # 相似度搜索
    search_kwargs={"k": 4}      # 返回 top-4
)

# 检索相关文档
query = "如何重置密码？"
docs = retriever.invoke(query)

for i, doc in enumerate(docs):
    print(f"--- 文档 {i+1} (相似度: {doc.metadata.get('score', 'N/A')}) ---")
    print(doc.page_content[:200])
```

### 步骤 5：RAG Chain 生成

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

llm = ChatOpenAI(model="gpt-4o-mini")

prompt = ChatPromptTemplate.from_messages([
    ("system", """基于以下上下文回答用户问题。如果上下文中没有相关信息，请明确说明。

上下文：
{context}"""),
    ("user", "{question}")
])

def format_docs(docs) -> str:
    """将检索到的文档拼接为上下文字符串"""
    return "\n\n---\n\n".join([
        f"[来源 {i+1}] {doc.page_content}"
        for i, doc in enumerate(docs)
    ])

# 完整 RAG Chain
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

result = rag_chain.invoke("如何重置密码？")
print(result)
```

## RAG 作为 Agent 工具

将 RAG 检索器封装为工具，让 Agent 自主决定何时检索：

```python
from langchain_core.tools import tool

@tool
def knowledge_base_search(query: str) -> str:
    """搜索内部知识库。适用于产品使用、公司政策、技术文档等问题。"""
    docs = retriever.invoke(query)
    if not docs:
        return "未找到相关信息"
    return "\n\n---\n\n".join([
        f"[来源 {i+1}] {doc.page_content[:500]}"
        for i, doc in enumerate(docs[:5])
    ])

# 绑定到 Agent
from langchain.agents import create_agent

agent = create_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[knowledge_base_search],
    system_prompt="你是客服助手，优先使用知识库搜索工具查找答案。"
)
```

## 高级检索策略

### MMR（最大边际相关性）

```python
retriever = vectorstore.as_retriever(
    search_type="mmr",  # 平衡相关性和多样性
    search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": 0.5}
)
```

### 带阈值的相似度搜索

```python
retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.7, "k": 4}
)
```

### 多查询融合

```python
from langchain.retrievers.multi_query import MultiQueryRetriever

multi_retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(),
    llm=ChatOpenAI(model="gpt-4o-mini")
)
# 自动从多个角度重写查询，提高召回率
```

## 实践练习

1. 搭建完整 RAG 流水线（加载 PDF → 分割 → 存储 → 检索 → 生成）
2. 对比 similarity 和 mmr 两种检索模式的返回结果差异
3. 使用 MultiQueryRetriever 提升对模糊问题的检索质量
