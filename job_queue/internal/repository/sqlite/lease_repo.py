from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from internal.context.tenant_context import TenantContext
from internal.domain.lease.model import Lease
from internal.domain.lease.states import LeaseState
from internal.domain.lease.transitions import require_lease_transition
from internal.repository.interfaces.lease_repository import LeaseRepository

class SQLiteLeaseRepository(LeaseRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def create_lease(self, lease: Lease) -> None:
        """建立新的租約"""
        self._conn.execute(
            """
            INSERT INTO leases (
                lease_id, lease_token, tenant_id, queue_id, job_id, 
                worker_id, state, leased_at, lease_until, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lease.lease_id, lease.lease_token, lease.tenant_id, lease.queue_id,
                lease.job_id, lease.worker_id, lease.state.value, 
                lease.leased_at.isoformat(), lease.lease_until.isoformat(),
                lease.created_at.isoformat(), lease.updated_at.isoformat()
            ),
        )

    def get_active_lease_by_token(self, tenant: TenantContext, token: str) -> Lease | None:
        """根據 Token 找尋活躍租約（結案驗證用）"""
        row = self._conn.execute(
            "SELECT * FROM leases WHERE tenant_id = ? AND lease_token = ?",
            (tenant.tenant_id, token)
        ).fetchone()
        
        return self._row_to_lease(row) if row else None

    def find_expired_leases(self, tenant: TenantContext, now: datetime) -> list[Lease]:
        """找尋所有已過期但狀態仍為 active 的租約（救援機制用）"""
        rows = self._conn.execute(
            "SELECT * FROM leases WHERE tenant_id = ? AND state = 'active' AND lease_until < ?",
            (tenant.tenant_id, now.isoformat())
        ).fetchall()
        
        return [self._row_to_lease(row) for row in rows]

    def release_lease(self, tenant: TenantContext, lease_id: str, event: str) -> None:
        """根據事件更新租約狀態（結案或沒收）"""
        row = self._conn.execute("SELECT state FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not row:
            return
            
        current_state = LeaseState(row["state"])
        next_state = require_lease_transition(current_state, event)
        
        self._conn.execute(
            "UPDATE leases SET state = ?, updated_at = ? WHERE lease_id = ?",
            (next_state.value, datetime.now(timezone.utc).isoformat(), lease_id)
        )

    def _row_to_lease(self, row: sqlite3.Row) -> Lease:
        """將資料庫橫列轉換為 Lease 模型物件"""
        return Lease(
            lease_id=row["lease_id"],
            lease_token=row["lease_token"],
            tenant_id=row["tenant_id"],
            queue_id=row["queue_id"],
            job_id=row["job_id"],
            worker_id=row["worker_id"],
            state=LeaseState(row["state"]),
            leased_at=datetime.fromisoformat(row["leased_at"]),
            lease_until=datetime.fromisoformat(row["lease_until"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )
