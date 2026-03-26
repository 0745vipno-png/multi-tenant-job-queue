Multi-Tenant Job Queue / Task Runner — Job Lifecycle Architecture
Multi-Tenant Job Queue / Task Runner
Job Lifecycle Architecture (v0.1)

Goal
-----
Define explicit job states and valid transitions for
submission, leasing, execution, retry, timeout recovery,
and terminal completion.


────────────────────────────────────────────────────────────────────

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
                           │ worker starts execution
                           ▼

                    ┌──────────────┐
                    │   running    │
                    └───┬────┬─────┘
                        │    │
          ack_success   │    │ fail_job
                        │    │
                        ▼    ▼

              ┌──────────────┐   ┌──────────────┐
              │  succeeded   │   │    failed    │
              └──────────────┘   └──────┬───────┘
                                        │
                                        │ retry policy allows retry
                                        ▼

                                 ┌──────────────┐
                                 │  retry_wait  │
                                 └──────┬───────┘
                                        │
                                        │ retry available
                                        ▼

                                 ┌──────────────┐
                                 │    queued    │
                                 └──────────────┘


────────────────────────────────────────────────────────────────────

                    Timeout / Lease Recovery


    leased
      │
      │ lease expired before execution starts
      ▼
    retry_wait or queued


    running
      │
      │ worker timeout / heartbeat lost / lease expired
      ▼
    failed or retry_wait


────────────────────────────────────────────────────────────────────

                    Terminal States


    succeeded
    failed
    dead_letter
    cancelled


These states are terminal unless an explicit admin/operator
action requeues the job.


────────────────────────────────────────────────────────────────────

                    State Definitions


queued
    Job is waiting to be leased by an eligible worker.


leased
    Job has been reserved by a worker, but execution has not yet
    been confirmed as started.


running
    Worker has started processing the job.


succeeded
    Job completed successfully.


failed
    Job execution failed and will not be retried.


retry_wait
    Job failed or timed out, but retry policy allows another attempt
    after delay / backoff.


dead_letter
    Job exceeded retry policy or entered unrecoverable failure state.


cancelled
    Job was cancelled before successful completion.


────────────────────────────────────────────────────────────────────

                    Valid Transitions


submit_job
    none → queued


lease_job
    queued → leased


start_execution
    leased → running


ack_success
    running → succeeded


fail_without_retry
    running → failed


fail_with_retry
    running → retry_wait


retry_release
    retry_wait → queued


exceed_retry_limit
    retry_wait → dead_letter


cancel_job
    queued → cancelled
    leased → cancelled   (policy dependent)
    retry_wait → cancelled


lease_expired
    leased → queued or retry_wait


execution_timeout
    running → retry_wait or failed


────────────────────────────────────────────────────────────────────

                    Invalid Transitions


succeeded → queued
succeeded → running
failed → running
dead_letter → running
cancelled → running


running → leased
queued → succeeded
leased → succeeded


These transitions must be rejected by the service layer.


────────────────────────────────────────────────────────────────────

                    Attempt Model


A single job may have multiple attempts.


    Job J1
      ├─ Attempt 1 → failed
      ├─ Attempt 2 → timeout
      └─ Attempt 3 → succeeded


Job state reflects current lifecycle position.

Attempt history preserves execution history.


────────────────────────────────────────────────────────────────────

                    Retry Model


When a job fails:

    if attempts < max_attempts
        → retry_wait
    else
        → dead_letter


Optional retry controls:

    - fixed delay
    - exponential backoff
    - max retry limit
    - retryable / non-retryable error classification


────────────────────────────────────────────────────────────────────

                    Lease Semantics


A job may only be worked by one active lease at a time.


    queued
      │
      ▼
    leased(worker=A, lease_until=T)


If the lease expires before completion:

    recover job
    return to queued / retry_wait


Lease protects against duplicate concurrent execution,
but idempotency may still be required at execution layer.


────────────────────────────────────────────────────────────────────

                    Tenant Isolation


All job lifecycle transitions are tenant-scoped.


Example safe rule:

    tenant A may only lease jobs belonging to tenant A


All lifecycle operations MUST include:

    tenant_id
    queue_id
    job_id


Cross-tenant lifecycle mutation is forbidden.


────────────────────────────────────────────────────────────────────

                    Design Principles


1. Explicit lifecycle states
2. Deterministic transition rules
3. Lease-based execution ownership
4. Retry is a state, not a side effect
5. Attempt history remains observable
6. Terminal states are stable unless explicitly overridden