Multi-Tenant Job Queue / Task Runner — Lease Architecture
Multi-Tenant Job Queue / Task Runner
Lease Architecture (v0.1)

Goal
-----
Define how workers temporarily acquire execution ownership of jobs,
how lease expiration is handled, and how duplicate execution risk is reduced.


────────────────────────────────────────────────────────────────────

                        Lease Concept


A lease is a time-bounded execution claim on a job.

It means:

    "worker X currently has the right to execute job Y
     until lease expiration time T"


A lease is NOT:

    - proof of successful execution
    - permanent ownership
    - completion acknowledgement


────────────────────────────────────────────────────────────────────

                        Lease Flow


    queued job
       │
       │ worker requests next eligible job
       ▼

    lease_job()
       │
       │ atomically select job
       │ create lease
       ▼

    leased job
       │
       │ worker starts execution
       ▼

    running job
       │
       ├─ ack_success        → release lease / mark succeeded
       ├─ fail_job           → release lease / retry decision
       ├─ renew_lease        → extend lease_until
       └─ timeout / crash    → lease expires / recovery path


────────────────────────────────────────────────────────────────────

                    Core Lease Record


Lease metadata should include:

    lease_id
    tenant_id
    queue_id
    job_id
    worker_id
    lease_token
    leased_at
    lease_until
    status


Example:

    lease_id      = L001
    tenant_id     = T_ACME
    queue_id      = Q_EMAIL
    job_id        = J123
    worker_id     = W7
    lease_token   = abc-xyz-123
    leased_at     = 2026-03-16T12:00:00
    lease_until   = 2026-03-16T12:00:30
    status        = active


────────────────────────────────────────────────────────────────────

                    Lease State Model


                    create lease
                        │
                        ▼

                  ┌────────────┐
                  │   active   │
                  └─────┬──────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         │              │              │
         ▼              ▼              ▼

   released         expired         revoked
  (normal end)   (time elapsed)   (operator/system)


Terminal meanings:

    released
        worker completed or failed job and lease closed normally

    expired
        worker lost lease due to timeout / missing renewal

    revoked
        lease cancelled explicitly by system or operator


────────────────────────────────────────────────────────────────────

                    Lease Acquisition Rules


A job may only have ONE active lease at a time.


Safe acquisition rule:

    select one queued job
    create active lease
    move job → leased

These operations must be atomic.


Required conditions for leasing:

    - job belongs to requesting tenant
    - job state == queued
    - job is eligible for execution
    - no existing active lease
    - queue policy allows worker to take job


────────────────────────────────────────────────────────────────────

                    Worker Execution Ownership


Once a worker receives a lease:

    worker_id + lease_token

must be presented for any execution-sensitive action:

    - start_execution
    - renew_lease
    - ack_success
    - fail_job


This prevents another worker from accidentally completing or
modifying a job it does not own.


────────────────────────────────────────────────────────────────────

                    Lease Renewal


Long-running jobs may require lease extension.


    active lease
       │
       │ renew_lease(worker_id, lease_token)
       ▼
    active lease with new lease_until


Renewal conditions:

    - lease must still be active
    - worker_id must match
    - lease_token must match
    - job must still be in leased / running state


If renewal fails:

    worker should assume lease ownership is lost


────────────────────────────────────────────────────────────────────

                    Lease Expiration


A lease expires when:

    current_time > lease_until


Typical causes:

    - worker crashed
    - worker hung
    - network interruption
    - worker forgot to renew
    - task exceeded allowed visibility window


After expiration:

    lease status → expired

Job recovery policy may be:

    leased   → queued
    running  → retry_wait
    running  → failed

depending on system policy.


────────────────────────────────────────────────────────────────────

                    Recovery / Reclaim Flow


    worker A leases job J1
       │
       │ no ack / no renew
       ▼
    lease expires
       │
       │ recovery process scans expired leases
       ▼
    job becomes reclaimable
       │
       ├─ return to queued
       ├─ move to retry_wait
       └─ mark failed


Then:

    worker B may lease job J1 in a later attempt


────────────────────────────────────────────────────────────────────

                    Duplicate Execution Risk


Lease reduces concurrent execution risk,
but may not fully eliminate duplicate execution.


Example:

    worker A completes job
    but network fails before ack

system may think lease expired
and later requeue the job


Therefore:

    job handlers should preferably be idempotent


Lease provides ownership coordination,
not absolute once-only execution guarantee.


────────────────────────────────────────────────────────────────────

                    Lease Token Semantics


Each lease should generate a unique lease_token.

Purpose:

    - binds actions to a specific lease instance
    - prevents stale worker acknowledgements
    - protects against reuse of old lease state


Example:

    worker leases J1 with token T1
    lease expires
    worker B leases J1 with token T2

Now:

    any ack using T1 must be rejected


────────────────────────────────────────────────────────────────────

                    Tenant Isolation


All lease operations are tenant-scoped.

Required operation scope:

    tenant_id
    queue_id
    job_id
    worker_id
    lease_token


Safe query principle:

    WHERE tenant_id = ?
      AND queue_id = ?
      AND job_id = ?


Cross-tenant leasing is forbidden.


────────────────────────────────────────────────────────────────────

                    Lease Observability


System should expose lease visibility for operators:

    - active leases
    - expired leases
    - leases per worker
    - average lease duration
    - renewal failures
    - reclaim count


This makes stuck-job debugging possible.


────────────────────────────────────────────────────────────────────

                    Design Principles


1. Lease grants temporary execution ownership
2. Active lease must be unique per job
3. Lease acquisition must be atomic
4. Lease expiration must be recoverable
5. Renewal must be explicit
6. Old lease tokens must become invalid
7. Idempotency is still valuable above lease layer