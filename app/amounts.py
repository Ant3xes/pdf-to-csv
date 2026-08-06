from __future__ import annotations


def parse_montant_ht_fr(raw: str | None) -> float:
    """Parse un montant HT au format FR ; retourne 0 si vide ou invalide."""
    if raw is None:
        return 0.0
    cleaned = str(raw).strip().replace(" ", "")
    if not cleaned:
        return 0.0
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def format_montant_ht_fr(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")
