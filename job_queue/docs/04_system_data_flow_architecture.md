Multi-Tenant Job Queue / Task Runner — System Data Flow Architecture
Multi-Tenant Job Queue / Task Runner
System Data Flow Architecture (v0.1)

Goal
-----
Describe how data moves through the system during
job submission, leasing, execution, retry, timeout recovery,
and operator inspection.


────────────────────────────────────────────────────────────────────

                         System Flow


        User / Client / Worker
                 │
                 │ CLI / API request
                 ▼

        [Ingress Layer]
          - submit job
          - lease next job
          - ack success
          - fail job
          - renew lease
          - inspect queue / inspect job / inspect worker

                 │
                 │ resolve tenant scope
                 ▼

        [Tenant Context Layer]
          - tenant_id
          - queue_id
          - policy scope

                 │
                 │ dispatch action
                 ▼

        [Service Layer]
          - QueueService
          - JobService
          - LeaseService
          - ExecutionService
          - WorkerService
          - PolicyService

                 │
                 │ domain actions
                 ▼

        [Repository Layer]
          - QueueRepository
          - JobRepository
          - LeaseRepository
          - WorkerRepository

                 │
                 │ SQL / persistence
                 ▼

        [Storage Layer]
          - tenants
          - queues
          - jobs
          - job_attempts
          - leases
          - workers

                 │
                 ├──────────────────────────────┐
                 │                              │
                 ▼                              ▼

        [Worker Runtime]                [Observability / Inspection]
          - execute leased job            - queue depth
          - heartbeat                     - active leases
          - renew lease                   - retry count
          - ack / fail                    - worker status
1. Submit Job Flow

這是最基本的資料流。

Client / Operator
    │
    │ submit job
    ▼
Ingress Layer
    │
    ▼
Tenant Context
    │
    ▼
JobService.submit_job()
    │
    ├─ validate tenant / queue
    ├─ apply queue policy
    └─ construct job payload
    ▼
JobRepository.insert_job()
    │
    ▼
Storage.jobs
    │
    └─ state = queued
輸出結果
job created
job_id returned
state = queued
2. Lease Job Flow

這是整個系統最重要的 flow 之一。

Worker
    │
    │ request next job
    ▼
Ingress Layer
    │
    ▼
Tenant Context
    │
    ▼
LeaseService.lease_job()
    │
    ├─ validate tenant / queue
    ├─ select one eligible queued job
    ├─ create lease record
    ├─ attach worker_id + lease_token
    └─ move job state → leased
    ▼
JobRepository + LeaseRepository
    │
    ▼
Storage.jobs / Storage.leases
輸出結果
leased job returned to worker
job_id
lease_token
lease_until
payload
3. Start Execution Flow

拿到 lease 不代表真正開始執行，所以要分開。

Worker
    │
    │ start execution
    ▼
ExecutionService.start_execution()
    │
    ├─ validate lease_token
    ├─ validate worker ownership
    └─ move job state → running
    ▼
JobRepository.update_state()
    │
    ▼
Storage.jobs
狀態變化
leased → running
4. Ack Success Flow

job 成功完成後，worker 要明確回報。

Worker
    │
    │ ack success
    ▼
ExecutionService.ack_success()
    │
    ├─ validate tenant / job / worker
    ├─ validate active lease
    ├─ validate lease_token
    ├─ record attempt result
    ├─ mark lease → released
    └─ move job state → succeeded
    ▼
JobRepository / LeaseRepository / AttemptRepository
    │
    ▼
Storage.jobs
Storage.leases
Storage.job_attempts
輸出結果
job completed
state = succeeded
lease released
attempt recorded
5. Fail Job Flow

如果執行失敗，系統不能只標記失敗，還要經過 policy 判斷。

Worker
    │
    │ fail job
    ▼
ExecutionService.fail_job()
    │
    ├─ validate lease ownership
    ├─ validate lease_token
    ├─ record failure attempt
    ├─ ask PolicyService for retry decision
    │
    ├─ if retry allowed:
    │      move job → retry_wait
    │      release lease
    │
    └─ if retry exhausted:
           move job → dead_letter or failed
           release lease
    ▼
JobRepository / LeaseRepository / AttemptRepository
    │
    ▼
Storage.jobs
Storage.leases
Storage.job_attempts
狀態變化
running → retry_wait
or
running → failed
or
running → dead_letter
6. Retry Release Flow

在 retry delay 到期後，job 要重新排回 queue。

Recovery process / scheduler
    │
    │ scan retry_wait jobs
    ▼
PolicyService / RecoveryService
    │
    ├─ check retry_after
    └─ release job back to queue
    ▼
JobRepository.update_state()
    │
    ▼
Storage.jobs
狀態變化
retry_wait → queued
7. Lease Renewal Flow

長時間執行的 job 需要續租。

Worker
    │
    │ renew lease
    ▼
LeaseService.renew_lease()
    │
    ├─ validate worker_id
    ├─ validate lease_token
    ├─ validate lease still active
    └─ extend lease_until
    ▼
LeaseRepository.update_lease()
    │
    ▼
Storage.leases
輸出結果
lease extended
new lease_until returned
8. Lease Expiration Recovery Flow

這是 infra 系統最重要的恢復流程之一。

Recovery process
    │
    │ scan expired leases
    ▼
LeaseRepository.find_expired_leases()
    │
    ▼
RecoveryService.recover_expired_job()
    │
    ├─ mark lease → expired
    ├─ inspect current job state
    │
    ├─ if job == leased:
    │      move job → queued
    │
    ├─ if job == running:
    │      move job → retry_wait or failed
    │
    └─ record recovery reason
    ▼
JobRepository / LeaseRepository / AttemptRepository
    │
    ▼
Storage.jobs
Storage.leases
Storage.job_attempts
核心意義
stuck jobs become reclaimable
9. Queue Inspection Flow

operator 或 client 需要看 queue 狀態。

Operator / Client
    │
    │ inspect queue
    ▼
Ingress Layer
    │
    ▼
Tenant Context
    │
    ▼
QueueService.inspect_queue()
    │
    ├─ query queue depth
    ├─ query queued jobs
    ├─ query running jobs
    ├─ query retry_wait jobs
    └─ query dead-letter jobs
    ▼
Repository Layer
    │
    ▼
Storage.jobs / Storage.leases
輸出結果
queue metrics
job counts by state
active lease visibility
10. Worker Heartbeat Flow

worker 也需要被觀察，不然 system 無法判定 health。

Worker
    │
    │ heartbeat
    ▼
WorkerService.heartbeat()
    │
    ├─ validate tenant scope
    ├─ update worker last_seen_at
    ├─ update worker status
    └─ optionally attach runtime metrics
    ▼
WorkerRepository.update_heartbeat()
    │
    ▼
Storage.workers
用途
worker liveness tracking
lease troubleshooting
orphan execution diagnosis
System Data Flow Summary

整個系統的固定資料流是：

Client / Worker / Operator
    ↓
Ingress Layer
    ↓
Tenant Context
    ↓
Service Layer
    ↓
Repository Layer
    ↓
Storage Layer
    ↓
Worker / Recovery / Observability

這個 flow 原則上不應被繞過。

Flow Control Principles
1. every operation is tenant-scoped
2. every job mutation is state-aware
3. every execution action is lease-bound
4. retries are policy-driven
5. recovery paths are explicit
6. worker ownership must be validated