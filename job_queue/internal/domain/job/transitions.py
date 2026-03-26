from __future__ import annotations

from internal.domain.common.errors import InvalidStateTransitionError
from internal.domain.job.states import JobState


_ALLOWED_JOB_TRANSITIONS: dict[tuple[JobState | None, str], JobState] = {
    # 1. 提交任務
    (None, "submit_job"): JobState.QUEUED,
    
    # 2. 領取任務 (Lease)
    (JobState.QUEUED, "lease_job"): JobState.LEASED,
    
    # 3. 執行任務 (Start)
    (JobState.LEASED, "start_execution"): JobState.RUNNING,
    
    # 4. 結案 (Success) - 支援從 LEASED 或 RUNNING 跳轉
    (JobState.LEASED, "ack_success"): JobState.SUCCEEDED, 
    (JobState.RUNNING, "ack_success"): JobState.SUCCEEDED,
    
    # 5. 失敗處理 (Failure)
    (JobState.RUNNING, "fail_with_retry"): JobState.RETRY_WAIT,
    (JobState.RUNNING, "fail_without_retry"): JobState.FAILED,
    (JobState.LEASED, "fail_without_retry"): JobState.FAILED, # 領了直接報錯
    
    # 6. 重試邏輯 (Retry)
    (JobState.RETRY_WAIT, "retry_release"): JobState.QUEUED,
    (JobState.RETRY_WAIT, "exceed_retry_limit"): JobState.DEAD_LETTER,
    
    # 7. 取消邏輯 (Cancel)
    (JobState.QUEUED, "cancel_job"): JobState.CANCELLED,
    (JobState.LEASED, "cancel_job_before_execution_start"): JobState.CANCELLED,
    (JobState.RETRY_WAIT, "cancel_job"): JobState.CANCELLED,
    
    # 8. 異常恢復 (Recovery)
    (JobState.LEASED, "lease_expired_before_start"): JobState.QUEUED,
    (JobState.RUNNING, "execution_timeout"): JobState.RETRY_WAIT,
    (JobState.RUNNING, "execution_timeout_non_retryable"): JobState.FAILED,
}


def require_job_transition(from_state: JobState | None, event: str) -> JobState:
    """驗證並回傳下一個合法的 Job 狀態"""
    key = (from_state, event)
    try:
        return _ALLOWED_JOB_TRANSITIONS[key]
    except KeyError as exc:
        raise InvalidStateTransitionError(
            f"invalid job transition: from_state={from_state!s}, event={event}"
        ) from exc
