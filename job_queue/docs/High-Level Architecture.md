Multi-Tenant Job Queue / Task Runner
High-Level Architecture (v0.1)

Goal
-----
A multi-tenant infrastructure service for submitting, leasing,
executing, retrying, and tracking background jobs with clear
tenant isolation and deterministic job lifecycle handling.


────────────────────────────────────────────────────────────────────

[User / Operator / Client]

    │
    │ submits jobs / queries status / acknowledges results
    ▼

[Ingress Layer]
  - CLI commands
  - future HTTP API
  - future worker clients

  Example operations:
  - submit job
  - lease job
  - ack job
  - fail job
  - retry job
  - inspect queue
  - inspect worker

    │
    │ resolves tenant context
    ▼

[Tenant Context Layer]
  Responsible for binding every operation to a tenant.

  Provides:
  - tenant_id
  - queue scope
  - policy scope
  - isolation boundary

    │
    │
    ▼

[Service Layer]

  QueueService
      manage queues

  JobService
      submit / inspect / manage jobs

  LeaseService
      lease jobs to workers

  ExecutionService
      acknowledge / fail / retry jobs

  WorkerService
      track worker heartbeat / status

  PolicyService
      apply retry / timeout / concurrency rules

    │
    │
    ▼

[Repository Layer]

  QueueRepository
  JobRepository
  LeaseRepository
  WorkerRepository

  Responsibilities:
  - translate domain actions into SQL
  - enforce tenant-scoped queries
  - persist job state
  - persist lease state
  - persist worker metadata

    │
    │
    ▼

[Storage Layer]

  Database
  - tenants
  - queues
  - jobs
  - job_attempts
  - leases
  - workers

  Rules
  - tenant-scoped data isolation
  - deterministic job state transitions
  - lease expiration handling
  - retry metadata persistence

    │
    │
    ├──────────────────────────────┐
    │                              │
    ▼                              ▼

[Workers]                      [Observability / Reports]
  - poll queue                   - queue depth
  - lease job                    - running jobs
  - execute task                 - failed jobs
  - ack / fail                   - retry counts
  - heartbeat                    - worker status


────────────────────────────────────────────────────────────────────

Core Execution Flow
-------------------

Client submits job
    ↓
Job stored in queue
    ↓
Worker leases job
    ↓
Job enters running state
    ↓
Worker returns:
    - success  → ack
    - failure  → retry / dead-letter
    - timeout  → lease expires / recover


────────────────────────────────────────────────────────────────────

Isolation Model
---------------

Every operation MUST include tenant context.

All queries MUST include:

    WHERE tenant_id = ?

Cross-tenant reads and writes are forbidden.


────────────────────────────────────────────────────────────────────

Design Principles
-----------------

1. Multi-tenant isolation by design
2. Explicit job lifecycle transitions
3. Lease-based execution control
4. Deterministic retry handling
5. Worker-visible, operator-readable state
6. API-first evolution path