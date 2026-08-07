from __future__ import annotations

from datetime import datetime, timezone


class DiagnosticJournal:
    """Journal ephemere de diagnostic du Lot (session processus)."""

    def __init__(self, *, max_entries: int = 2000) -> None:
        self._max_entries = max_entries
        self._entries: list[str] = []

    def clear(self) -> None:
        self._entries.clear()

    def is_empty(self) -> bool:
        return not self._entries

    def record(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._entries.append(f"{stamp} {message}")
        if len(self._entries) > self._max_entries:
            overflow = len(self._entries) - self._max_entries
            del self._entries[:overflow]

    def export_text(self) -> str:
        return "\n".join(self._entries) + ("\n" if self._entries else "")
