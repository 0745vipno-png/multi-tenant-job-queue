from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from internal.context.tenant_context import TenantContext
from internal.domain.common.errors import (
    JobNotLeaseableError,
    LeaseConflictError,
    WorkerUnavailableError,
)
from internal.domain.job.transitions import require_job_transition
from internal.domain.lease.model import Lease
from internal.domain.lease.states import LeaseState
from internal.domain.lease.transitions import require_lease_transition
from internal.domain.worker.states import WorkerState
from internal.infra.id.generator import IdGenerator
from internal.infra.time.provider import TimeProvider
from internal.repository.interfaces.job_repository import JobRepository
from internal.repository.interfaces.lease_repository import LeaseRepository
from internal.repository.interfaces.worker_repository import WorkerRepository


@dataclass(frozen=True, slots=True)
class LeaseJobResult:
    job_id: str
    lease_id: str
    lease_token: str
    lease_until: str
    worker_id: str


class LeaseService:
    def __init__(
        self,
        job_repo: JobRepository,
        lease_repo: LeaseRepository,
        worker_repo: WorkerRepository,
        time_provider: TimeProvider,
        id_generator: IdGenerator,
        conn: sqlite3.Connection,  # 注入連線以控制事務
        lease_timeout_seconds: int = 60,
        candidate_batch_size: int = 5,
    ) -> None:
        self._job_repo = job_repo
        self._lease_repo = lease_repo
        self._worker_repo = worker_repo
        self._time_provider = time_provider
        self._id_generator = id_generator
        self._conn = conn
        self._lease_timeout_seconds = lease_timeout_seconds
        self._candidate_batch_size = candidate_batch_size

    def lease_job(
        self,
        tenant: TenantContext,
        worker_id: str,
    ) -> LeaseJobResult:
        now = self._time_provider.now()

        # 1. 檢查 Worker 是否可用
        worker = self._worker_repo.get_worker(tenant.tenant_id, worker_id)
        if worker is None:
            raise WorkerUnavailableError(f"worker not found: {worker_id}")
        
        if worker.state in {WorkerState.UNHEALTHY, WorkerState.OFFLINE}:
            raise WorkerUnavailableError(
                f"worker unavailable: worker_id={worker_id}, state={worker.state}"
            )

        # 2. 找出潛在可執行的 Job
        candidates = self._job_repo.find_lease_candidates(
            tenant=tenant,
            now=now,
            limit=self._candidate_batch_size,
        )
        if not candidates:
            raise JobNotLeaseableError(f"no jobs available for queue={tenant.queue_id}")

        # 3. 嘗試搶奪 Job (Optimistic Concurrency)
        for job in candidates:
            # 驗證狀態機規則
            require_job_transition(job.state, "lease_job")
            
            lease_id = self._id_generator.new_id()
            lease_token = self._id_generator.new_token()
            lease_until = now + timedelta(seconds=self._lease_timeout_seconds)

            lease = Lease(
                lease_id=lease_id,
                lease_token=lease_token,
                tenant_id=tenant.tenant_id,
                queue_id=tenant.queue_id,
                job_id=job.job_id,
                worker_id=worker_id,
                state=LeaseState.ACTIVE,
                leased_at=now,
                lease_until=lease_until,
                created_at=now,
                updated_at=now,
            )

            try:
                # 使用資料庫 Transaction 確保原子性
                with self._conn:  # SQLite context manager 會自動處理 COMMIT/ROLLBACK
                    # 建立租約
                    self._lease_repo.create_lease(lease)
                    
                    # 標記 Job 為已租用 (這裡會檢查 state='queued'，搶輸會回傳 False)
                    updated = self._job_repo.mark_job_as_leased(
                        tenant=tenant,
                        job_id=job.job_id,
                        lease_id=lease_id,
                        worker_id=worker_id,
                        leased_at=now,
                    )
                    
                    if not updated:
                        # 搶輸了，觸發 ROLLBACK 並試下一個 Job
                        raise sqlite3.IntegrityError("Job already taken")

                # 如果走到這裡，代表 Transaction 成功
                self._worker_repo.set_worker_busy_if_available(
                    tenant_id=tenant.tenant_id,
                    worker_id=worker_id,
                )

                return LeaseJobResult(
                    job_id=job.job_id,
                    lease_id=lease_id,
                    lease_token=lease_token,
                    lease_until=lease_until.isoformat(),
                    worker_id=worker_id,
                )

            except (sqlite3.IntegrityError, LeaseConflictError):
                # 併發衝突，繼續嘗試下一個候選工作
                continue

        raise JobNotLeaseableError("all candidates were taken by other workers")
