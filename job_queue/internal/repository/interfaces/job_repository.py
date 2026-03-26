from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from internal.context.tenant_context import TenantContext
from internal.domain.job.model import Job

class JobRepository(ABC):
    @abstractmethod
    def save_job(self, tenant: TenantContext, job: Job) -> None:
        """將新 Job 存入資料庫"""
        raise NotImplementedError

    @abstractmethod
    def find_lease_candidates(self, tenant: TenantContext, now: datetime, limit: int) -> list[Job]:
        raise NotImplementedError

    @abstractmethod
    def mark_job_as_leased(self, tenant: TenantContext, job_id: str, lease_id: str, worker_id: str, leased_at: datetime) -> bool:
        raise NotImplementedError

    @abstractmethod
    def update_job_state(self, tenant: TenantContext, job_id: str, event: str) -> None:
        """根據事件更新 Job 狀態（例如 ack_success）"""
        raise NotImplementedError
