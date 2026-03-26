from __future__ import annotations

import sqlite3
from internal.context.tenant_context import TenantContext
from internal.domain.common.errors import DomainError
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
        self._job_repo = job_repo
        self._lease_repo = lease_repo
        self._time_provider = time_provider
        self._conn = conn

    def recover_expired_leases(self, tenant: TenantContext) -> int:
        """
        掃描並恢復所有過期的租約。
        回傳成功恢復的任務數量。
        """
        now = self._time_provider.now()
        
        # 1. 找出所有「佔著茅坑不拉屎」的租約
        expired_leases = self._lease_repo.find_expired_leases(tenant, now)
        
        recovered_count = 0
        for lease in expired_leases:
            try:
                # 每個租約的救援都包在獨立的 Transaction 裡，避免一個壞掉卡死全部
                with self._conn:
                    # 🔧 步驟 A: 沒收租約 (狀態跳至 EXPIRED)
                    # 使用 'lease_timeout' 事件觸發 Lease 狀態機
                    self._lease_repo.release_lease(tenant, lease.lease_id, "lease_timeout")
                    
                    # 🔧 步驟 B: 重啟任務 (狀態跳至 QUEUED)
                    # 使用 'lease_expired_before_start' 事件讓 Job 重新回到隊列
                    self._job_repo.update_job_state(tenant, lease.job_id, "lease_expired_before_start")
                    
                    recovered_count += 1
                    print(f"🚑 [Recovery] Job {lease.job_id} recovered from expired lease {lease.lease_id}")
            
            except Exception as e:
                # 救援失敗不要崩潰，記錄下來繼續救下一個
                print(f"❌ [Recovery] Failed to recover lease {lease.lease_id}: {str(e)}")
                
        return recovered_count
