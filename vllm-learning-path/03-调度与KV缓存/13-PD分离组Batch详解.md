# PD 分离组 Batch 全流程

> P 和 D 各自独立调度，通过 `kv_transfer_params` + `KVConnector` 协调。两者 Batch 特征截然不同。

---

## 一、先看全景：两个 Batch 长什么样

同一个请求 X（prompt=4000t），在 P 和 D 两侧的 batch 形态完全不同：

```mermaid
flowchart LR
    subgraph P_BLOCK["⚡ P 侧 Step P2 的 Batch"]
        direction TB
        PB1["<table><tr><td>req_X</td><td>████████████████████████████████████████████████</td><td>2048t Prefill</td></tr><tr><td>req_Y</td><td>████████████████████████████████████████████████</td><td>2048t Prefill</td></tr></table>"]
        PB2["2 个请求 · 4096 tokens<br/>token_budget 吃掉 50%"]
    end

    subgraph D_BLOCK["🔄 D 侧 Step D2 的 Batch（同一时刻）"]
        direction TB
        DB1["<table><tr><td>req_A</td><td>█</td><td>1t Decode</td></tr><tr><td>req_B</td><td>█</td><td>1t Decode</td></tr><tr><td>req_C</td><td>█</td><td>1t Decode</td></tr><tr><td>req_D</td><td>█</td><td>1t Decode</td></tr><tr><td>req_E</td><td>█</td><td>1t Decode</td></tr><tr><td>req_F</td><td>█</td><td>1t Decode</td></tr><tr><td>req_G</td><td>█</td><td>1t Decode</td></tr><tr><td>req_H</td><td>█</td><td>1t Decode</td></tr></table>"]
        DB2["8 个请求 · 8 tokens<br/>token_budget 几乎没动"]
    end

    P_BLOCK -->|"差距 500 倍"| D_BLOCK

    style P_BLOCK fill:#e3f2fd,stroke:#1565c0
    style D_BLOCK fill:#fff3e0,stroke:#e65100
```

**一句话理解：P 是把 token_budget 当饭吃（每个请求吃几千），D 是 token_budget 当空气（每个请求吃 1）。**

---

## 二、P/D 双线并行时间线

下面这张图展示 P 和 D 两个节点**同时**各自调度，同一个请求如何在两侧流转：

```mermaid
gantt
    title P/D 双线时间线（配置: P max_tokens=8192 D max_tokens=512）
    dateFormat X
    axisFormat %s

    section P-⚡req_X(4000t)
    WAITING              :px1, 0, 1
    Prefill chunk 1024t  :px2, 1, 3
    Prefill chunk 2976t  :px3, 3, 5
    完成→kv_transfer_params :milestone, px4, 5, 0

    section P-⚡req_Y(3000t)
    WAITING              :py1, 1, 3
    Prefill chunk 2048t  :py2, 3, 5
    Prefill chunk 952t   :py3, 5, 7
    完成→kv_transfer_params :milestone, py4, 7, 0

    section P-⚡req_Z(10t)
    WAITING              :pz1, 2, 3
    Prefill+完成         :pz2, 3, 4
    完成→kv_transfer_params :milestone, pz3, 4, 0

    section D-🔄req_Z(本地)
    WAITING              :dz1, 0, 1
    Prefill 10t          :dz2, 1, 2
    Decode               :dz3, 2, 9

    section D-🔄req_X(远程KV)
    WAITING_FOR_REMOTE_KVS :dx1, 3, 6
    KV加载中              :crit, dx2, 3, 6
    Decode               :dx3, 6, 12

    section D-🔄req_Y(远程KV)
    WAITING_FOR_REMOTE_KVS :dy1, 5, 8
    KV加载中              :crit, dy2, 5, 8
    Decode               :dy3, 8, 14
```

**关键观察：**
- P 侧：请求大部分时间在**跑 Prefill**（长条），完成后立刻释放线程
- D 侧：请求大部分时间在**跑 Decode**（细长条），开头有一个 `WAITING_FOR_REMOTE_KVS` 的 KV 加载间隙
- P 和 D 是**各自独立调度**的，时间轴没有锁步关系

---

## 三、焦点图：一个请求在 D 侧如何入 Batch

这是 PD 分离最核心的机制——远程 KV 加载期间**分配 blocks 但不消耗 token_budget，不跑 Forward**。

```mermaid
sequenceDiagram
    participant Q as D-Waiting队列
    participant S as D-Scheduler
    participant KC as KVConnector
    participant W as D-Worker(GPU)

    Note over Q,S: === Step N: 发现远程 Prefill 请求 ===

    Q->>S: 取出 req_X (kv_transfer_params.do_remote_prefill=True)

    S->>KC: ① 查远程 KV: get_num_new_matched_tokens()
    KC-->>S: 返回 (4000t 可加载, load_kv_async=True)

    rect rgb(255, 243, 224)
        Note over S: ② 关键决策：load_kv_async=True
        S->>S: allocate_slots(外部4000t, delay_cache_blocks=True)
        Note right of S: 分配 KV blocks ✓<br/>消耗 token_budget ✗<br/>加入 running ✗
        S->>KC: update_state_after_alloc()
        S->>S: req_X → WAITING_FOR_REMOTE_KVS
        Note right of S: 移到 skipped_waiting<br/>继续取下一个 waiting 请求
    end

    Note over S,W: === Forward 执行 ===

    S->>W: SchedulerOutput (含 kv_connector_metadata)
    W->>W: start_load_kv() → RDMA 拉取 KV

    Note over S,W: === Step N+1: KV 还在加载中 ===
    S->>S: req_X 仍在 WAITING_FOR_REMOTE_KVS<br/>→ 跳过, 留在 skipped_waiting

    Note over S,W: === Step N+2: KV 加载完成 ===
    W-->>S: KVConnectorOutput.finished_recving = {req_X}

    Note over S,W: === Step N+3: 提升入 Batch ===
    S->>S: ③ _try_promote_blocked_waiting_request(req_X)
    Note right of S: finished_recving 匹配!<br/>cache_blocks(req_X, 4000)
    S->>S: req_X → WAITING (重新排队)
    S->>S: num_computed=4000, num_new=1<br/>→ allocate(1t) → RUNNING ✓

    rect rgb(200, 230, 201)
        Note over S: ④ 自此正常 Decode<br/>每步 1 token, 直到 max_tokens
    end
```

**核心洞察：步骤②中，4000 tokens 的外部 KV 不占 token_budget。这意味着 D 可以在等 req_X 加载的同时，继续调度其他请求。**

---

## 四、焦点图：P 侧请求完成后发生了什么

```mermaid
sequenceDiagram
    participant S as P-Scheduler
    participant KC as P-KVConnector
    participant Out as EngineCoreOutput
    participant API as API Server

    Note over S: req_X 的最后一个 Prefill chunk 执行完毕

    S->>S: update_from_output(): req_X.num_computed == 4000 ✓

    rect rgb(255, 243, 224)
        Note over S,KC: Prefill 完成 → 不释放 KV blocks!
        S->>KC: request_finished(req_X, block_ids)
        KC->>KC: delay_free_blocks = True
        Note right of KC: KV blocks 保留在 GPU<br/>等待 D 来 RDMA 读取
        KC-->>S: kv_transfer_params = {<br/>  do_remote_prefill: True,<br/>  remote_block_ids: [5,6,7,...],<br/>  remote_engine_id: "P-0",<br/>  remote_host: "10.0.0.1",<br/>  remote_port: 14579<br/>}
    end

    S->>Out: EngineCoreOutput (含 kv_transfer_params)
    Out->>API: 返回给 API Server
    API->>API: 将 kv_transfer_params 注入新 EngineCoreRequest<br/>路由到 D 节点

    Note over KC: 30 秒 lease 超时后<br/>如果 D 没来读, blocks 自动释放
```

---

## 五、P 和 D 的调度决策树对比

```mermaid
flowchart TB
    subgraph P_DECISION["⚡ P 侧: 每个 waiting 请求的处理"]
        direction TB
        PA["取出 waiting 队首请求"] --> PB{"kv_transfer_params<br/>中有 do_remote_decode?"}
        PB -->|"Yes (D转发来)"| PC["和普通请求一样处理<br/>查 prefix cache → allocate → RUNNING"]
        PB -->|"No (本地请求)"| PC
        PC --> PD{"allocate_slots() 成功?"}
        PD -->|"Yes"| PE["→ RUNNING<br/>加入 batch 跑 Prefill"]
        PD -->|"No"| PF["→ 抢占或停止取新请求<br/>KV Cache 满了"]
    end

    subgraph D_DECISION["🔄 D 侧: 每个 waiting 请求的处理"]
        direction TB
        DA["取出 waiting 队首请求"] --> DB{"状态是 WAITING_FOR<br/>_REMOTE_KVS?"}
        DB -->|"Yes (KV加载中)"| DC{"finished_recving<br/>信号到了?"}
        DC -->|"Yes"| DD["→ 提升为 WAITING<br/>重新参与调度"]
        DC -->|"No"| DE["→ 留在 skipped_waiting<br/>不占 token_budget"]
        DB -->|"No (正常 WAITING)"| DF{"kv_transfer_params<br/>中有 do_remote_prefill?"}
        DF -->|"Yes"| DG["→ WAITING_FOR_REMOTE_KVS<br/>分配 blocks, 不进 Forward<br/>不消耗 token_budget!"]
        DF -->|"No"| DH["→ 正常 allocate → RUNNING"]
    end

    style P_DECISION fill:#e3f2fd,stroke:#1565c0
    style D_DECISION fill:#fff3e0,stroke:#e65100
    style DG fill:#ffcc80,stroke:#e65100
```

---

## 六、Batch 组成可视化：P 侧 vs D 侧

```
                          P 侧 Batch                          D 侧 Batch
                       (token_budget=8192)                 (token_budget=512)
                      
    token 用量                          token 用量
    8192 ┬                              512 ┬
         │                                  │
    6144 ┤ ░░░░░░░░░░░░░░░░                 │
         │ ░░░░░░░░░░░░░░░░              384 ┤ ░░░░░░░░░░░░░░░░░░░
    4096 ┤ ░░░░░░░░░░░░░░░░                 │ ░░░░░░░░░░░░░░░░░░░
         │ ░░░  req_Y   ░░░                 │ ░░ 未使用  ░░░░░░░░
    2048 ┤ ░░░  2048t   ░░░              256 ┤ ░░░░░░░░░░░░░░░░░░░
         │ ░░░░░░░░░░░░░░░░                 │ ░░░░░░░░░░░░░░░░░░░
       0 └─███──────────███─             128 ┤ ░░░░░░░░░░░░░░░░░░░
           req_X 2048t                       │ ░░░░░░░░░░░░░░░░░░░
                                             │ ░░░░░░░░░░░░░░░░░░░
         batch: 2 个请求                     0 └─█─█─█─█─█─█─█─█──
         用掉 4096/8192 (50%)                   A B C D E F G H
                                                 各 1t Decode
                                             
                                             batch: 8 个请求
                                             用掉 8/512 (1.5%)
```

---

## 七、同一请求 X 在 P 和 D 的生命周期对照

```mermaid
flowchart TB
    subgraph LIFE["req_X(4000t) 完整生命旅程"]
        direction LR

        subgraph STAGE1["① 到达 P 侧"]
            S1A["API Server 路由到 P"]
            S1B["P: 入 waiting 队列"]
            S1C["P: schedule() → Prefill chunk"]
            S1D["P: 多次 chunk 直到 4000t 完成"]
        end

        subgraph STAGE2["② KV 交接"]
            S2A["P: request_finished()"]
            S2B["P: 生成 kv_transfer_params"]
            S2C["API Server: 路由到 D"]
            S2D["D: 收到请求, 识别 do_remote_prefill"]
        end

        subgraph STAGE3["③ D 侧异步加载"]
            S3A["D: WAITING_FOR_REMOTE_KVS"]
            S3B["D: RDMA 拉取 P 的 KV"]
            S3C["D: 加载完成 → finished_recving"]
        end

        subgraph STAGE4["④ D 侧 Decode"]
            S4A["D: 提升为 WAITING → RUNNING"]
            S4B["D: 每步 1 token Decode"]
            S4C["D: 流式返回给用户"]
        end

        STAGE1 --> STAGE2 --> STAGE3 --> STAGE4
    end

    style STAGE1 fill:#e3f2fd,stroke:#1565c0
    style STAGE2 fill:#fff9c4,stroke:#f9a825
    style STAGE3 fill:#ffcc80,stroke:#e65100
    style STAGE4 fill:#c8e6c9,stroke:#388e3c
```

---

## 八、核心结论

```mermaid
flowchart LR
    subgraph P_SUMMARY["⚡ P 侧 Batch = 算力优先"]
        direction TB
        PS1["少数请求（1~4个）"]
        PS2["每个请求消耗大量 token<br/>(1000~4000t Prefill chunk)"]
        PS3["token_budget 是瓶颈"]
        PS4["请求完成后 KV blocks 不释放<br/>等 D 来 RDMA 读取"]
        PS1 --> PS2 --> PS3 --> PS4
    end

    subgraph D_SUMMARY["🔄 D 侧 Batch = 并发优先"]
        direction TB
        DS1["大量请求（8~64个）"]
        DS2["每个请求消耗 1 token<br/>(Decode 每步生成一个 token)"]
        DS3["token_budget 几乎用不完"]
        DS4["远程 KV 异步加载不占 budget<br/>WAITING_FOR_REMOTE_KVS 是免算等待区"]
        DS1 --> DS2 --> DS3 --> DS4
    end

    style P_SUMMARY fill:#e3f2fd,stroke:#1565c0
    style D_SUMMARY fill:#fff3e0,stroke:#e65100
```

**这就是 PD 分离的根本价值：P 和 D 各自按自己的节奏组 batch，互不干扰。P 可以独立扩容应对 Prefill 突发，D 可以独立扩容应对高并发 Decode。**
