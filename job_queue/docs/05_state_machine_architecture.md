Multi-Tenant Job Queue / Task Runner — State Machine Architecture
Multi-Tenant Job Queue / Task Runner
State Machine Architecture (v0.1)

Goal
-----
Define explicit lifecycle states and valid transitions for
jobs, leases, and workers.

State machines prevent invalid execution flow, reduce ambiguity,
and provide deterministic recovery behavior.
1. Job State Machine

這是整個系統最核心的狀態機。

Job Lifecycle


                submit_job
                    │
                    ▼

              ┌──────────────┐
              │    queued    │
              └──────┬───────┘
                     │
                     │ lease_job
                     ▼

              ┌──────────────┐
              │    leased    │
              └──────┬───────┘
                     │
                     │ start_execution
                     ▼

              ┌──────────────┐
              │   running    │
              └───┬────┬─────┘
                  │    │
                  │    │ fail_job
                  │    ▼
                  │  ┌──────────────┐
ack_success       │  │  retry_wait  │
                  │  └──────┬───────┘
                  │         │
                  │         │ retry_release
                  │         ▼
                  │  ┌──────────────┐
                  │  │    queued    │
                  │  └──────────────┘
                  │
                  ▼
           ┌──────────────┐
           │  succeeded   │
           └──────────────┘
Lease: A lease token is single-use and bound to exactly one lease lifecycle.

Additional terminal / failure paths:

running     → failed
retry_wait  → dead_letter
queued      → cancelled
leased → cancelled  cancel_job_before_execution_start (policy dependent)
retry_wait  → cancelled
Job States
State	Meaning
queued	waiting to be leased
leased	reserved by a worker, execution not yet confirmed
running	worker has started execution
retry_wait	failed or timed out, waiting for retry release
succeeded	completed successfully
failed	terminal non-retry failure
dead_letter	retry policy exhausted or unrecoverable
cancelled	cancelled before completion
Valid Job Transitions
none        → queued        submit_job
queued      → leased        lease_job
leased      → running       start_execution
running     → succeeded     ack_success
running     → retry_wait    fail_with_retry
running     → failed        fail_without_retry
retry_wait  → queued        retry_release
retry_wait → dead_letter   retry_limit_exhausted_or_unrecoverable
queued      → cancelled     cancel_job
leased      → cancelled     cancel_job (policy dependent)
retry_wait  → cancelled     cancel_job
leased      → queued        lease_expired_before_start
running     → retry_wait    execution_timeout
running     → failed        execution_timeout_non_retryable
Invalid Job Transitions

這些都應該被 service layer 拒絕：

succeeded   → running
succeeded   → queued
failed      → running
dead_letter → running
cancelled   → running

queued      → succeeded
leased      → succeeded
retry_wait  → running
running     → leased
2. Lease State Machine

Lease 是暫時執行權，不是 job 本身。

Lease Lifecycle


              create_lease
                  │
                  ▼

             ┌────────────┐
             │   active   │
             └────┬───────┘
                  │
      ┌───────────┼─────────────┐
      │           │             │
      ▼           ▼             ▼

 ┌──────────┐ ┌──────────┐ ┌──────────┐
 │ released │ │ expired  │ │ revoked  │
 └──────────┘ └──────────┘ └──────────┘
Lease States
State	Meaning
active	worker currently owns execution claim
released	closed normally after success/failure path
expired	lease timed out
revoked	explicitly invalidated by system/operator
Valid Lease Transitions
none    → active    create_lease
active → released  normal_close_after_ack_or_failure
active  → expired   lease_timeout
active  → revoked   operator_revoke / system_revoke
Invalid Lease Transitions
released → active
expired  → active
revoked  → active
released → expired
expired  → released

lease 一旦離開 active，就不應該再被重用。

3. Worker State Model

Worker 的狀態不像 job 那麼複雜，但還是需要明確。

Worker Lifecycle


            register_worker
                 │
                 ▼

            ┌────────────┐
            │   idle     │
            └────┬───────┘
                 │
                 │ lease_job / start work
                 ▼

            ┌────────────┐
            │  busy      │
            └────┬───────┘
                 │
        ┌────────┼────────┐
        │        │        │
        ▼        ▼        ▼

      idle   unhealthy   offline

也可以更完整看成：

idle
  ├─ takes lease → busy
  ├─ heartbeat lost → unhealthy
  └─ unregister / disappear → offline

busy
  ├─ completes work → idle
  ├─ heartbeat lost → unhealthy
  └─ shutdown / disappear → offline

unhealthy
  ├─ heartbeat restored → idle or busy
  └─ prolonged loss → offline
Worker States
State	Meaning
idle	registered and available for work
busy	currently executing one or more jobs (policy dependent)
unhealthy	heartbeat missing or runtime degraded
offline	no longer considered active
Valid Worker Transitions
none       → idle        register_worker
idle       → busy        lease_job / start execution
busy       → idle        job_complete / no active work
idle       → unhealthy   heartbeat_missed
busy       → unhealthy   heartbeat_missed
unhealthy  → idle        heartbeat_restored and no active lease
unhealthy  → busy        heartbeat_restored and active lease exists
idle       → offline     shutdown / unregister / TTL expired
busy       → offline     crash / disappearance / TTL expired
unhealthy  → offline     prolonged heartbeat loss
4. Attempt State Model

雖然 attempt 不一定要獨立成完整狀態機，但語義上最好定義清楚。

Attempt Lifecycle

create attempt
    │
    ▼
running_attempt
    ├─ success
    ├─ failed
    ├─ timeout
    └─ cancelled
Attempt 結果
Result	Meaning
success	execution succeeded
failed	execution failed with explicit failure
timeout	execution lost lease or exceeded allowed time
cancelled	execution aborted

這張表的重點是：

job 表示工作目前整體狀態

attempt 表示某一次執行結果

5. Combined System View

把三個狀態一起看，會變成這樣：

Tenant-scoped Queue
   │
   ▼

Job(queued)
   │ lease
   ▼
Job(leased) + Lease(active) + Worker(idle→busy)
   │ start execution
   ▼
Job(running) + Lease(active) + Worker(busy)
   │
   ├─ success
   │      → Job(succeeded) + Lease(released) + Worker(idle)
   │
   ├─ failure with retry
   │      → Job(retry_wait) + Lease(released) + Worker(idle)
   │
   ├─ failure without retry
   │      → Job(failed) + Lease(released) + Worker(idle)
   │
   └─ timeout / heartbeat loss
          → Lease(expired) + Job(retry_wait / queued / failed)
6. State Enforcement Layer

所有狀態機規則都應由 Service Layer 強制。

Service Layer

QueueService
JobService
LeaseService
ExecutionService
WorkerService
PolicyService

例如：

if job.state != "queued":
    raise InvalidJobStateError
if lease.state != "active":
    raise LeaseNotActiveError
if worker.state == "offline":
    raise WorkerUnavailableError

重點是：

Repository 不決定狀態是否合法，Service 決定。

7. System Invariants

這題最重要的是 invariant，要先講死。

Invariant 1
A job may have at most one active lease at a time.

Invariant 2
A lease may only be acknowledged by its owning worker + lease_token.

Invariant 3
A succeeded job cannot re-enter execution without explicit override.

Invariant 4
Retry is explicit and policy-driven, not implicit mutation.

Invariant 5
Worker health does not imply job success.

Invariant 6
All state transitions are tenant-scoped.
8. Why These State Machines Matter

這張圖真正要保護的是下面幾件事：

Job state machine

避免 job 在不合理狀態下被重複執行或錯誤完成。

Lease state machine

避免舊 lease、過期 lease、錯誤 worker 對 job 做操作。

Worker state model

讓系統能處理 heartbeat、故障、恢復，而不是假設 worker 永遠可靠。

Lease expiration before execution start and execution timeout after start
must be treated as distinct recovery events.