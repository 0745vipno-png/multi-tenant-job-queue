from __future__ import annotations
from abc import ABC, abstractmethod
from internal.context.tenant_context import TenantContext
from internal.domain.lease.model import Lease

class LeaseRepository(ABC):
    @abstractmethod
    def create_lease(self, lease: Lease) -> None:
        pass

    @abstractmethod
    def get_active_lease_by_token(self, tenant: TenantContext, token: str) -> Lease | None:
        pass

    @abstractmethod
    def release_lease(self, tenant: TenantContext, lease_id: str, event: str) -> None:
        pass
