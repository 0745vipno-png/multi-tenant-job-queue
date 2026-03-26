from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

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
        lease_timeout_seconds: int = 60,
        candidate_batch_size: int = 5,
    ) -> None:
        self._job_repo = job_repo
        self._lease_repo = lease_repo
        self._worker_repo = worker_repo
        self._time_provider = time_provider
        self._id_generator = id_generator
        self._lease_timeout_seconds = lease_timeout_seconds
        self._candidate_batch_size = candidate_batch_size

    def lease_job(self, tenant: TenantContext, worker_id: str) -> LeaseJobResult:
        now = self._time_provider.now()

        # 檢查 Worker 是否健康
        worker = self._worker_repo.get_worker(tenant.tenant_id, worker_id)
        if not worker or worker.state in {WorkerState.UNHEALTHY, WorkerState.OFFLINE}:
            raise WorkerUnavailableError(f"worker {worker_id} unavailable")

        # 撈出潛在候選 Job
        candidates = self._job_repo.find_lease_candidates(
            tenant=tenant, now=now, limit=self._candidate_batch_size
        )
        if not candidates:
            raise JobNotLeaseableError("no candidates")

        # --- 以下就是 GPT 說的 Critical Change 邏輯 ---
        for job in candidates:
            require_job_transition(job.state, "lease_job")

            lease_id = self._id_generator.new_id()
            lease_token = self._id_generator.new_token()
            lease_until = now + timedelta(seconds=self._lease_timeout_seconds)

            # STEP 1: 先去資料庫搶 Job (樂觀鎖)
            # 只有當資料庫裡該 Job 還是 'queued' 時，這步才會成功
            updated = self._job_repo.mark_job_as_leased(
                tenant=tenant,
                job_id=job.job_id,
                lease_id=lease_id,
                worker_id=worker_id,
                leased_at=now,
            )

            if not updated:
                continue  # 搶輸了，換下一個 Job 試試

            # STEP 2: 搶贏了，補辦租約手續
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
                self._lease_repo.create_lease(lease)
            except Exception as exc:
                # 這裡如果失敗，代表 Job 鎖定了但租約沒建成功，會變成殭屍任務
                # 商業環境通常會在這裡加一個 Rollback 或自動修復邏輯
                raise LeaseConflictError("lease insert failed after job claim") from exc

            # 更新 Worker 狀態為忙碌
            self._worker_repo.set_worker_busy_if_available(
                tenant_id=tenant.tenant_id, worker_id=worker_id
            )

            return LeaseJobResult(
                job_id=job.job_id,
                lease_id=lease_id,
                lease_token=lease_token,
                lease_until=lease_until.isoformat(),
                worker_id=worker_id,
            )

        raise JobNotLeaseableError("all candidates lost race")
