from __future__ import annotations
from datetime import datetime
from internal.context.tenant_context import TenantContext
from internal.domain.job.model import Job
from internal.domain.job.states import JobState
from internal.infra.id.generator import IdGenerator
from internal.infra.time.provider import TimeProvider
from internal.repository.interfaces.job_repository import JobRepository

class SubmitJobUseCase:
    def __init__(
        self, 
        job_repo: JobRepository, 
        time_provider: TimeProvider,
        id_generator: IdGenerator
    ):
        self._job_repo = job_repo
        self._time_provider = time_provider
        self._id_generator = id_generator

    def execute(
        self, 
        ctx: TenantContext, 
        payload_json: str, 
        priority: int = 10,
        max_attempts: int = 3
    ) -> str:
        now = self._time_provider.now()
        job_id = self._id_generator.new_id()
        
        job = Job(
            job_id=job_id,
            tenant_id=ctx.tenant_id,
            queue_id=ctx.queue_id,
            state=JobState.QUEUED,
            payload_json=payload_json,
            priority=priority,
            available_at=now,
            attempt_count=0,
            max_attempts=max_attempts,
            current_lease_id=None,
            current_worker_id=None,
            created_at=now,
            updated_at=now
        )
        
        # 這裡未來可以加入 idempotency_key 檢查
        self._job_repo.save_job(ctx, job) # 記得要在 JobRepository 補上 save_job 接口
        return job_id