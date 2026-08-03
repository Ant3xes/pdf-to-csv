from dataclasses import dataclass


@dataclass(frozen=True)
class LigneFacture:
    fichier: str
    emetteur: str | None
    date: str | None
    montant_ttc: str | None
    statut: str
