from __future__ import annotations


class DomainError(Exception):
    """Base class for domain/application errors."""


class InvalidStateTransitionError(DomainError):
    pass


class WorkerUnavailableError(DomainError):
    pass


class JobNotLeaseableError(DomainError):
    pass


class LeaseConflictError(DomainError):
    pass


class TenantScopeError(DomainError):
    pass