from internal.context.tenant_context import TenantContext
from internal.infra.time.provider import SystemTimeProvider
from internal.repository.sqlite.db import SQLiteDatabase
from internal.repository.sqlite.job_repo import SQLiteJobRepository
from internal.repository.sqlite.lease_repo import SQLiteLeaseRepository
from internal.repository.sqlite.worker_repo import SQLiteWorkerRepository
from internal.service.execution_service import ExecutionService

class AckJobUseCase:
    def __init__(self, db: SQLiteDatabase):
        self._db = db

    def execute(self, tenant_id: str, queue_id: str, job_id: str, lease_token: str, worker_id: str):
        ctx = TenantContext(tenant_id=tenant_id, queue_id=queue_id)
        
        with self._db.transaction() as conn:
            service = ExecutionService(
                job_repo=SQLiteJobRepository(conn),
                lease_repo=SQLiteLeaseRepository(conn),
                worker_repo=SQLiteWorkerRepository(conn),
                time_provider=SystemTimeProvider(),
                conn=conn
            )
            service.ack_success(ctx, job_id, lease_token, worker_id)
