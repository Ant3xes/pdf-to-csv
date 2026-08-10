"""Helpers partages des tests (assertions sur le domaine, pas de fixtures)."""

from __future__ import annotations


def montant_fr(ligne):
    """Montant HT format FR pour assertions ; None si absent."""
    return ligne.montant_ht.format_fr() if ligne.montant_ht else None
