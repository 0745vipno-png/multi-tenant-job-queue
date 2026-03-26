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

