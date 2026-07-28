from __future__ import annotations

import re
from collections import defaultdict

_SIGNED_POINTS = re.compile(r"(?P<value>[+-]\d+)(?:\s+Punkte)?\b")
_BASE_PRIORITY = re.compile(r"Priorität gewichtet:\s*(?P<value>-?\d+)\s+Punkte")

_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Priorität", ("priorität", "eigenfuhrpark vor fremdvergabe", "kundenrichtlinie")),
    ("Kompatibilität", ("trailer", "mega-zugmaschine", "standardressource", "ressource genutzt")),
    ("Leerfahrt", ("leerfahrt", "anfahrt", "gleicher standort", "minimiert leeranfahrt")),
    ("Zeitfenster", ("zeitfenster", "umbuchung", "wartezeit")),
    ("Arbeitszeit", ("arbeitszeit", "anschlussverfügbarkeit", "schicht")),
    ("Fahrer/Fahrzeug", ("fahrer", "stamm", "gekoppelter trailer", "recoupling", "trailerwechsel")),
    ("Kettenbildung", ("transportkette", "rundtour", "folgeauftrag")),
    ("Flottenbalance", ("flottenauslastung", "ungenutztes geeignetes fahrzeug")),
    ("Planungsstabilität", ("bestehende tour", "planung bleibt stabil", "neue tour")),
)


def _category(reason: str) -> str:
    normalized = reason.casefold()
    for category, needles in _CATEGORY_RULES:
        if any(needle in normalized for needle in needles):
            return category
    return "Sonstiges"


def build_score_breakdown(reasons: list[str], final_score: int) -> dict[str, int]:
    """Derive an auditable component summary from the exact scoring reasons.

    The dispatcher already records every score mutation as a reason. Keeping the
    breakdown derived from those reasons avoids a second scoring implementation
    that could drift from the actual optimizer logic.
    """
    components: defaultdict[str, int] = defaultdict(int)
    accounted = 0
    for reason in reasons:
        base_match = _BASE_PRIORITY.search(reason)
        if base_match:
            value = int(base_match.group("value"))
            components["Priorität"] += value
            accounted += value
            continue
        match = _SIGNED_POINTS.search(reason)
        if not match:
            continue
        value = int(match.group("value"))
        components[_category(reason)] += value
        accounted += value

    difference = int(final_score) - accounted
    if difference:
        components["Grund-/Regelwert"] += difference
    return dict(sorted(components.items()))
