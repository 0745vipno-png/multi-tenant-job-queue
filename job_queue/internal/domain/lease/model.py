from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from internal.domain.lease.states import LeaseState


@dataclass(slots=True)
class Lease:
    lease_id: str
    lease_token: str
    tenant_id: str
    queue_id: str
    job_id: str
    worker_id: str
    state: LeaseState
    leased_at: datetime
    lease_until: datetime
    created_at: datetime
    updated_at: datetime