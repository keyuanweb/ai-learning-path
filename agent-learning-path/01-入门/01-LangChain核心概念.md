# LangChain 核心概念

## 什么是 LangChain

LangChain 是构建 LLM 应用的开源框架，提供 200+ 预构建组件，涵盖 Prompt 模板、链式调用、工具集成、记忆管理等功能。

### 核心组件一览

| 组件 | 说明 | 示例 |
|------|------|------|
| **Model I/O** | LLM 调用抽象 | ChatOpenAI, ChatAnthropic |
| **Prompt Templates** | 动态 Prompt 构造 | ChatPromptTemplate |
| **Chains** | 组合多步骤调用 | LLMChain, SequentialChain |
| **Tools** | LLM 可调用的外部函数 | 搜索、计算器、API 调用 |
| **Memory** | 对话上下文管理 | ConversationBufferMemory |
| **Retrievers** | 文档检索接口 | 向量相似度搜索 |
| **Output Parsers** | 结构化输出解析 | StrOutputParser, JsonOutputParser |

## Model I/O：统一 LLM 调用

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# 同步调用
response = llm.invoke("什么是 LangGraph?")

# 异步调用
response = await llm.ainvoke("什么是 LangGraph?")

# 流式输出
for chunk in llm.stream("讲个故事"):
    print(chunk.content, end="", flush=True)
```

## Prompt Templates：动态构造 Prompt

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}，擅长{skill}。"),
    ("user", "{question}")
])

# 填充模板变量
messages = prompt.invoke({
    "role": "Python 编程专家",
    "skill": "代码调试",
    "question": "如何定位 Python 内存泄漏？"
})
```

### MessagesPlaceholder：动态消息列表

```python
from langchain_core.prompts import MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有用的助手。"),
    MessagesPlaceholder("history"),  # 运行时插入对话历史
    ("user", "{input}")
])
```

## Chains：组合多步骤

### 基础链式调用

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_template("将以下文本翻译为英文：{text}")
parser = StrOutputParser()

chain = prompt | llm | parser

result = chain.invoke({"text": "今天天气真好"})
print(result)  # "The weather is really nice today"
```

## Tools：让 LLM 调用外部函数

```python
from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    """Add two integers together."""
    return a + b

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers together."""
    return a * b

# 绑定工具到 LLM
llm_with_tools = llm.bind_tools([add, multiply])
```

## Memory：对话上下文管理

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

# 在 LangGraph 中使用 checkpoint 实现多轮对话记忆
# 详见 02-图核心/04-状态管理与Checkpoint.md
```

## Output Parsers：结构化输出

```python
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from pydantic import BaseModel, Field

class Translation(BaseModel):
    original: str = Field(description="原始文本")
    translated: str = Field(description="翻译结果")
    language: str = Field(description="目标语言")

parser = JsonOutputParser(pydantic_object=Translation)
```

## 实践练习

1. 使用 `ChatPromptTemplate` 创建一个代码审查 Prompt 模板
2. 用 `|` 管道符组合 prompt + llm + parser
3. 定义一个带类型注解的 `@tool` 函数，并用 `bind_tools` 绑定到 LLM
