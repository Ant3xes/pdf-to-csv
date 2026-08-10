from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO

from app.amounts import format_montant_ht_fr
from app.models import TYPE_FACTURE, LigneFacture

_COLUMNS_AGREGE = (
    "emetteur",
    "montant_ht",
    "nb_documents",
    "fichier",
    "date",
    "statut",
    "type",
)


@dataclass(frozen=True)
class TotalEmetteur:
    emetteur: str
    montant_ht: str
    nb_documents: int


def valider_export(lignes: list[LigneFacture]) -> str | None:
    if not lignes:
        return "Aucune ligne à exporter."
    for ligne in lignes:
        if ligne.statut not in ("OK", "A_VERIFIER"):
            return "Export impossible : statut de facture invalide."
    return None


def _a_un_emetteur(ligne: LigneFacture) -> bool:
    return bool((ligne.emetteur or "").strip())


def _sort_detail(lignes: list[LigneFacture]) -> list[LigneFacture]:
    return sorted(
        lignes,
        key=lambda ligne: 0 if ligne.type_document == TYPE_FACTURE else 1,
    )


def _montant_cell(ligne: LigneFacture) -> str:
    if ligne.montant_ht is None:
        return ""
    return ligne.montant_ht.format_fr()


def agreger_par_emetteur(lignes: list[LigneFacture]) -> list[TotalEmetteur]:
    totals: dict[str, tuple[Decimal, int]] = {}
    for ligne in lignes:
        emetteur = ligne.emetteur.strip() if ligne.emetteur else ""
        amount = ligne.montant_ht.value if ligne.montant_ht is not None else Decimal("0")
        if emetteur in totals:
            prev_sum, prev_count = totals[emetteur]
            totals[emetteur] = (prev_sum + amount, prev_count + 1)
        else:
            totals[emetteur] = (amount, 1)
    return [
        TotalEmetteur(
            emetteur=emetteur,
            montant_ht=format_montant_ht_fr(total),
            nb_documents=count,
        )
        for emetteur, (total, count) in sorted(totals.items())
    ]


def export_csv_agrege(lignes: list[LigneFacture]) -> str:
    """Agrège par Émetteur nommé ; les Factures sans Émetteur restent en détail."""
    sans_emetteur = [ligne for ligne in lignes if not _a_un_emetteur(ligne)]
    avec_emetteur = [ligne for ligne in lignes if _a_un_emetteur(ligne)]
    totaux = agreger_par_emetteur(avec_emetteur)

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=_COLUMNS_AGREGE,
        delimiter=";",
        lineterminator="\n",
    )
    writer.writeheader()
    for ligne in _sort_detail(sans_emetteur):
        writer.writerow(
            {
                "emetteur": "",
                "montant_ht": _montant_cell(ligne),
                "nb_documents": "1",
                "fichier": ligne.fichier,
                "date": ligne.date or "",
                "statut": ligne.statut,
                "type": ligne.type_document,
            }
        )
    for total in totaux:
        writer.writerow(
            {
                "emetteur": total.emetteur,
                "montant_ht": total.montant_ht,
                "nb_documents": str(total.nb_documents),
                "fichier": "",
                "date": "",
                "statut": "",
                "type": "",
            }
        )
    # BOM UTF-8 pour ouverture directe correcte dans Excel FR (#18).
    return "\ufeff" + buffer.getvalue()
