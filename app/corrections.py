from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.amounts import MontantHt
from app.models import LigneFacture

_UNSET: Any = object()


def corriger_ligne(
    ligne: LigneFacture,
    *,
    emetteur: str | None = _UNSET,
    date: str | None = _UNSET,
    montant_ht: MontantHt | str | None = _UNSET,
    type_document: str | None = _UNSET,
) -> LigneFacture:
    """Correction manuelle éphémère : nouvelle ligne, templates intacts.

    Utilitaire de modèle (tests / agents). L'UI corrige en local ; la vérité
    runtime à l'export est l'état client validé par ``valider_export``.
    """
    updates: dict[str, Any] = {}
    if emetteur is not _UNSET:
        updates["emetteur"] = emetteur
    if date is not _UNSET:
        updates["date"] = date
    if montant_ht is not _UNSET:
        if isinstance(montant_ht, str):
            updates["montant_ht"] = MontantHt.parse_fr(montant_ht)
        else:
            updates["montant_ht"] = montant_ht
    if type_document is not _UNSET:
        updates["type_document"] = type_document
    return replace(ligne, **updates)
