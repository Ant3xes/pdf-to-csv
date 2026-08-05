from __future__ import annotations

import csv
from io import StringIO

from app.models import TYPE_FACTURE, LigneFacture

_COLUMNS = ("fichier", "emetteur", "date", "montant_ttc", "statut", "type")


def _sort_for_export(lignes: list[LigneFacture]) -> list[LigneFacture]:
    return sorted(
        lignes,
        key=lambda ligne: 0 if ligne.type_document == TYPE_FACTURE else 1,
    )


def export_csv(lignes: list[LigneFacture]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=_COLUMNS,
        delimiter=";",
        lineterminator="\n",
    )
    writer.writeheader()
    for ligne in _sort_for_export(lignes):
        writer.writerow(
            {
                "fichier": ligne.fichier,
                "emetteur": ligne.emetteur or "",
                "date": ligne.date or "",
                "montant_ttc": ligne.montant_ttc or "",
                "statut": ligne.statut,
                "type": ligne.type_document,
            }
        )
    return buffer.getvalue()
