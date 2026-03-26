from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class TimeProvider(Protocol):
    def now(self) -> datetime:
        ...


class SystemTimeProvider:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)