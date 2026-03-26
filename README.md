# 🚀 Multi-Tenant Job Queue / Task Runner

A production-style infrastructure system for **reliable background job execution**, built with:

* lease-based execution control
* deterministic state machines
* retry scheduling with backoff
* failure recovery mechanisms
* strict multi-tenant isolation

---

## 🧠 Why This Project

Most job queues focus on usability.

This project focuses on:

```text
correctness, failure handling, and execution guarantees
```

It is designed as an **infrastructure component**, not just a queue.

---

## ⚙️ Core Features

* 🔒 Lease-based concurrency control
* 🔁 Explicit retry with exponential backoff
* 🧩 Deterministic job lifecycle (state machine)
* ♻️ Automatic recovery from worker failure
* 🏢 Multi-tenant isolation (tenant_id scoped)
* 📜 Execution attempt tracking
* 🖥 CLI-driven execution

---

## 🏗 Architecture

```text
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

---

## 🔁 Execution Flow

```text
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

## 🧪 Quick Start

### Submit a job

```bash
python -m cmd.jobq.cli submit \
  --tenant t1 \
  --queue q1 \
  --payload '{"task": "demo"}'
```

---

### Run worker

```bash
python -m cmd.jobq.cli worker \
  --tenant t1 \
  --queue q1 \
  --worker worker-A
```

---

### Inspect jobs

```bash
python -m cmd.jobq.cli inspect \
  --tenant t1 \
  --queue q1
```

---

## 🔒 System Guarantees

* A job has **at most one active lease**
* Only lease owner can acknowledge execution
* Expired leases are invalid
* Terminal states are immutable
* All operations are tenant-scoped

---

## ⚖️ Design Trade-offs

| Decision               | Reason                           |
| ---------------------- | -------------------------------- |
| SQLite                 | Simplicity, easy local execution |
| No distributed lock    | Focus on correctness first       |
| Explicit state machine | Prevent hidden bugs              |
| Lease-based model      | Safe concurrency control         |

---

## 📈 Future Work

* HTTP API
* Distributed workers
* Priority queues
* Rate limiting
* Observability (metrics, dashboard)
* Dead-letter monitoring

---

## 📜 License

Licensed under **AGPL-3.0**

This ensures improvements remain open, especially for SaaS usage.

---

## 🎯 Summary

This is not a simple queue.

It is a **deterministic, fault-tolerant job execution engine**
built with infrastructure-grade design principles.
