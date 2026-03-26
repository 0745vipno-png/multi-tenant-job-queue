from __future__ import annotations

from internal.domain.common.errors import InvalidStateTransitionError
from internal.domain.lease.states import LeaseState


_ALLOWED_LEASE_TRANSITIONS: dict[tuple[LeaseState | None, str], LeaseState] = {
    (None, "create_lease"): LeaseState.ACTIVE,
    (LeaseState.ACTIVE, "normal_close_after_ack_or_failure"): LeaseState.RELEASED,
    (LeaseState.ACTIVE, "lease_timeout"): LeaseState.EXPIRED,
    (LeaseState.ACTIVE, "revoke_lease"): LeaseState.REVOKED,
}


def require_lease_transition(from_state: LeaseState | None, event: str) -> LeaseState:
    key = (from_state, event)
    try:
        return _ALLOWED_LEASE_TRANSITIONS[key]
    except KeyError as exc:
        raise InvalidStateTransitionError(
            f"invalid lease transition: from_state={from_state!s}, event={event}"
        ) from exc