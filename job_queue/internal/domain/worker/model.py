from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from internal.domain.worker.states import WorkerState


@dataclass(slots=True)
class Worker:
    worker_id: str
    tenant_id: str
    state: WorkerState
    last_heartbeat_at: datetime | None
    updated_at: datetime