from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class MontantHt:
    """Montant HT numérique ; le format FR n'apparaît qu'à la sérialisation."""

    value: Decimal

    def __post_init__(self) -> None:
        quantized = self.value.quantize(Decimal("0.01"))
        object.__setattr__(self, "value", quantized)

    @classmethod
    def from_raw(
        cls,
        raw: str,
        decimal_separator: str,
        amount_sign: str | None = None,
    ) -> MontantHt | None:
        cleaned = raw.strip().replace(" ", "")
        if decimal_separator == ",":
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
        try:
            value = Decimal(cleaned)
        except InvalidOperation:
            return None
        if amount_sign == "negative" and value > 0:
            value = -value
        return cls(value)

    @classmethod
    def parse_fr(cls, raw: str | None) -> MontantHt | None:
        """Parse un montant HT au format FR ; None si vide ou invalide."""
        if raw is None:
            return None
        cleaned = str(raw).strip().replace(" ", "")
        if not cleaned:
            return None
        cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return cls(Decimal(cleaned))
        except InvalidOperation:
            return None

    def format_fr(self) -> str:
        return f"{self.value:.2f}".replace(".", ",")

    def __add__(self, other: MontantHt) -> MontantHt:
        if not isinstance(other, MontantHt):
            return NotImplemented
        return MontantHt(self.value + other.value)


def format_montant_ht_fr(value: Decimal | float | int) -> str:
    return MontantHt(Decimal(str(value))).format_fr()
