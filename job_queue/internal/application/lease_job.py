from __future__ import annotations

from internal.context.tenant_context import TenantContext
from internal.infra.id.generator import UUIDGenerator
from internal.infra.time.provider import SystemTimeProvider
from internal.repository.sqlite.db import SQLiteDatabase
from internal.repository.sqlite.job_repo import SQLiteJobRepository
from internal.repository.sqlite.lease_repo import SQLiteLeaseRepository
from internal.repository.sqlite.worker_repo import SQLiteWorkerRepository
from internal.service.lease_service import LeaseService, LeaseJobResult


class LeaseJobUseCase:
    def __init__(self, db: SQLiteDatabase, lease_timeout_seconds: int = 30) -> None:
        self._db = db
        self._lease_timeout_seconds = lease_timeout_seconds

    def execute(self, tenant_id: str, queue_id: str, worker_id: str) -> LeaseJobResult:
        tenant = TenantContext(tenant_id=tenant_id, queue_id=queue_id)

        with self._db.transaction() as conn:
            job_repo = SQLiteJobRepository(conn)
            lease_repo = SQLiteLeaseRepository(conn)
            worker_repo = SQLiteWorkerRepository(conn)

            # 🛠️ 關鍵修正：這裡要補上 conn=conn
            service = LeaseService(
                job_repo=job_repo,
                lease_repo=lease_repo,
                worker_repo=worker_repo,
                time_provider=SystemTimeProvider(),
                id_generator=UUIDGenerator(),
                conn=conn,  # <-- 把 Transaction 的連線傳進去
                lease_timeout_seconds=self._lease_timeout_seconds,
            )
            return service.lease_job(tenant=tenant, worker_id=worker_id)
