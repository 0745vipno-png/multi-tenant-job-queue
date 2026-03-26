from __future__ import annotations

import sqlite3
from datetime import datetime, UTC
from internal.context.tenant_context import TenantContext
from internal.domain.job.model import Job
from internal.domain.job.states import JobState
from internal.domain.job.transitions import require_job_transition
from internal.repository.interfaces.job_repository import JobRepository

class SQLiteJobRepository(JobRepository):
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def save_job(self, tenant: TenantContext, job: Job) -> None:
        """將新任務持久化到資料庫"""
        self._conn.execute(
            """
            INSERT INTO jobs (
                job_id, tenant_id, queue_id, state, payload_json,
                priority, available_at, attempt_count, max_attempts,
                current_lease_id, current_worker_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id, tenant.tenant_id, tenant.queue_id, job.state.value, job.payload_json,
                job.priority, job.available_at.isoformat(), job.attempt_count, job.max_attempts,
                job.current_lease_id, job.current_worker_id, job.created_at.isoformat(), job.updated_at.isoformat()
            )
        )

    def find_lease_candidates(self, tenant: TenantContext, now: datetime, limit: int) -> list[Job]:
        """找出所有排隊中且可執行的任務"""
        rows = self._conn.execute(
            """
            SELECT * FROM jobs 
            WHERE tenant_id = ? AND queue_id = ? AND state = 'queued' AND available_at <= ? 
            ORDER BY priority DESC, created_at ASC LIMIT ?
            """,
            (tenant.tenant_id, tenant.queue_id, now.isoformat(), limit)
        ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def mark_job_as_leased(self, tenant: TenantContext, job_id: str, lease_id: str, worker_id: str, leased_at: datetime) -> bool:
        """樂觀鎖搶奪任務：只有 state='queued' 才能成功"""
        cur = self._conn.execute(
            """
            UPDATE jobs 
            SET state = 'leased', current_lease_id = ?, current_worker_id = ?, updated_at = ? 
            WHERE job_id = ? AND state = 'queued'
            """,
            (lease_id, worker_id, leased_at.isoformat(), job_id)
        )
        return cur.rowcount == 1

    def update_job_state(
        self, 
        tenant: TenantContext, 
        job_id: str, 
        event: str, 
        next_available_at: datetime | None = None
    ) -> None:
        """根據狀態機事件更新 Job 狀態，並清理租約關聯"""
        row = self._conn.execute("SELECT state, attempt_count FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return
        
        current_state = JobState(row["state"])
        next_state = require_job_transition(current_state, event)
        
        # 如果是重試事件，次數加 1
        attempt_increment = 1 if event == "fail_with_retry" else 0
        now_str = datetime.now(UTC).isoformat()
        
        # 當任務結案或進入重試等待時，清空當前租約 ID
        sql = """
            UPDATE jobs 
            SET state = ?, 
                attempt_count = attempt_count + ?, 
                available_at = COALESCE(?, available_at),
                current_lease_id = CASE WHEN ? IN ('succeeded', 'failed', 'retry_wait', 'queued') THEN NULL ELSE current_lease_id END,
                current_worker_id = CASE WHEN ? IN ('succeeded', 'failed', 'retry_wait', 'queued') THEN NULL ELSE current_worker_id END,
                updated_at = ? 
            WHERE job_id = ?
        """
        self._conn.execute(sql, (
            next_state.value, 
            attempt_increment, 
            next_available_at.isoformat() if next_available_at else None,
            next_state.value,
            next_state.value,
            now_str,
            job_id
        ))

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """資料庫 Row 轉 Domain Model"""
        return Job(
            job_id=row["job_id"], tenant_id=row["tenant_id"], queue_id=row["queue_id"],
            state=JobState(row["state"]), payload_json=row["payload_json"], priority=row["priority"],
            available_at=datetime.fromisoformat(row["available_at"]), attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"], current_lease_id=row["current_lease_id"],
            current_worker_id=row["current_worker_id"], created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )
