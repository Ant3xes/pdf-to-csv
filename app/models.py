from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.amounts import MontantHt

TYPE_FACTURE = "FACTURE"
TYPE_AVOIR = "AVOIR"
TYPES_DOCUMENT = frozenset({TYPE_FACTURE, TYPE_AVOIR})

STATUT_OK = "OK"
STATUT_A_VERIFIER = "A_VERIFIER"

_DEFAULT_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y")


@dataclass(frozen=True)
class LigneFacture:
    fichier: str
    emetteur: str | None
    date: str | None
    montant_ht: MontantHt | None
    statut: str
    type_document: str

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "fichier": self.fichier,
            "emetteur": self.emetteur,
            "date": self.date,
            "montant_ht": self.montant_ht.format_fr() if self.montant_ht else None,
            "statut": self.statut,
            "type_document": self.type_document,
        }


@dataclass(frozen=True)
class Template:
    """Contrat typé d'un Template YAML (Fournisseur → règles d'extraction)."""

    issuer: str
    keywords: tuple[str, ...]
    date_pattern: str | None
    amount_pattern: str | None
    date_formats: tuple[str, ...]
    decimal_separator: str
    amount_sign: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Template:
        issuer = data.get("issuer")
        if not isinstance(issuer, str) or not issuer.strip():
            raise ValueError("Template invalide : 'issuer' obligatoire (chaîne non vide).")

        keywords_raw = data.get("keywords")
        if keywords_raw is None:
            keywords_raw = []
        if not isinstance(keywords_raw, list) or not all(
            isinstance(k, str) for k in keywords_raw
        ):
            raise ValueError("Template invalide : 'keywords' doit être une liste de chaînes.")

        fields = data.get("fields") or {}
        if not isinstance(fields, dict):
            raise ValueError("Template invalide : 'fields' doit être un objet.")

        date_pattern = fields.get("date")
        amount_pattern = fields.get("amount")
        if date_pattern is not None and not isinstance(date_pattern, str):
            raise ValueError("Template invalide : fields.date doit être une chaîne.")
        if amount_pattern is not None and not isinstance(amount_pattern, str):
            raise ValueError("Template invalide : fields.amount doit être une chaîne.")

        options = data.get("options") or {}
        if not isinstance(options, dict):
            raise ValueError("Template invalide : 'options' doit être un objet.")

        date_formats_raw = options.get("date_formats")
        if date_formats_raw is None:
            date_formats: tuple[str, ...] = _DEFAULT_DATE_FORMATS
        else:
            if not isinstance(date_formats_raw, list) or not date_formats_raw or not all(
                isinstance(fmt, str) for fmt in date_formats_raw
            ):
                raise ValueError(
                    "Template invalide : options.date_formats doit être une liste de chaînes."
                )
            date_formats = tuple(date_formats_raw)

        decimal_separator = options.get("decimal_separator", ",")
        if not isinstance(decimal_separator, str) or decimal_separator not in {",", "."}:
            raise ValueError(
                "Template invalide : options.decimal_separator doit être ',' ou '.'."
            )

        amount_sign = options.get("amount_sign")
        if amount_sign is not None and amount_sign != "negative":
            raise ValueError(
                "Template invalide : options.amount_sign doit être 'negative' ou absent."
            )

        return cls(
            issuer=issuer.strip(),
            keywords=tuple(keywords_raw),
            date_pattern=date_pattern,
            amount_pattern=amount_pattern,
            date_formats=date_formats,
            decimal_separator=decimal_separator,
            amount_sign=amount_sign,
        )
