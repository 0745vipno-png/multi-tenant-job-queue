from __future__ import annotations

from enum import StrEnum


class WorkerState(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"