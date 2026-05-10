# 第一个 Chain

## 目标

构建一个带 Prompt 模板 + LLM + 输出解析器的完整翻译 Chain，理解 LCEL 管道的完整数据流。

## 完整代码

```python
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. 配置 LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    api_key=os.environ.get("OPENAI_API_KEY", "sk-...")
)

# 2. 定义 Prompt 模板
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业的翻译助手。请将用户输入的文本翻译为{target_language}。只返回翻译结果，不要添加任何解释。"),
    ("user", "{text}")
])

# 3. 输出解析器
parser = StrOutputParser()

# 4. 组装 Chain
translate_chain = prompt | llm | parser

# 5. 调用 Chain
result = translate_chain.invoke({
    "target_language": "英文",
    "text": "人工智能正在改变我们与计算机交互的方式"
})

print(result)
# 输出: "Artificial intelligence is changing the way we interact with computers."
```

## 数据流解析

```mermaid
flowchart TD
    A['invoke({"target_language": "英文", "text": "人工智能..."})'] --> B["[Prompt] 填充模板变量，生成 Message 列表"]
    B --> C["[LLM] 发送 Message 到 GPT-4o-mini，获取 AIMessage"]
    C --> D["[Parser] 从 AIMessage 中提取 content 字符串"]
    D --> E['"Artificial intelligence is changing..."']
```

## 扩展：多语言翻译批处理

```python
inputs = [
    {"target_language": "英文", "text": "今天天气真好"},
    {"target_language": "日文", "text": "你好世界"},
    {"target_language": "法文", "text": "机器学习很有趣"},
]

# 批量调用（内部会并行处理）
results = translate_chain.batch(inputs)
for inp, res in zip(inputs, results):
    print(f"{inp['text']} → ({inp['target_language']}) {res}")
```

## 扩展：流式输出

```python
for chunk in translate_chain.stream({
    "target_language": "英文",
    "text": "人工智能正在改变我们与计算机交互的方式"
}):
    print(chunk, end="", flush=True)
```

## 扩展：带 JSON 输出的翻译 Chain

```python
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser

class TranslationResult(BaseModel):
    source_text: str = Field(description="原文")
    target_text: str = Field(description="译文")
    target_language: str = Field(description="目标语言")
    confidence: float = Field(description="翻译置信度 0-1")

json_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个翻译助手。将用户输入翻译为{target_language}。
返回 JSON 格式：{{"source_text": "原文", "target_text": "译文", "target_language": "语言", "confidence": 0.95}}"""),
    ("user", "{text}")
])

json_parser = JsonOutputParser(pydantic_object=TranslationResult)
json_chain = json_prompt | llm | json_parser

result = json_chain.invoke({
    "target_language": "English",
    "text": "深度学习是机器学习的一个子集"
})
print(f"译文: {result['target_text']}")
print(f"置信度: {result['confidence']}")
```

## 实践练习

1. 修改 Prompt 模板，支持指定翻译风格（正式/口语/学术）
2. 增加一个 RunnableLambda 步骤，对 LLM 输出做后处理（去除首尾空白、标点规范化）
3. 尝试用 `with_fallbacks` 为链配置备选模型降级方案
