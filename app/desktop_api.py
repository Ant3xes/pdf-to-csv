from __future__ import annotations

from pathlib import Path
from typing import Any


class DesktopApi:
    """API JS exposee a la fenetre pywebview (enregistrement de fichiers)."""

    def save_text_file(
        self,
        suggested_name: str,
        content: str,
        file_types: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        import webview

        window = webview.active_window()
        if window is None and webview.windows:
            window = webview.windows[0]
        if window is None:
            return {"saved": False, "error": "Fenetre indisponible."}

        types = file_types or (
            "Fichiers texte (*.txt;*.log)",
            "Tous les fichiers (*.*)",
        )
        # FileDialog.SAVE remplace SAVE_DIALOG (déprécié depuis pywebview récents).
        file_dialog = getattr(webview, "FileDialog", None)
        dialog_type = getattr(file_dialog, "SAVE", None)
        if dialog_type is None:
            dialog_type = webview.SAVE_DIALOG
        result = window.create_file_dialog(
            dialog_type,
            save_filename=suggested_name or "export.txt",
            file_types=tuple(types),
        )
        if not result:
            return {"saved": False, "cancelled": True}

        path = result if isinstance(result, (str, Path)) else result[0]
        Path(path).write_text(content, encoding="utf-8")
        return {"saved": True, "path": str(path)}
