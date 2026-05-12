#免責聲明:此代碼為MVP版本 僅供參考

#為什麼要寫 time_provider 而不直接用 datetime.now()？
#為了確保測試的確定性。透過 Mock TimeProvider，我可以模擬任務超時（Lease Timeout）的邊界情況，而不需要真的在測試中 sleep 30 秒。

#為什麼要用 SQLite 跑測試？
#這符合我追求的 Zero-config 交付。我確保開發者不需要安裝 Redis 或 RabbitMQ，只要有 Python 環境，就能 100% 驗證整個系統的生命週期。

#「既然是多租戶（Multi-tenant），如果 Tenant A 塞爆了 Queue，會影響 Tenant B 嗎？」
#在目前的 JobRepo 層級，我透過 tenant_id 物理隔離了查詢。未來如果要防止資源擠兌（Noisy Neighbor），我可以在 LeaseService裡加入 Tenant Quota（租戶配額） 的策略控制。」

#「SQLite 在高併發（Concurrency）下會有 Locking 問題，這怎麼解決？」

#「SQLite 的確不適合極高頻寫入，但在我的設計中，資料庫層級被封裝在 Repository 之後。如果未來規模擴大，我只需要抽換PostgreSQLRepository 即可，核心業務邏輯不需要改動。

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
