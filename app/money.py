"""Money helpers. Amounts are stored as integer cents to avoid float rounding errors."""
from decimal import ROUND_HALF_UP, Decimal


def to_cents(value) -> int:
    """Convert a dollar amount (int, float, str or Decimal) to integer cents, rounding half up."""
    d = Decimal(str(value)) * 100
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_dollars(cents) -> float | None:
    return None if cents is None else round(cents / 100, 2)


def fmt(cents: int) -> str:
    return f"S${cents / 100:,.2f}"
