from __future__ import annotations

import csv
from io import StringIO

from app.models import LigneFacture

_COLUMNS = ("fichier", "emetteur", "date", "montant_ttc", "statut")


def export_csv(lignes: list[LigneFacture]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=_COLUMNS,
        delimiter=";",
        lineterminator="\n",
    )
    writer.writeheader()
    for ligne in lignes:
        writer.writerow(
            {
                "fichier": ligne.fichier,
                "emetteur": ligne.emetteur or "",
                "date": ligne.date or "",
                "montant_ttc": ligne.montant_ttc or "",
                "statut": ligne.statut,
            }
        )
    return buffer.getvalue()
