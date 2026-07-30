from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditActor:
    user_id: int | None = None
    username: str = ""
    display_name: str = ""
    source: str = "System"
    reason: str = ""


_actor: ContextVar[AuditActor] = ContextVar("leipzigerflow_audit_actor", default=AuditActor())


def current_actor() -> AuditActor:
    return _actor.get()


def set_user(user_id: int | None, username: str = "", display_name: str = "") -> None:
    _actor.set(AuditActor(user_id, username, display_name, "Benutzer", ""))


def clear_user() -> None:
    _actor.set(AuditActor())


@contextmanager
def audit_scope(source: str, reason: str = ""):
    current = current_actor()
    token = _actor.set(AuditActor(current.user_id, current.username, current.display_name, source, reason))
    try:
        yield
    finally:
        _actor.reset(token)
