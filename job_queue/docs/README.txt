### 🧠 Advanced Architectural Decisions: Brain-Split & Fencing Mitigation

In a distributed environment, transient network partitions or prolonged worker garbage collection (GC) pauses can lead to the notorious **"Zombie Worker" (Straggler) problem**, causing **Brain-Split scenarios** where multiple workers attempt to mutate state simultaneously.

This system guarantees strict data consistency against brain-split through an industrial-grade **Token/Epoch Fencing Mechanism**:

1. **Server-Side Truth**: Real-time state and lease tracking are strictly confined to the centralized database (`NOW()` evaluation and version anchoring). 
2. **Generational Tokens**: When a tenant lease expires, the system increments the `version_token` (Epoch). The old token held by the zombie worker is instantly revoked system-wide.
3. **Side-Effect Fencing**: To prevent un-fenced zombie workers from polluting external downstream storage (e.g., AWS S3) prior to database acknowledgment, all artifact paths are deterministically isolated using the snapshot pattern: `job_id_version_token.json`. 
4. **Optimistic Guard**: Any stale acknowledgement or out-of-order write attempts from a partitioned worker will trigger an optimistic locking failure, forcing the zombie worker to gracefully self-terminate.


# 深入探討：極端場景下的防禦性設計 (Deep Dive: Defensive Design for Edge Cases)
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
--------------------------------------------------------------------------------------------------------------------------

進階難度問答題:

問:多租戶（Multi-tenant），假設 A 租戶是個大戶，一秒鐘塞了 10 萬個高優先級（High Priority）的 AI 簽核任務進來；而 B 租戶是小客戶，只發了一個任務。在 Priority + Lease 機制下，B 租戶的任務會被完全餓死（Starvation）。要怎麼修改你的任務獲取（Polling/Lease）邏輯，在不幫每個租戶開獨立資料庫與獨立獨立機器的前提下，兼顧『高優先級優先』與『租戶間的資源公平性（Fairness）』？」

答:「這確實是多租戶最頭痛的『雜訊鄰居』問題。單純依賴全域的 priority 欄位一定會導致小客戶被餓死。為了在單一 SQLite/PostgreSQL 中解決，我會引入 Fair-Share 派發演算法 或 租約配額制（Quota）。具體做法是，在 LeaseService 撈取任務時，SQL 不能只下 ORDER BY priority DESC。我會調整為 帶有租戶配額的權重隨機（Weighted Random） 或 按租戶分組的 Window Function。例如：限制每次 Batch 取出 100 個任務時，單一 TenantID 的佔比不能超過 30%。如果超過，剩餘的份額強制留給其他 Tenant 的任務。這樣既能保證大戶的緊急任務被快速處理，也能確保小客戶得到基本的服務承諾（SLA）。」

問:前面提到了 Lease-based 租約機制，還提到 TimeProvider 來做測試。但現實中， Job Queue 服務可能部署在伺服器 A，而那群 Worker 部署在不同的伺服器 B、C、D 上。各台機器的硬體時鐘一定存在微小的時鐘偏移（Clock Skew），甚至 NTP 同步時會出現『時間跳變（Time Jump）』。如果 Worker B 的系統時間比伺服器 A 快了整整 5 秒，你的 Lease 超時判定與樂觀鎖 Token 檢查，會不會因為這個時間差直接崩潰？你怎麼在軟體層面做到對時鐘的不依賴？」

答:這就是為什麼我的 Lease 機制絕對不依賴 Worker 端的系統時間，時間的絕對真理只能存在於中央資料庫（Server-side）。當 Worker 來領取任務時，資料庫會用 NOW() + 30s 計算過期時間，但回傳給 Worker 的不是一個絕對的時間戳（Timestamp），而是一個相對的租約長度（TTL，例如 30 秒）。Worker 內部自己倒數 30 秒。如果快到期了，Worker 必須主動發起『續租（Renew Lease）』請求。而在最終的 Ack 階段，我的樂觀鎖校驗只比對資料庫內的 version_token，完全不看 Worker 帶過來的時間。透過『中央決定絕對時間，客戶端只用相對時間』的設計，時鐘偏移對我的系統一致性零影響。」

問:『殭屍 Worker 雙重校驗』。假設 Worker 處理的是一個長耗時 AI 任務，它在執行第 29 秒時，Lease 剛好過期。此時，中央資料庫認定它死了，把任務重置並派給了 Worker 2。就在這一瞬間，原本卡住的 Worker 1 突然醒了，它剛好執行到最後一步：把 AI 算好的巨量結果資料（例如 50MB 的分析報告）寫入另一個獨立的儲存服務（如 AWS S3），然後才回頭來找你的資料庫 Ack。這時候你的資料庫樂觀鎖確實會拒絕它的 Ack，但那份 50MB 的產出已經被錯誤地寫進 S3、覆蓋掉正確的資料了。這種在 Ack 之前的外部寫入副作用，要怎麼攔截？」

(柵欄機制是專門處理分散式系統腦裂的作法)

答:「這涉及到了分散式系統中的 Fencing（柵欄機制）。當我們無法阻止殭屍 Worker 向外部第三方服務（如 S3）發起寫入時，我們必須讓第三方服務也具備識別『過期憑證』的能力。我的解決方案有兩個層級：
儲存端版本化（Versioning）：S3 的檔案命名不能用固定的 report.json，必須強制帶上 job_id_version_token.json。這樣 Worker 1 與 Worker 2 寫入的是不同的物件，不發生覆蓋。
條件式寫入（Conditional Upload）：在寫入儲存體或進行下一個破壞性操作前，Worker 必須實作『內部檢查點（Checkpoint）』。它必須先向 ExecutionService 發起一個輕量級的 is_lease_valid() 預檢。雖然這無法 100% 消除時序上的 Race Condition（TOCTOU 漏洞），但搭配物件版本化，就能徹底確保最終數據的正確性。」

問:「用 job_id_version_token 分開寫入 S3 成功解決了覆蓋問題。但最後到底是誰來決定哪一個檔案才是『最終真理』？是不是在樂觀鎖 Ack 成功的那個 Worker，才有權力去更新一個 latest_report_pointer 的資料庫欄位？」
答:沒錯！只有 Ack 成功的 Worker，它的 Version Token 才會寫入 DB 主表，這時 DB 內的欄位就是唯一真理的 Pointer。)

問:「在高併發下，每次 Polling 都用 Window Function 做 30% 的 Tenant 篩選，SQLite 的 CPU 可能會吃滿。未來如果要轉向 PostgreSQL，你會怎麼優化這個公平調度佇列？」
答:：未來可以引入 Redis 的 ZSET（有序集合）為每個 Tenant 做權重滑動視窗，或者在應用層（Application Layer）實作變形的使用者權杖桶（Token Bucket），把這層計算從關聯式 DB 剝離。

--------------底下為架構圖的設計-------------------------------

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

