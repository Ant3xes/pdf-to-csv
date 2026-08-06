from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

from app.amounts import format_montant_ht_fr, parse_montant_ht_fr
from app.models import LigneFacture

_COLUMNS = ("emetteur", "montant_ht", "nb_documents")


@dataclass(frozen=True)
class TotalEmetteur:
    emetteur: str
    montant_ht: str
    nb_documents: int


def valider_export(lignes: list[LigneFacture]) -> str | None:
    if not lignes:
        return "Aucune ligne à exporter."
    for ligne in lignes:
        if ligne.statut == "A_VERIFIER":
            return "Export impossible : des factures sont encore à vérifier."
        emetteur = (ligne.emetteur or "").strip()
        if not emetteur:
            return "Export impossible : une facture n'a pas d'émetteur."
    return None


def agreger_par_emetteur(lignes: list[LigneFacture]) -> list[TotalEmetteur]:
    totals: dict[str, tuple[float, int]] = {}
    for ligne in lignes:
        emetteur = ligne.emetteur.strip() if ligne.emetteur else ""
        amount = parse_montant_ht_fr(ligne.montant_ht)
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
    totaux = agreger_par_emetteur(lignes)
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=_COLUMNS,
        delimiter=";",
        lineterminator="\n",
    )
    writer.writeheader()
    for total in totaux:
        writer.writerow(
            {
                "emetteur": total.emetteur,
                "montant_ht": total.montant_ht,
                "nb_documents": str(total.nb_documents),
            }
        )
    return buffer.getvalue()
