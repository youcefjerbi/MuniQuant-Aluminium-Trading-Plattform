"""Deterministic industrial-unit normalization.

Reported values are preserved by the caller.  This module only converts explicit,
recognized spellings and deliberately refuses ambiguous lower-case ``mt`` units.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class UnitError(ValueError):
    pass


@dataclass(frozen=True)
class UnitDefinition:
    code: str
    dimension: str
    base_unit: str
    factor: Decimal


UNITS = {
    item.code: item
    for item in (
        UnitDefinition("t/year", "MASS_RATE", "t/year", Decimal("1")),
        UnitDefinition("kt/year", "MASS_RATE", "t/year", Decimal("1000")),
        UnitDefinition("Mt/year", "MASS_RATE", "t/year", Decimal("1000000")),
        UnitDefinition("t/day", "MASS_RATE", "t/year", Decimal("365")),
        UnitDefinition("MW", "POWER", "MW", Decimal("1")),
        UnitDefinition("GW", "POWER", "MW", Decimal("1000")),
        UnitDefinition("%", "RATIO", "ratio", Decimal("0.01")),
        UnitDefinition("ratio", "RATIO", "ratio", Decimal("1")),
    )
}

ALIASES = {
    "tpa": "t/year",
    "tpy": "t/year",
    "t/yr": "t/year",
    "tonnes/year": "t/year",
    "tonnes per year": "t/year",
    "tpd": "t/day",
    "t/d": "t/day",
    "ktpa": "kt/year",
    "kt/yr": "kt/year",
    "kt/a": "kt/year",
    "thousand tonnes per year": "kt/year",
    "Mtpa": "Mt/year",
    "Mt/yr": "Mt/year",
    "Mt/a": "Mt/year",
    "million tonnes per year": "Mt/year",
}


def resolve_unit(reported: str) -> str:
    value = reported.strip()
    if value in UNITS:
        return value
    if value in ALIASES:
        return ALIASES[value]
    lowered = value.lower()
    if lowered.startswith("mt"):
        raise UnitError(f"ambiguous unit {reported!r}: use 't', 'kt', or capitalized 'Mt' explicitly")
    case_insensitive = {key.lower(): target for key, target in ALIASES.items() if not key.startswith("Mt")}
    if lowered in case_insensitive:
        return case_insensitive[lowered]
    raise UnitError(f"unsupported unit {reported!r}")


def normalize(value: str | int | Decimal, reported_unit: str, *, expected_dimension: str | None = None):
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise UnitError(f"invalid numeric value {value!r}") from exc
    if not number.is_finite() or number < 0:
        raise UnitError("value must be finite and nonnegative")
    code = resolve_unit(reported_unit)
    definition = UNITS[code]
    if expected_dimension and definition.dimension != expected_dimension:
        raise UnitError(f"unit {code!r} has dimension {definition.dimension}, expected {expected_dimension}")
    return (number * definition.factor).normalize(), definition.base_unit, code
