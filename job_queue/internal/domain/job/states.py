from __future__ import annotations

from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


TERMINAL_JOB_STATES: set[JobState] = {
    JobState.SUCCEEDED,
    JobState.FAILED,
    JobState.DEAD_LETTER,
    JobState.CANCELLED,
}