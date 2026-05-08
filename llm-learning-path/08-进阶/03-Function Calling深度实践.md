# Function Calling 深度实践

Function Calling 是 LLM 和外部世界交互的"插座"。通过它，LLM 能调用任何 API——查天气、搜文档、发消息、执行代码。

---

## 1. Function Calling 解决什么问题

### 元问题

LLM 的核心能力是"生成文本"。但现实世界需要的是"执行操作"。Function Calling 桥接了这个鸿沟——让 LLM 输出一个结构化的函数调用请求，而不是一段自然语言。

```
不是: "你应该调用 get_weather 函数并传入 city='北京'"
而是: {"function": "get_weather", "arguments": {"city": "北京"}}   ← 可以直接被代码解析和执行
```

### 为什么需要结构化输出而非文本

一句话：解析可靠。文本"请设置闹钟为 7 点"比 JSON `{"time": "07:00"}` 更容易出现解析错误。生产系统需要确定性。

---

## 2. 工具定义的完整规范

### 一个标准的 Function 定义

```python
{
    "type": "function",
    "function": {
        "name": "search_documents",                        # 1. 函数名
        "description": "在知识库中搜索相关文档",             # 2. 功能描述
        "parameters": {                                    # 3. 参数 JSON Schema
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或自然语言查询"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 5
                },
                "category": {
                    "type": "string",
                    "enum": ["技术", "产品", "人事"],
                    "description": "搜索范围限定"
                }
            },
            "required": ["query"]                          # 4. 必填参数
        }
    }
}
```

### 四个关键要素

| 要素 | 为什么重要 |
|------|-----------|
| **name** | 清晰的名字让 LLM 一眼知道"这个工具干什么" |
| **description** | LLM 根据描述选择正确的工具，描述错误 → 选错工具 |
| **parameters JSON Schema** | 类型约束让 LLM 知道参数格式，避免生成无效参数 |
| **required** | 明确哪些必填，避免 LLM 漏传 |

---

## 3. 调用完整流程

```python
import json

def function_calling_loop(user_message, tools, llm):
    # Step 1: LLM 判断是否需要调用工具
    messages = [{"role": "user", "content": user_message}]
    response = llm.chat(messages, tools=tools, tool_choice="auto")
    
    # Step 2: 如果 LLM 要求调用工具
    if response.tool_calls:
        for tool_call in response.tool_calls:
            # Step 3: 执行工具
            func = tool_registry[tool_call.function.name]
            args = json.loads(tool_call.function.arguments)
            result = func(**args)
            
            # Step 4: 把结果回传给 LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })
        
        # Step 5: LLM 基于工具结果生成最终回答
        final_response = llm.chat(messages)
        return final_response.content
    
    # LLM 直接回答，不需要工具
    return response.content
```

---

## 4. 错误恢复：3 种常见错误及处理

### 错误 1：参数格式错误

```python
try:
    args = json.loads(tool_call.function.arguments)
except json.JSONDecodeError as e:
    # 让 LLM 修正格式
    messages.append({
        "role": "tool",
        "content": f"参数 JSON 格式错误: {e}。请修正后重新调用。"
    })
    continue  # 重新进入对话循环
```

### 错误 2：缺少必填参数

```python
required = tool_schema["function"]["parameters"].get("required", [])
missing = [p for p in required if p not in args]
if missing:
    messages.append({
        "role": "tool",
        "content": f"缺少必填参数: {missing}。请提供后重新调用。"
    })
    continue
```

### 错误 3：工具执行异常

```python
try:
    result = func(**args)
except Exception as e:
    # 不要让 LLM 看到 Python traceback！
    messages.append({
        "role": "tool",
        "content": f"工具执行失败: {str(e)}。请尝试其他方式获取信息。"
    })
```

---

## 5. 流式调用中的 Tool Calling

### 挑战

流式输出是分块（chunk）到达的。Tool Call 的参数分散在多个 chunk 中，需要先拼起来再 parse。

```python
accumulated_args = ""
tool_call_in_progress = None

for chunk in llm.stream(messages, tools=tools):
    if chunk.tool_calls:
        for tc in chunk.tool_calls:
            if tc.id and tc.function.name:  # 新的 tool call 开始
                tool_call_in_progress = tc
                accumulated_args = ""
            if tc.function.arguments:       # 参数片段
                accumulated_args += tc.function.arguments
                # 不断累积，等收到 finish_reason="tool_calls" 后再 parse
    else:
        yield chunk.content  # 普通文本内容，直接流出
```

---

## 6. 实战建议

| 策略 | 说明 |
|------|------|
| **描述写清楚** | 工具 description 是 LLM 选择工具的唯一依据。写不清楚 → 选错 |
| **限制工具数量** | 一次给 50 个工具 → LLM 选择困难。按场景分组，每个场景 5-10 个 |
| **参数可枚举就枚举** | 能用 `enum` 约束的不要用自由格式 string |
| **大结果截断** | 搜索结果太多 → 只取前几条，控制 token 消耗 |
| **并行调用** | 多个不互相依赖的工具调用可以并行（减少轮次） |
| **强制模式** | `tool_choice="required"` 强制 LLM 必须调用工具，关闭时用 `"none"` |

---

## 本章速查

| 概念 | 关键 |
|------|------|
| **工具定义** | name + description + JSON Schema |
| **调用流程** | LLM判断→执行→回传结果→LLM总结 |
| **错误恢复** | 格式错→让LLM修，缺参数→提醒，执行错→给简洁错误信息 |
| **流式** | 累积参数片段，完成后再 parse |
| **配额管理** | 限制工具数、结果长度、调用深度 |
