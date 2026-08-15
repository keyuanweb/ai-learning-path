# LCEL 表达式语言

## 什么是 LCEL

LCEL（LangChain Expression Language）是 LangChain 的组合式编程接口，使用 `|` 管道运算符连接可运行组件（Runnable），构建类型安全的处理流水线。

## 核心原语

### RunnablePassthrough：透传数据

```python
from langchain_core.runnables import RunnablePassthrough

# 保持原始输入不变并透传
chain = RunnablePassthrough()
chain.invoke("hello")  # "hello"

# 常用于并行分支中透传原始输入
chain = (
    {"original": RunnablePassthrough(), "upper": lambda x: x.upper()}
)
chain.invoke("hello")  # {"original": "hello", "upper": "HELLO"}
```

### RunnableLambda：包装自定义函数

```python
from langchain_core.runnables import RunnableLambda

def word_count(text: str) -> int:
    return len(text.split())

runnable = RunnableLambda(word_count)
runnable.invoke("hello world today")  # 3
```

### RunnableParallel：并行执行

```python
from langchain_core.runnables import RunnableParallel

# 同时执行多个分支
chain = RunnableParallel(
    summary=summarize_chain,
    translation=translate_chain,
    keywords=keyword_chain,
)

result = chain.invoke({"text": "..."})
# result == {"summary": "...", "translation": "...", "keywords": [...]}
```

### RunnableBranch：条件路由

```python
from langchain_core.runnables import RunnableBranch

chain = RunnableBranch(
    (lambda x: "math" in x["topic"].lower(), math_chain),
    (lambda x: "code" in x["topic"].lower(), code_chain),
    general_chain  # default
)
```

## LCEL 在 LangChain 中的应用

### Chain 就是 Runnable 的组合

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_template("翻译为{language}：{text}")
parser = StrOutputParser()

# 每个组件都是一个 Runnable
chain = prompt | llm | parser
#       ↑        ↑      ↑
#    Runnable  Runnable Runnable

# 接口统一
chain.invoke({"language": "英文", "text": "你好"})
chain.ainvoke({"language": "英文", "text": "你好"})   # async
chain.batch([{"language": "英文", "text": "你好"}, ...]) # 批量
chain.stream({"language": "英文", "text": "你好"})     # 流式
```

### 复杂数据流

```python
from langchain_core.runnables import RunnablePassthrough

# 将输入拆分为多个处理通道
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | parser
)

# invoke 只传入 question，retriever 会自动从 question 中提取
chain.invoke("什么是 LangGraph?")
# 实际执行: retriever("什么是 LangGraph?") → context
#          prompt(context=docs, question="什么是 LangGraph?") → ... → answer
```

## LCEL 接口协议

所有 Runnable 都实现统一的接口：

| 方法 | 说明 |
|------|------|
| `invoke(input)` | 同步单次调用 |
| `ainvoke(input)` | 异步单次调用 |
| `batch(inputs)` | 批量调用 |
| `stream(input)` | 流式输出 |
| `astream(input)` | 异步流式 |
| `astream_events(input)` | 异步流式+事件（可观测性） |
| `with_config(config)` | 配置绑定 |
| `with_retry()` | 自动重试 |
| `with_fallbacks([])` | 降级备选 |

## 自定义 Runnable

```python
from langchain_core.runnables import RunnableSerializable
from typing import Any

class WordCountRunnable(RunnableSerializable):
    """自定义 Runnable：统计词数"""

    def invoke(self, input: str, config=None) -> dict:
        words = input.split()
        return {"count": len(words), "words": words}

# 可以像标准组件一样组合
runnable = WordCountRunnable()
chain = runnable | (lambda x: f"共 {x['count']} 个词")
chain.invoke("hello world today")  # "共 3 个词"
```

## 实践练习

1. 用 `RunnableParallel` 同时对一段文本做总结和翻译
2. 用 `RunnableBranch` 根据输入语言选择不同的翻译链
3. 自定义一个 Runnable，实现文本清洗功能（去除 HTML 标签、多余空格）
