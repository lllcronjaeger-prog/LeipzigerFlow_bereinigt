from __future__ import annotations

SEPARATOR = ";"

TRAILER_TYPES = (
    "Plane",
    "Mega-Plane",
    "Koffer",
    "Mega-Koffer",
    "Kühler",
    "Mega-Kühler",
)


def parse_trailer_types(value: object) -> tuple[str, ...]:
    """Liest alte Einzelwerte und neue, semikolongetrennte Mehrfachwerte."""
    if isinstance(value, (list, tuple, set, frozenset)):
        raw_items = [str(item).strip() for item in value]
    else:
        raw = str(value or "").strip()
        if not raw:
            return ("Plane",)
        raw_items = raw.replace(",", SEPARATOR).split(SEPARATOR)
    values = []
    for item in raw_items:
        trailer_type = item.strip()
        if trailer_type in TRAILER_TYPES and trailer_type not in values:
            values.append(trailer_type)
    return tuple(values) or ("Plane",)


def serialize_trailer_types(values: object) -> str:
    if isinstance(values, str):
        parsed = parse_trailer_types(values)
    else:
        parsed = tuple(
            value for value in TRAILER_TYPES
            if value in {str(item).strip() for item in (values or [])}
        )
    return SEPARATOR.join(parsed or ("Plane",))


def display_trailer_types(value: object) -> str:
    return ", ".join(parse_trailer_types(value))


def requires_mega_only(value: object) -> bool:
    types = parse_trailer_types(value)
    return bool(types) and all(item.startswith("Mega-") for item in types)


def requires_refrigeration_only(value: object) -> bool:
    types = parse_trailer_types(value)
    return bool(types) and all(item in {"Kühler", "Mega-Kühler"} for item in types)
