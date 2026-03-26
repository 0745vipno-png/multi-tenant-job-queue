from __future__ import annotations

import sqlite3
from datetime import timedelta
from internal.context.tenant_context import TenantContext
from internal.domain.common.errors import DomainError
from internal.infra.time.provider import TimeProvider
from internal.repository.interfaces.job_repository import JobRepository
from internal.repository.interfaces.lease_repository import LeaseRepository
from internal.repository.interfaces.worker_repository import WorkerRepository

class ExecutionService:
    def __init__(
        self,
        job_repo: JobRepository,
        lease_repo: LeaseRepository,
        worker_repo: WorkerRepository,
        time_provider: TimeProvider,
        conn: sqlite3.Connection
    ) -> None:
        self._job_repo = job_repo
        self._lease_repo = lease_repo
        self._worker_repo = worker_repo
        self._time_provider = time_provider
        self._conn = conn

    def ack_success(
        self, 
        tenant: TenantContext, 
        job_id: str, 
        lease_token: str, 
        worker_id: str
    ) -> None:
        """處理任務成功完成的邏輯"""
        now = self._time_provider.now()

        # 1. 驗證租約合法性
        lease = self._lease_repo.get_active_lease_by_token(tenant, lease_token)
        if not lease or lease.job_id != job_id or lease.worker_id != worker_id:
            raise DomainError("invalid lease token or worker mismatch")

        if lease.lease_until < now:
            raise DomainError("lease expired, cannot ack success")

        # 2. 原子更新所有狀態
        try:
            with self._conn:
                # Job: RUNNING -> SUCCEEDED
                self._job_repo.update_job_state(tenant, job_id, "ack_success")

                # Lease: ACTIVE -> RELEASED
                self._lease_repo.release_lease(tenant, lease.lease_id, "normal_close_after_ack_or_failure")

                # Worker: BUSY -> IDLE
                self._worker_repo.update_heartbeat(tenant, worker_id, "idle")
        except Exception as e:
            raise DomainError(f"failed to acknowledge job: {str(e)}")

    def fail_with_retry(
        self, 
        tenant: TenantContext, 
        job_id: str, 
        lease_token: str, 
        worker_id: str,
        delay_seconds: int = 60
    ) -> None:
        """處理任務失敗並排程重試的邏輯"""
        now = self._time_provider.now()
        
        # 1. 驗證租約合法性
        lease = self._lease_repo.get_active_lease_by_token(tenant, lease_token)
        if not lease or lease.job_id != job_id or lease.worker_id != worker_id:
            raise DomainError("invalid lease token for failure reporting")

        # 2. 原子執行重試排程
        try:
            with self._conn:
                # Job: RUNNING -> RETRY_WAIT，並設定下次可用時間
                next_run = now + timedelta(seconds=delay_seconds)
                self._job_repo.update_job_state(
                    tenant, 
                    job_id, 
                    "fail_with_retry", 
                    next_available_at=next_run
                )

                # Lease: 釋放當前租約
                self._lease_repo.release_lease(tenant, lease.lease_id, "normal_close_after_ack_or_failure")

                # Worker: 釋放 Worker 回到閒置狀態
                self._worker_repo.update_heartbeat(tenant, worker_id, "idle")
        except Exception as e:
            raise DomainError(f"failed to schedule retry: {str(e)}")
