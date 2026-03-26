from __future__ import annotations
from abc import ABC, abstractmethod
from internal.context.tenant_context import TenantContext
from internal.domain.worker.model import Worker

class WorkerRepository(ABC):
    @abstractmethod
    def get_worker(self, tenant_id: str, worker_id: str) -> Worker | None:
        pass

    @abstractmethod
    def set_worker_busy_if_available(self, tenant_id: str, worker_id: str) -> bool:
        pass

    @abstractmethod
    def update_heartbeat(self, ctx: TenantContext, worker_id: str, state: str) -> None:
        """更新 Worker 狀態與最後活動時間"""
        pass
