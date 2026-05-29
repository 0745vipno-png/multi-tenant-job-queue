System Design分散式系統常見問答整理
實作這個多租戶 Job Queue 時，遇過最難的挑戰是什麼？
答：「最難的不是寫出功能，而是對抗系統的不確定性。我當時花了很多時間在做防禦性設計。例如我一直在思考：萬一 Worker 沒死，只是因為長耗時 I/O 卡住，在 Lease 過期後突然活過來發起 Ack，要怎麼防止它變成『殭屍』破壞一致性？後來我決定在 ExecutionService 實作雙重校驗，配合狀態機與樂觀鎖的 Token 匹配，直接拒絕非法 Ack，強制殭屍自毀。這比盲目去引入沉重的 Redis 鎖更直觀、更具備確定性

「Lease-based（租約制）」：解決 Worker 消失、任務卡死的問題。
「Idempotent（冪等性）」：確保任務重複跑也不會出事。
「若 Lease 過期且次數未達上限，系統必須在不經人工干預下，自動回退狀態並觸發重試。」

問 : AI 推理動輒 30 秒，HTTP 連線斷線怎麼辦？
答（Lease-based）：
 「AI 任務是昂貴且長耗時的資源。我的系統捨棄了脆弱的 HTTP 同步等待，改用 Lease-based（租約制）非同步引擎。一旦 Worker 在推理過程中斷線，租約過期自動回收並重啟任務，確保高價的 GPU 算力不被幽靈任務榨乾。」

問:高併發下，使用者瘋狂點擊，導致同一個 AI 請求被重複執行（算力加倍浪費）？
答:Idempotent + State Machine）： 「我引入了顯式狀態機（Explicit State Machine）與樂觀鎖（Optimistic Locking），嚴格限制狀態轉移路徑。配合冪等性（Idempotent）設計，即使高併發下發生 Race Condition，系統也從架構層級確保執行權的唯一性，絕對不重複浪費 AI 資源。」

問:為什麼不選「現成的」Redis/Celery？
答 :「現成的工具在極端網路 Partition 或節點崩潰時，容易產生不可預測的狀態。我追求的是 Deterministic（確定性）。透過 Lease-based 租約機制，我能確保任務在任何情況下都『生有處、死有蹤』，這對企業級 AI 簽核來說是安全底線。」

問：「為什麼不用 Redis / RabbitMQ？」
答：「比起導入複雜的基礎設施，我優先選擇『部署確定性』。在當前規模下，SQLite 讓系統達成 Zero-config，且能 100% 驗證邏輯正確性。」

問：「你不怕分散式鎖的問題嗎？」
答：「分散式鎖增加複雜度。我目前採用 Lease-based 模型搭配狀態機，先從架構層級確保『任務執行權』的唯一性，這比依賴外部鎖更直觀。」

問：「為什麼要特地寫狀態機？if-else 不行嗎？
答：「if-else 會產生隱藏狀態。顯式狀態機（Explicit state machine）是為了消除不可能的執行路徑，將 Bug 擋在設計階段。」

問：「Lease-based 的超時設定怎麼拿捏？
答：「這是正確性與恢復速度的權衡。我透過 TimeProvider 讓這個參數可測試，未來能根據不同租戶的作業類型進行動態調優。」

問:Worker 過期前一秒當機會怎樣？
答:「當 Worker 崩潰導致 Lease 過期，LeaseService 會在下一個循環發現該任務已超時且未 Ack。系統會自動重置任務狀態回 Pending，並根據 PolicyService 的 Jitter 重試機制重新派發。因為我的設計是 Idempotent（冪等） 的，所以不用擔心重複執行的風險。」

額外補充問答 
問:SQLite 的併發寫入限制（Write Lock）很明顯，如果未來公司有數萬個任務同時進來，你怎麼辦？」
答:目前選擇 SQLite 是基於 單機確定性 與 零配置部署。當規模擴大到單機 I/O 瓶頸時，因為我的架構採用了 Repository Layer (倉儲層) 與 Domain Layer 解耦，我可以無痛將 Repository 實作替換為 PostgreSQL 或 MySQL，而核心的 Lease 邏輯與狀態機完全不需要改動。這正是 Clean Architecture 的價值。」

問:如果 Worker 的 Lease 過期了，但它其實『沒死』只是卡住了（例如 GC 或長耗時 I/O），後來它突然活過來並嘗試 Ack，你的系統怎麼處理這個『殭屍』？」
答:在 Ack 階段，ExecutionService 會進行第二次校驗。如果資料庫中的 Lease 已經被 LeaseService 宣告過期並重置為 Pending，則該次 Ack 會因為 Version/Token 不匹配 而被拒絕（樂觀鎖）。Worker 會收到一個失敗回傳，自行終止任務，確保數據一致性。」
 殭屍 Worker 額外說明: 這是關於雙重寫入/分散式腦裂的問題
 答： ExecutionService 在 Ack 階段會透過樂觀鎖（Version/Token）進行第二次校驗，直接拒絕過期的 Ack，讓殭屍自行終止。

# Multi-Tenant Job Queue / Task Runner

A production-style, infrastructure-oriented job queue system designed with **deterministic state machines**, **lease-based execution control**, and **multi-tenant isolation**.

This project focuses on **system correctness, failure handling, and execution guarantees**, rather than building a simple queue or background worker.

---

## 🚀 Overview

This system provides a minimal yet robust foundation for:

* background job execution
* worker coordination
* retry handling with backoff
* failure recovery
* multi-tenant workload isolation

It is designed as an **infrastructure component**, not an application.

---

## 🧠 Core Concepts

### 1. Lease-Based Execution

Workers do not own jobs permanently.

Instead, they acquire **temporary execution rights** via leases:

* `lease_token`
* `lease_until`
* `worker_id`

This prevents:

* duplicate execution
* stale worker acknowledgment
* race conditions under concurrency

---

### 2. Explicit State Machines

All entities follow strict lifecycle transitions.

#### Job Lifecycle

```
queued → leased → running → succeeded
                        ↘
                         retry_wait → queued
                        ↘
                         failed / dead_letter
```

#### Lease Lifecycle

```
active → released | expired | revoked
```

#### Worker Lifecycle

```
idle ↔ busy → unhealthy → offline
```

All transitions are enforced in the **Service Layer**, ensuring deterministic behavior.

---

### 3. Multi-Tenant Isolation

Every operation is scoped by:

* `tenant_id`
* `queue_id`

All queries enforce:

```
WHERE tenant_id = ?
```

Cross-tenant access is strictly forbidden.

---

### 4. Retry & Scheduling

Failures are handled explicitly:

* `running → retry_wait`
* exponential backoff
* `available_at` controls re-scheduling

Retry release is handled by a scheduler:

```
retry_wait → queued (when available_at <= now)
```

---

### 5. Failure Recovery

The system is resilient to:

* worker crashes
* lease expiration
* partial execution

Recovery engine:

* detects expired leases
* reclaims stuck jobs
* marks attempts as expired
* moves jobs back into execution

---

## 🏗 Architecture

```
Client / CLI
      │
      ▼
Ingress Layer
      │
      ▼
Tenant Context Layer
      │
      ▼
Service Layer
      │
      ▼
Repository Layer
      │
      ▼
SQLite Storage
```

### Key Layers

* **Domain** → state machines, invariants
* **Service** → business logic enforcement
* **Repository** → persistence only
* **Application** → use-case orchestration
* **Infra** → time, IDs, config

---

## ⚙️ Features

* Lease-based concurrency control
* Deterministic job lifecycle
* Retry with exponential backoff
* Expired lease recovery
* Multi-tenant isolation
* Attempt tracking (execution history)
* CLI-driven execution

---

## 🧪 Quick Start

### 1. Submit a job

```bash
python -m cmd.jobq.cli submit \
  --tenant t1 \
  --queue q1 \
  --payload '{"task": "demo"}'
```

---

### 2. Run worker (single iteration)

```bash
python -m cmd.jobq.cli worker \
  --tenant t1 \
  --queue q1 \
  --worker worker-A
```

---

### 3. Inspect queue

```bash
python -m cmd.jobq.cli inspect \
  --tenant t1 \
  --queue q1
```

---

## 🔁 Execution Flow

```
submit → queued
        ↓
     lease
        ↓
     running
        ↓
   ┌───────────────┐
   │               │
success         failure
   │               │
succeeded     retry_wait
                  ↓
               queued
```

---

## 🔒 System Invariants

* A job may have **at most one active lease**
* Only the lease owner may acknowledge execution
* Expired leases are never valid
* Terminal states cannot re-enter execution
* All operations are tenant-scoped

---

## 🧱 Design Trade-offs

### SQLite (v0.1)

* simple and portable
* limited concurrency
* upgrade path → PostgreSQL

---

### No distributed coordination (yet)

* single-node execution model
* easier to reason about correctness

---

### Explicit over implicit

* retry is explicit
* recovery is explicit
* state transitions are enforced

---

## 📈 Future Improvements

* HTTP API layer
* distributed worker model
* priority queues
* rate limiting
* observability (metrics, dashboards)
* dead-letter monitoring UI

---

## 🎯 What This Project Demonstrates

This project is designed to showcase:

* system design fundamentals
* state machine modeling
* concurrency control via leases
* failure handling & recovery
* multi-tenant system design
* clean architecture (domain/service/repository separation)

---

## 🏁 Conclusion

This is not a simple queue.

It is a **deterministic, fault-tolerant task execution engine** built with infrastructure-grade design principles.

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

### Why AGPL?

This system is designed as an infrastructure component for building
multi-tenant job execution platforms.

AGPL ensures that:

* improvements to the system remain open
* SaaS deployments using modified versions must also share source code

This helps preserve the openness of the system while preventing
closed-source forks of infrastructure built on top of it.

For commercial use cases that require different licensing terms,
please contact the author.

