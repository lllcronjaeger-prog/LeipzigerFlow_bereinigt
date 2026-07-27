from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TourOptimizationProfile(StrEnum):
    FAST = "Schnellplanung"
    BALANCED = "Ausgewogene Planung"
    THOROUGH = "Optimale Planung"


@dataclass(frozen=True, slots=True)
class ProfileSettings:
    candidate_limit: int | None
    alternative_limit: int


PROFILE_SETTINGS = {
    TourOptimizationProfile.FAST: ProfileSettings(candidate_limit=10, alternative_limit=2),
    TourOptimizationProfile.BALANCED: ProfileSettings(candidate_limit=50, alternative_limit=3),
    TourOptimizationProfile.THOROUGH: ProfileSettings(candidate_limit=None, alternative_limit=5),
}
