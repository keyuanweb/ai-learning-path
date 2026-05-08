# LLM 应用架构设计模式

LLM 应用不只是"调 API"。在生产环境中，你需要处理延迟、成本、可靠性、模型选择等多维度的工程挑战。这一章总结经过验证的架构模式。

---

## 1. 路由 (Router)

### 解决的问题

不同的问题需要不同的处理方式。一个简单问候不需要调用 GPT-4o，一次复杂推理没必要走小模型。

### 模式

```
用户输入 → 分类器 → ├→ 简单问题 → 小模型 (7B, 便宜快)
                    ├→ 一般问题 → 中等模型 (70B)
                    └→ 复杂推理 → 大模型 (GPT-4o/DeepSeek-V3)
```

```python
def route_query(query: str) -> str:
    # 第 1 层：关键词规则（几乎零成本）
    if any(word in query for word in ["你好", "谢谢", "再见"]):
        return "small"
    
    # 第 2 层：用小模型分类（成本极低）
    complexity = small_llm.classify(query, categories=[
        "greeting", "factual", "reasoning", "code", "creative"
    ])
    
    routing_table = {
        "greeting": "small",
        "factual": "medium",
        "reasoning": "large",
        "code": "large",
        "creative": "large",
    }
    return routing_table[complexity]
```

### 关键考虑

- 分类器成本 < 被节省的模型调用成本，路由才有收益
- 分类器错误 → 简单问题误入大模型只是多花了钱，复杂问题误入小模型会导致用户体验变差

---

## 2. 缓存 (Cache)

### 解决的问题

相同或相似的问题反复问 → 每次都调 LLM → 浪费钱和时间。

### 三级缓存策略

```python
# 第 1 级：精确缓存（完全相同的输入 → 直接用缓存结果）
exact_cache = {}  # 或用 Redis

# 第 2 级：语义缓存（语义相似的输入 → 复用结果）
from sentence_transformers import SentenceTransformer
encoder = SentenceTransformer('bge-small-zh')

def semantic_cache_lookup(query, threshold=0.95):
    q_embedding = encoder.encode(query)
    for cached_q, cached_embedding, cached_answer in cache:
        similarity = cosine_sim(q_embedding, cached_embedding)
        if similarity > threshold:
            return cached_answer
    return None

# 第 3 级：增量缓存（长文档摘要 → 只重算变化的部分）
```

**缓存效果**：在客服、FAQ 等场景中，缓存命中率可达 60-70%。

---

## 3. 降级 (Fallback)

### 解决的问题

LLM API 会挂。超时、限流、返回异常——生产系统必须能优雅降级。

```python
def generate_with_fallback(prompt, model_preferences):
    errors = []
    
    for model_name in model_preferences:  # 按优先级尝试
        try:
            result = call_llm(model_name, prompt, timeout=30)
            return result
        except TimeoutError as e:
            errors.append(f"{model_name}: 超时")
        except RateLimitError:
            errors.append(f"{model_name}: 限流，换下一个")
        except Exception as e:
            errors.append(f"{model_name}: {e}")
    
    # 所有模型都失败 → 最终降级
    return {
        "answer": "抱歉，服务暂时不可用，请稍后重试。",
        "errors": errors
    }

# 配置多级降级链
model_chain = [
    "deepseek-v3",      # 首选：能力强 + 便宜
    "qwen3-235b",        # 备选 1：中文好
    "gpt-4o",            # 备选 2：兜底
    "local-7b-model",    # 最后手段：本地模型
]
```

---

## 4. 多模型编排 (Multi-Model Orchestration)

### 模式 1：评估 + 优化

```
内容生成模型 (快速) → 输出草稿
评估模型 (挑剔)     → 对草稿打分/提意见
内容生成模型        → 根据反馈修改 → 输出终稿
```

### 模式 2：专项分工

```
通用模型接收请求 → 发现需要代码 → 转发给代码专项模型 → 汇总结果
```

### 模式 3：结果聚合

```
同一个问题发给 3 个不同模型 → 得到 3 个回答 → 用第 4 个模型来综合/投票
```

---

## 5. 流式输出 + 首 token 优化

### 为什么重要

用户等待时间 = 首 token 延迟 + 每个 token 的生成时间。优化首 token 延迟对用户体验影响最大。

```python
# 不阻塞等完整结果，边生成边返回
async for chunk in llm.stream(prompt):
    yield chunk  # 浏览器可以逐字展示

# 优化策略
# 1. 用 MoE 模型（活跃参数少，首 token 快）
# 2. 预填 prompt cache（减少 prompt 处理时间）
# 3. 使用更小的 draft model 做 Speculative Decoding
```

### 实践中

流式输出是 LLM 应用的标准模式。非流式的 30 秒等待 vs 流式的即时反馈——用户体验天差地别。

---

## 6. 输入/输出 Guard

### 输入安全

```python
def input_guard(user_input: str) -> bool:
    """在发给 LLM 之前做安全检查"""
    # 1. 长度检查
    if len(user_input) > max_length:
        return False, "输入过长"  # 防止 token 炸弹

    # 2. 敏感词过滤
    if contains_blocked_patterns(user_input):
        return False, "输入包含不当内容"  # 防 Jailbreak

    # 3. PII 脱敏（可选）
    user_input = mask_pii(user_input)  # 手机号 → [REDACTED]

    return True, user_input
```

### 输出安全

```python
def output_guard(llm_output: str) -> str:
    """在返回给用户之前做安全检查"""
    # 1. 内容安全
    if is_harmful(llm_output):
        return "抱歉，无法生成该内容。"

    # 2. 引用检查（RAG 场景）
    if not is_grounded_in_documents(llm_output, retrieved_docs):
        log_warning("可能的幻觉")

    return llm_output
```

---

## 7. 架构总结

```
用户请求
   ↓
[输入安全 Guard]
   ↓
[路由 Router]  →  选择合适的模型
   ↓
[缓存 Cache]   →  精确匹配 → 直接返回
   ↓
[LLM 调用]     →  主/备/本地 降级链
   ↓
[输出安全 Guard]
   ↓
[流式返回]
   ↓
[日志/监控]    →  记录延迟、成本、错误
```

这是一个经过验证的生产级 LLM 应用架构——不是所有系统都需要全部，但理解每个模块存在的理由，才能按需添加。

---

## 本章速查

| 模式 | 解决的问题 | 代价 |
|------|-----------|------|
| **路由** | 简单问题不浪费大模型 | 需要分类器 |
| **缓存** | 重复问题不重复花钱 | 需要缓存存储 |
| **降级** | API 挂了不断服务 | 需要多模型密钥 |
| **多模型编排** | 单一模型有盲区 | 复杂度 |
| **流式输出** | 减少用户等待感知 | 实现复杂 |
| **入/出 Guard** | 安全 + 内容合规 | 额外的延迟 |
