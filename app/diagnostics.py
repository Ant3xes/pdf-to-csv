from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

JOURNAL_TZ = ZoneInfo("Europe/Paris")

ACTION_KINDS = frozenset(
    {
        "depot",
        "correction",
        "validation",
        "type_document",
        "apercu",
        "export_csv",
        "export_journal",
        "nouveau_lot",
    }
)
# Contrat UI → /api/journal/events. Les lignes « pipeline » sont côté serveur.


def format_timestamp(when: datetime | None = None) -> str:
    """Date et heure locales (Europe/Paris) : YYYY-MM-DD HH:MM:SS."""
    stamp = when or datetime.now(JOURNAL_TZ)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=JOURNAL_TZ)
    else:
        stamp = stamp.astimezone(JOURNAL_TZ)
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


def format_action_line(action: str, fields: Mapping[str, Any] | None = None) -> str:
    """Ligne journal stable : action=<nom> cle=valeur …"""
    parts = [f"action={action}"]
    if fields:
        for key, value in fields.items():
            if key == "action" or value is None:
                continue
            parts.append(f"{key}={value}")
    return " ".join(parts)


class DiagnosticJournal:
    """Journal ephemere de session du Lot (diagnostics + actions utilisateur)."""

    def __init__(self, *, max_entries: int = 5000) -> None:
        self._max_entries = max_entries
        self._entries: list[str] = []

    def clear(self) -> None:
        self._entries.clear()

    def is_empty(self) -> bool:
        return not self._entries

    def record(self, message: str) -> None:
        self._entries.append(f"{format_timestamp()} {message}")
        if len(self._entries) > self._max_entries:
            overflow = len(self._entries) - self._max_entries
            del self._entries[:overflow]

    def record_action(self, action: str, fields: Mapping[str, Any] | None = None) -> None:
        self.record(format_action_line(action, fields))

    def export_text(self) -> str:
        return "\n".join(self._entries) + ("\n" if self._entries else "")
