from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from internal.context.tenant_context import TenantContext
from internal.domain.worker.model import Worker
from internal.domain.worker.states import WorkerState
from internal.repository.interfaces.worker_repository import WorkerRepository

class SQLiteWorkerRepository(WorkerRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def get_worker(self, tenant_id: str, worker_id: str) -> Worker | None:
        row = self._conn.execute(
            "SELECT * FROM workers WHERE tenant_id = ? AND worker_id = ?",
            (tenant_id, worker_id)
        ).fetchone()
        if not row: return None
        return Worker(
            worker_id=row["worker_id"],
            tenant_id=row["tenant_id"],
            state=WorkerState(row["state"]),
            last_heartbeat_at=datetime.fromisoformat(row["last_heartbeat_at"]) if row["last_heartbeat_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"])
        )

    def set_worker_busy_if_available(self, tenant_id: str, worker_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "UPDATE workers SET state = 'busy', updated_at = ? WHERE tenant_id = ? AND worker_id = ? AND state IN ('idle', 'busy')",
            (now, tenant_id, worker_id)
        )
        return cur.rowcount == 1

    def update_heartbeat(self, ctx: TenantContext, worker_id: str, state: str) -> None:
        """實作遺失的結案方法"""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE workers SET state = ?, last_heartbeat_at = ?, updated_at = ? WHERE tenant_id = ? AND worker_id = ?",
            (state, now, now, ctx.tenant_id, worker_id)
        )
