from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from leipzigerflow.models.audit import AuditLog
from leipzigerflow.services.audit_context import current_actor


_EXCLUDED = {"AuditLog", "User", "Role", "Permission"}
_INSTALLED = False


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    text = str(value)
    return text if len(text) <= 4000 else text[:3997] + "..."


def _label(obj: object) -> str:
    for name in ("display_name", "order_number", "tour_number", "license_plate", "name", "username"):
        value = getattr(obj, name, None)
        if value:
            return str(value)[:255]
    return obj.__class__.__name__


def install_audit_listeners() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    @event.listens_for(Session, "before_flush")
    def collect_changes(session: Session, _flush_context, _instances) -> None:
        if session.info.get("_writing_audit"):
            return
        actor = current_actor()
        changes: list[dict[str, str | int | None]] = []

        for obj in list(session.new):
            if obj.__class__.__name__ in _EXCLUDED:
                continue
            state = inspect(obj)
            values = []
            for attr in state.mapper.column_attrs:
                if attr.key in {"created_at", "updated_at"}:
                    continue
                value = getattr(obj, attr.key, None)
                if value not in (None, "", False, 0):
                    values.append(f"{attr.key}={_text(value)}")
            changes.append({
                "user_id": actor.user_id, "username": actor.username,
                "display_name": actor.display_name, "source": actor.source,
                "entity_type": obj.__class__.__name__, "entity_id": "",
                "entity_label": _label(obj), "action": "Angelegt",
                "field_name": "", "old_value": "", "new_value": "; ".join(values),
                "reason": actor.reason,
            })

        for obj in list(session.dirty):
            if obj.__class__.__name__ in _EXCLUDED or not session.is_modified(obj, include_collections=False):
                continue
            state = inspect(obj)
            for attr in state.mapper.column_attrs:
                if attr.key in {"created_at", "updated_at"}:
                    continue
                history = state.attrs[attr.key].history
                if not history.has_changes():
                    continue
                old = history.deleted[0] if history.deleted else None
                new = history.added[0] if history.added else getattr(obj, attr.key, None)
                changes.append({
                    "user_id": actor.user_id, "username": actor.username,
                    "display_name": actor.display_name, "source": actor.source,
                    "entity_type": obj.__class__.__name__,
                    "entity_id": _text(getattr(obj, "id", "")),
                    "entity_label": _label(obj), "action": "Geändert",
                    "field_name": attr.key, "old_value": _text(old), "new_value": _text(new),
                    "reason": actor.reason,
                })

        for obj in list(session.deleted):
            if obj.__class__.__name__ in _EXCLUDED:
                continue
            changes.append({
                "user_id": actor.user_id, "username": actor.username,
                "display_name": actor.display_name, "source": actor.source,
                "entity_type": obj.__class__.__name__,
                "entity_id": _text(getattr(obj, "id", "")),
                "entity_label": _label(obj), "action": "Gelöscht",
                "field_name": "", "old_value": _label(obj), "new_value": "",
                "reason": actor.reason,
            })
        if changes:
            session.info.setdefault("_pending_audit", []).extend(changes)

    @event.listens_for(Session, "after_flush_postexec")
    def write_changes(session: Session, _flush_context) -> None:
        pending = session.info.pop("_pending_audit", [])
        if not pending or session.info.get("_writing_audit"):
            return
        session.info["_writing_audit"] = True
        try:
            session.add_all(AuditLog(**item) for item in pending)
        finally:
            session.info["_writing_audit"] = False


class AuditService:
    def __init__(self, session: Session):
        self.session = session

    def latest(self, *, limit: int = 500, username: str = "", entity_type: str = "") -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(limit)
        if username:
            stmt = stmt.where(AuditLog.username.ilike(f"%{username.strip()}%"))
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        return list(self.session.scalars(stmt))

    def for_entity(self, entity_type: str, entity_id: object) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(entity_id))
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        )
        return list(self.session.scalars(stmt))
