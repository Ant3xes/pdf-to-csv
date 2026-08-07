from __future__ import annotations

from pathlib import Path
from typing import Any


class DesktopApi:
    """API JS exposee a la fenetre pywebview (enregistrement de fichiers)."""

    def save_text_file(self, suggested_name: str, content: str) -> dict[str, Any]:
        import webview

        window = webview.active_window()
        if window is None and webview.windows:
            window = webview.windows[0]
        if window is None:
            return {"saved": False, "error": "Fenetre indisponible."}

        result = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=suggested_name or "journal.txt",
            file_types=("Fichiers texte (*.txt;*.log)", "Tous les fichiers (*.*)"),
        )
        if not result:
            return {"saved": False, "cancelled": True}

        path = result if isinstance(result, (str, Path)) else result[0]
        Path(path).write_text(content, encoding="utf-8")
        return {"saved": True, "path": str(path)}
