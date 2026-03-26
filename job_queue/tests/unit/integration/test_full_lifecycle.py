from __future__ import annotations
import pytest
from datetime import datetime, timezone

from internal.context.tenant_context import TenantContext
from internal.domain.job.states import JobState
from internal.infra.id.generator import UUIDGenerator
from internal.infra.time.provider import SystemTimeProvider
from internal.repository.sqlite.db import SQLiteDatabase
from internal.repository.sqlite.job_repo import SQLiteJobRepository
from internal.repository.sqlite.lease_repo import SQLiteLeaseRepository
from internal.repository.sqlite.worker_repo import SQLiteWorkerRepository

# 匯入你的 Application Use Cases
from internal.application.submit_job import SubmitJobUseCase
from internal.application.lease_job import LeaseJobUseCase
from internal.application.ack_job import AckJobUseCase

def test_job_lifecycle():
    # 1. 初始化資料庫（內存模式，跑完就丟，不留垃圾）
    db = SQLiteDatabase(":memory:")
    db.initialize_schema() 
    
    tenant_id = "tenant-1"
    queue_id = "default"
    worker_id = "worker-A"
    ctx = TenantContext(tenant_id=tenant_id, queue_id=queue_id)

    # 🔧 準備基礎設施工具
    time_provider = SystemTimeProvider()
    id_generator = UUIDGenerator()

    # ---------------------------------------------------------
    # 2. 測試：提交任務 (Submit Job)
    # ---------------------------------------------------------
    # 我們需要先手動建立一個 JobRepo 給它
    job_repo = SQLiteJobRepository(db._conn)
    
    submitter = SubmitJobUseCase(
        job_repo=job_repo,
        time_provider=time_provider,
        id_generator=id_generator
    )
    
    job_id = submitter.execute(
        ctx=ctx, 
        payload_json='{"task": "send_email", "to": "user@example.com"}',
        priority=10
    )
    
    assert job_id is not None
    print(f"\n✅ [Step 1] Job {job_id} submitted successfully!")

    # ---------------------------------------------------------
    # 3. 測試：領取任務 (Lease Job)
    # ---------------------------------------------------------
    # 我們需要確保 Worker 在資料庫裡是存在的且為 IDLE
    worker_repo = SQLiteWorkerRepository(db._conn)
    # 這裡我們先手動模擬一個 Worker 註冊進去（或是在 migration 裡預設有資料）
    db._conn.execute(
        "INSERT INTO workers (worker_id, tenant_id, state, updated_at) VALUES (?, ?, 'idle', ?)",
        (worker_id, tenant_id, time_provider.now().isoformat())
    )

    leaser = LeaseJobUseCase(db, lease_timeout_seconds=30)
    lease_result = leaser.execute(tenant_id, queue_id, worker_id)
    
    assert lease_result.job_id == job_id
    assert lease_result.lease_token is not None
    print(f"✅ [Step 2] Job {job_id} leased by {worker_id}! Token: {lease_result.lease_token[:8]}...")

    # ---------------------------------------------------------
    # 4. 測試：完成任務 (Ack Success)
    # ---------------------------------------------------------
    acker = AckJobUseCase(db)
    acker.execute(
        tenant_id=tenant_id,
        queue_id=queue_id,
        job_id=job_id,
        lease_token=lease_result.lease_token,
        worker_id=worker_id
    )
    
    # 驗證資料庫裡的 Job 狀態是否真的變成 succeeded
    final_job = job_repo._row_to_job(
        db._conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    )
    assert final_job.state == JobState.SUCCEEDED
    print(f"✅ [Step 3] Job {job_id} status is now: {final_job.state}")
    print("\n🎉 ALL SYSTEMS GO! Your SaaS Job Queue is working perfectly!")
