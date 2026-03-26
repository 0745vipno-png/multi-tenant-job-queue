from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from internal.domain.job.states import JobState


@dataclass(slots=True)
class Job:
    job_id: str
    tenant_id: str
    queue_id: str
    state: JobState
    payload_json: str
    priority: int
    available_at: datetime
    attempt_count: int
    max_attempts: int
    current_lease_id: str | None
    current_worker_id: str | None
    created_at: datetime
    updated_at: datetime