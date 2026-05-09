# 04 · OmniCoordinator：多节点部署协调

**源码**：[`code/vllm-omni/vllm_omni/distributed/omni_coordinator/`](../../code/vllm-omni/vllm_omni/distributed/omni_coordinator/)

## OmniCoordinator 是什么

当 vLLM-Omni 部署在**多台机器**上时，需要一个"中央调度中心"来协调各个 Stage 的实例。OmniCoordinator 就是做这件事的。

```
                      OmniCoordinator（中央协调器）
                      ┌────────────────────────┐
                      │  负载均衡               │
                      │  Stage 状态管理          │
                      │  路由决策               │
                      └───┬───────┬────────────┘
                          │       │
              ┌───────────┘       └───────────┐
              ▼                               ▼
    节点 1（GPU 服务器）              节点 2（GPU 服务器）
    ├─ Stage 0 Replica 0             ├─ Stage 0 Replica 2
    └─ Stage 1 Replica 0             └─ Stage 1 Replica 1
```

## 核心组件

### `omni_coordinator.py` —— 主协调器

```python
class OmniCoordinator:
    """
    负责：
    - 维护所有节点的注册信息
    - 接收客户端的注册/心跳
    - 分配请求到具体的 Stage 实例
    - 监控实例健康状态
    """
```

### `load_balancer.py` —— 负载均衡器

```python
class LoadBalancer:
    """
    决定请求应该路由到哪个节点/实例：
    - 轮询（Round Robin）
    - 最少连接数（Least Connections）
    - 最短队列（Shortest Queue）
    - 亲和性路由（一个请求的各 Stage 尽量在同一节点）
    """
```

### `messages.py` —— 通信消息

定义了协调器和客户端之间的消息格式：

```python
# 注册消息
{"type": "register", "node_id": "...", "stage_id": 0, ...}

# 心跳消息
{"type": "heartbeat", "node_id": "...", "load": 0.7, ...}

# 路由请求
{"type": "route_request", "request_id": "...", "target_stage": 1, ...}
```

### `omni_coord_client_for_hub.py` —— 对外入口的客户端

API 服务器（Hub）使用这个客户端连接到 OmniCoordinator，获取路由信息。

### `omni_coord_client_for_stage.py` —— Stage 的客户端

每个 Stage 实例使用这个客户端向 OmniCoordinator 注册自己并上报状态。

## 工作流程

```
1. 启动阶段：
   Stage 实例启动 → 向 OmniCoordinator 注册
   "我是 Stage-0 的 Replica-1，在节点 10.0.0.5:8000"

2. 请求到达：
   API 服务器收到请求 → 询问 OmniCoordinator "Stage 0 有哪些实例可用？"
   OmniCoordinator → 返回负载最低的实例地址

3. 请求处理：
   Stage 0 处理完成 → 通过 OmniConnector 传 KV Cache 给 Stage 1
   （跨节点时通过 Mooncake/Yuanrong）

4. 健康监控：
   Stage 实例定期发心跳 → OmniCoordinator 检测挂掉的实例并移除
```

## Ray Utils

[`ray_utils/`](../../code/vllm-omni/vllm_omni/distributed/ray_utils/) 包含使用 Ray 进行分布式部署的工具：

```python
# ray_utils/utils.py
# 使用 Ray 的 placement group 来管理 GPU 资源分配
# 方便在 Ray 集群上部署 vLLM-Omni
```

## 与 Orchestrator 的关系

```
OmniCoordinator                  Orchestrator
（跨节点协调）                     （单节点内协调）
     │                                │
     ├─ 决定请求去哪个节点             ├─ 决定请求去哪个 Stage
     ├─ 节点级别负载均衡               ├─ Stage 级别流水线
     └─ 多节点拓扑管理                 └─ 请求生命周期管理
```

OmniCoordinator 是 Orchestrator 的"上一级"：先决定请求去哪个节点，然后由该节点的 Orchestrator 负责请求在该节点内部的 Stage 间流转。

## 阅读时间

约 20 分钟。如果你只在单机部署，可以跳过这一节。多节点部署时再回头看即可。
