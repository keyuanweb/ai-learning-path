# LangGraph Platform

## 什么是 LangGraph Platform

LangGraph Platform 是 LangGraph 的生产化部署平台，提供 API 服务化、自动扩容、CI/CD 集成等能力。支持云托管（LangGraph Cloud）和自托管（Self-Hosted）两种方式。

## 从开发到部署

```
开发阶段                      部署阶段
┌──────────┐               ┌──────────────┐
│ Python   │               │ LangGraph     │
│ StateGraph ─── deploy ───→ Platform      │
│ local dev │               │ (Cloud/Self) │
└──────────┘               └──────────────┘
                                    │
                            ┌───────┴───────┐
                            │  REST API     │
                            │  Streaming    │
                            │  Cron Jobs    │
                            │  Webhooks     │
                            └───────────────┘
```

## LangGraph Cloud 部署

### 项目结构

```
my-agent-app/
├── langgraph.json          # 部署配置
├── requirements.txt
├── agent.py                # Graph 定义
└── .env                    # 环境变量
```

### langgraph.json

```json
{
  "dependencies": ["./agent.py"],
  "graphs": {
    "customer_service": "./agent.py:graph",
    "research": "./agent.py:deep_research_graph"
  },
  "env": ".env",
  "python_version": "3.12"
}
```

### agent.py

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

# 定义并编译 Graph
agent = create_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[search_tool, calc_tool],
    system_prompt="你是一个客服助手"
)

# Graph 会被 Platform 自动加载为 API 端点
# graph 是模块级别的变量，是 Platform 的入口
graph = agent  # 或 agent.compile(checkpointer=MemorySaver())
```

### 部署命令

```bash
# 安装 CLI
pip install langgraph-cli

# 登录
langgraph login

# 部署到 LangGraph Cloud
langgraph deploy --project my-agent-app
```

## LangGraph Server API

部署后自动获得以下 API 端点：

### 1. 基础调用

```python
# POST /runs
import requests

response = requests.post(
    "https://my-agent-app.langgraph.app/runs",
    json={
        "graph_id": "customer_service",
        "input": {
            "messages": [{"role": "user", "content": "如何退货？"}]
        },
        "config": {
            "configurable": {"thread_id": "user-123"}
        }
    }
)
result = response.json()
```

### 2. 流式调用

```python
# POST /runs/stream
response = requests.post(
    "https://my-agent-app.langgraph.app/runs/stream",
    json={
        "graph_id": "customer_service",
        "input": {
            "messages": [{"role": "user", "content": "..."}]
        }
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        event = json.loads(line)
        # event["event"]: "messages", "updates", "metadata", etc.
        print(f"[{event['event']}] {event.get('data', '')}")
```

### 3. 查询 State

```python
# GET /threads/{thread_id}/state
r = requests.get(
    "https://my-agent-app.langgraph.app/threads/user-123/state"
)
state = r.json()
print(state["values"]["messages"])
```

### 4. 查看历史

```python
# GET /threads/{thread_id}/state/history
r = requests.get(
    "https://my-agent-app.langgraph.app/threads/user-123/state/history"
)
history = r.json()
for snapshot in history:
    print(f"Step {snapshot['metadata'].get('step')}")
```

## 自托管部署

### Docker 部署

```dockerfile
FROM langchain/langgraph-server:latest

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt

ENV LANGGRAPH_CONFIG=/app/langgraph.json

EXPOSE 8000
CMD ["langgraph", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t my-agent-app .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e LANGCHAIN_API_KEY=$LANGCHAIN_API_KEY \
  my-agent-app
```

### Kubernetes 部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: langgraph-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: langgraph-agent
  template:
    metadata:
      labels:
        app: langgraph-agent
    spec:
      containers:
      - name: agent
        image: my-agent-app:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: langgraph-agent-svc
spec:
  selector:
    app: langgraph-agent
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Cron Jobs 与异步任务

```json
{
  "dependencies": ["./agent.py"],
  "graphs": {
    "customer_service": "./agent.py:graph"
  },
  "crons": [{
    "schedule": "0 3 * * *",
    "graph_id": "report_generator",
    "input": {"task": "生成每日客服数据报告"}
  }]
}
```

## 环境管理

```python
# 使用不同环境
config = {
    "configurable": {"thread_id": "user-123"},
    "metadata": {
        "environment": "production",   # prod / staging / dev
        "version": "1.2.3"
    }
}
```

## 生产化 Checklist

| 项 | 说明 |
|----|------|
| ✅ Checkpointer | 持久化到 Postgres/SQLite（不能用 MemorySaver） |
| ✅ 环境变量 | API Key 通过 Secret 管理，不写在代码中 |
| ✅ 健康检查 | `/health` 端点返回正常 |
| ✅ 日志 | 结构化日志 + LangSmith Trace |
| ✅ 限流 | 根据用户/API Key 设置调用频率限制 |
| ✅ 错误处理 | 所有 API 调用有重试和降级 |
| ✅ 监控告警 | 延迟、错误率、Token 用量的告警规则 |

## 实践练习

1. 将一个本地 Agent 项目改造为 langgraph.json 格式
2. 使用 `langgraph dev` 在本地启动 Server 并测试 API
3. 部署到自托管 Docker 环境并测试流式调用
