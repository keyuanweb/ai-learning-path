# Human-in-the-Loop (HITL)

## 为什么需要 Human-in-the-Loop

在生产 Agent 系统中，某些操作**必须**经过人工审批：

- 支付/退款操作
- 发送客户邮件
- 修改生产数据库
- 发布公开内容
- 超过一定金额的决策

LangGraph 的 `interrupt()` 机制是**真正的暂停**（不仅是一个确认弹窗），它持久化了当前状态，可以随时恢复、修改甚至从不同路径继续。

## 核心机制

```
graph.invoke() → 执行到 interrupt() → 暂停
                ↓
        人工检查/修改状态
                ↓
     graph.invoke(Command(resume=...)) → 从断点继续
```

## interrupt()：在节点中暂停

```python
from langgraph.types import interrupt

def payment_node(state: PaymentState) -> dict:
    """执行支付前需要人工审批"""
    amount = state["amount"]
    recipient = state["recipient"]

    # 暂停，等待人工决策
    decision = interrupt(f"确认支付 ¥{amount} 给 {recipient}？需要二级审批。")

    if decision == "approved":
        return {"payment_status": "success", "transaction_id": execute_payment(state)}
    else:
        return {"payment_status": "cancelled", "reason": "人工审批未通过"}
```

## 编译时打断点

### interrupt_before：节点执行前暂停

```python
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["sensitive_operation", "send_email"]
)
```

### interrupt_after：节点执行后暂停

```python
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_after=["tool_execution", "llm_decision"]
)
```

## 完整的审批工作流

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langchain_openai import ChatOpenAI

class RefundState(TypedDict):
    order_id: str
    amount: float
    reason: str
    review_result: str   # "approved" / "rejected" / "needs_info"
    reviewer_note: str
    refund_status: str
    final_message: str

llm = ChatOpenAI(model="gpt-4o-mini")

def validate_order(state: RefundState) -> dict:
    """验证订单是否存在、金额是否匹配"""
    if state["amount"] > 10000:
        return {"review_result": "needs_info",
                "reviewer_note": "金额超过 10000，需要高级审批"}
    return {"review_result": "pending_review"}

def auto_review(state: RefundState) -> dict:
    """自动审核：检查退款原因是否合理"""
    prompt = f"""审核以下退款请求：
订单号：{state['order_id']}
金额：¥{state['amount']}
原因：{state['reason']}

判断是否自动通过。规则：金额 < 100 且原因合理则自动通过。"""
    response = llm.invoke(prompt).content.lower()
    if "通过" in response:
        return {"review_result": "auto_approved"}
    return {"review_result": "needs_manual"}

def manual_review(state: RefundState) -> dict:
    """人工审核（interrupt 暂停点）"""
    decision = interrupt(
        f"退款审核请求：\n"
        f"  订单：{state['order_id']}\n"
        f"  金额：¥{state['amount']}\n"
        f"  原因：{state['reason']}\n"
        f"  自动审核意见：{state.get('reviewer_note', 'N/A')}\n\n"
        f"请输入 'approved' 或 'rejected' 或 'request_info'："
    )
    if decision == "approved":
        return {"review_result": "approved", "reviewer_note": "人工审批通过"}
    elif decision == "request_info":
        return {"review_result": "needs_info", "reviewer_note": "需要更多信息"}
    return {"review_result": "rejected", "reviewer_note": "人工审批拒绝"}

def process_refund(state: RefundState) -> dict:
    """执行退款"""
    return {
        "refund_status": "completed",
        "final_message": f"退款 ¥{state['amount']} 已原路返回"
    }

def cancel_refund(state: RefundState) -> dict:
    """取消退款"""
    reason = state.get("reviewer_note", "审核未通过")
    return {
        "refund_status": "cancelled",
        "final_message": f"退款已拒绝：{reason}"
    }

def route_after_review(state: RefundState) -> str:
    result = state.get("review_result", "rejected")
    if result == "approved" or result == "auto_approved":
        return "execute"
    if result == "needs_manual":
        return "manual"
    return "cancel"

# ── 构建 Graph ──
builder = StateGraph(RefundState)
builder.add_node("validate", validate_order)
builder.add_node("auto_review", auto_review)
builder.add_node("manual_review", manual_review)
builder.add_node("execute", process_refund)
builder.add_node("cancel", cancel_refund)

builder.add_edge(START, "validate")
builder.add_conditional_edges("validate", route_after_review, {
    "execute": "execute",
    "manual": "manual_review",
    "cancel": "cancel",
})
builder.add_edge("auto_review", "manual_review")  # 也可以直接到 execute
builder.add_edge("manual_review", "execute")
builder.add_edge("execute", END)
builder.add_edge("cancel", END)

graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["manual_review"]  # 人工审核前暂停
)

# ── 使用演示 ──
config = {"configurable": {"thread_id": "refund-order-12345"}}

# 第一步：提交退款，走到 manual_review 前暂停
result = graph.invoke({
    "order_id": "ORD-2024-001",
    "amount": 500.00,
    "reason": "商品与描述不符，申请退款"
}, config)

# 第二步：检查状态
state = graph.get_state(config)
print(f"等待审批 | 下一步节点：{state.next}")

# 第三步：人工审批通过，恢复执行
graph.invoke(Command(resume="approved"), config)

# 第四步：查看最终结果
final_state = graph.get_state(config)
print(final_state.values.get("final_message"))
```

## HITL 最佳实践

| 原则 | 说明 |
|------|------|
| **关键操作必须暂停** | 支付、删除、发送等不可逆操作 |
| **暂停时提供完整上下文** | 让审批者能做出正确判断 |
| **记录审批轨迹** | 谁审批的、审批结果、时间戳 |
| **支持多种恢复路径** | 通过/拒绝/修改后重试 |
| **超时处理** | 长时间未审批应有降级策略 |

## 实践练习

1. 为上述退款系统增加"修改金额后重试"的恢复路径
2. 实现双人审批：需要两个不同审批者都 approve 才执行
3. 使用 LangSmith 追踪一次完整的 HITL 流程
