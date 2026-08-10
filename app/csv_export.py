from __future__ import annotations

import csv
from io import StringIO

from app.export_agrege import export_csv_agrege, valider_export
from app.models import TYPE_FACTURE, LigneFacture

_COLUMNS = ("fichier", "emetteur", "date", "montant_ht", "statut", "type")


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
                "montant_ht": (
                    ligne.montant_ht.format_fr() if ligne.montant_ht is not None else ""
                ),
                "statut": ligne.statut,
                "type": ligne.type_document,
            }
        )
    # BOM UTF-8 pour ouverture directe correcte dans Excel FR (#18).
    return "\ufeff" + buffer.getvalue()


__all__ = ["export_csv", "export_csv_agrege", "valider_export"]
