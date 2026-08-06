from __future__ import annotations

from app.export_agrege import export_csv_agrege, valider_export
from app.models import LigneFacture


def export_csv(lignes: list[LigneFacture]) -> str:
    return export_csv_agrege(lignes)


__all__ = ["export_csv", "export_csv_agrege", "valider_export"]
