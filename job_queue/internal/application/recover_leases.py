from __future__ import annotations

from internal.context.tenant_context import TenantContext
from internal.infra.time.provider import SystemTimeProvider
from internal.repository.sqlite.db import SQLiteDatabase
from internal.repository.sqlite.job_repo import SQLiteJobRepository
from internal.repository.sqlite.lease_repo import SQLiteLeaseRepository
from internal.service.recovery_service import RecoveryService


class RecoverLeasesUseCase:
    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def execute(self, tenant_id: str, queue_id: str) -> int:
        """
        執行租約恢復任務。
        會掃描該租戶下所有過期的租約並將對應任務重新放回隊列。
        """
        ctx = TenantContext(tenant_id=tenant_id, queue_id=queue_id)
        
        # 開啟事務，確保救援過程中的資料庫操作具備原子性
        with self._db.transaction() as conn:
            service = RecoveryService(
                job_repo=SQLiteJobRepository(conn),
                lease_repo=SQLiteLeaseRepository(conn),
                time_provider=SystemTimeProvider(),
                conn=conn
            )
            
            # 啟動救援程序並回傳成功救援的總數
            recovered_count = service.recover_expired_leases(ctx)
            
            if recovered_count > 0:
                print(f"🚑 [Application] Recovery complete: {recovered_count} jobs returned to queue.")
            
            return recovered_count
