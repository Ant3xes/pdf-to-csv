from dataclasses import dataclass

TYPE_FACTURE = "FACTURE"
TYPE_AVOIR = "AVOIR"
TYPES_DOCUMENT = frozenset({TYPE_FACTURE, TYPE_AVOIR})


@dataclass(frozen=True)
class LigneFacture:
    fichier: str
    emetteur: str | None
    date: str | None
    montant_ht: str | None
    statut: str
    type_document: str
