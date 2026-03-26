from __future__ import annotations

import sqlite3
from internal.context.tenant_context import TenantContext
from internal.infra.time.provider import TimeProvider
from internal.repository.interfaces.job_repository import JobRepository
from internal.repository.interfaces.lease_repository import LeaseRepository

class RecoveryService:
    def __init__(
        self,
        job_repo: JobRepository,
        lease_repo: LeaseRepository,
        time_provider: TimeProvider,
        conn: sqlite3.Connection
    ) -> None:
        # 醫生需要醫藥箱 (JobRepo) 和 巡邏名單 (LeaseRepo)
        self._job_repo = job_repo
        self._lease_repo = lease_repo
        self._time_provider = time_provider
        self._conn = conn

    def recover_expired_leases(self, tenant: TenantContext) -> int:
        """
        核心救援邏輯：掃描並恢復所有過期的租約。
        """
        now = self._time_provider.now()
        
        # 1. 找出所有「過期但還沒結案」的租約 (LeaseState = 'active' 且時間超過 now)
        expired_leases = self._lease_repo.find_expired_leases(tenant, now)
        
        recovered_count = 0
        for lease in expired_leases:
            try:
                # 使用資料庫事務，確保「沒收租約」與「重啟任務」是一體的
                with self._conn:
                    # 🔧 A. 沒收租約：狀態由 ACTIVE 變為 EXPIRED
                    # 使用事件 'lease_timeout' 觸發 Lease 狀態機
                    self._lease_repo.release_lease(tenant, lease.lease_id, "lease_timeout")
                    
                    # 🔧 B. 重啟任務：將 Job 狀態改回 QUEUED (待領取)
                    # 使用事件 'lease_expired_before_start' 讓 Job 重新排隊
                    self._job_repo.update_job_state(tenant, lease.job_id, "lease_expired_before_start")
                    
                    recovered_count += 1
                    print(f"🚑 [Recovery] Job {lease.job_id} recovered from expired lease {lease.lease_id}")
            
            except Exception as e:
                # 如果這筆救失敗了，記錄下來，繼續救下一筆
                print(f"❌ [Recovery] Failed to recover lease {lease.lease_id}: {str(e)}")
                
        return recovered_count
