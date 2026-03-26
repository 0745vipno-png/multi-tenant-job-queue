from __future__ import annotations

import secrets
import uuid
from typing import Protocol


class IdGenerator(Protocol):
    def new_id(self) -> str:
        ...

    def new_token(self) -> str:
        ...


class UUIDGenerator:
    def new_id(self) -> str:
        return str(uuid.uuid4())

    def new_token(self) -> str:
        return secrets.token_urlsafe(32)