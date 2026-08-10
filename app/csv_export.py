from __future__ import annotations

import csv
from io import StringIO

from app.export_agrege import (
    export_csv_agrege,
    montant_cell,
    sort_facture_avant_avoir,
    valider_export,
)
from app.models import LigneFacture

_COLUMNS = ("fichier", "emetteur", "date", "montant_ht", "statut", "type")


def export_csv(lignes: list[LigneFacture]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=_COLUMNS,
        delimiter=";",
        lineterminator="\n",
    )
    writer.writeheader()
    for ligne in sort_facture_avant_avoir(lignes):
        writer.writerow(
            {
                "fichier": ligne.fichier,
                "emetteur": ligne.emetteur or "",
                "date": ligne.date or "",
                "montant_ht": montant_cell(ligne),
                "statut": ligne.statut,
                "type": ligne.type_document,
            }
        )
    # BOM UTF-8 pour ouverture directe correcte dans Excel FR (#18).
    return "\ufeff" + buffer.getvalue()


__all__ = ["export_csv", "export_csv_agrege", "valider_export"]
