from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import timedelta

from leipzigerflow.planner.engine.models import (
    ProposedAssignment, ProposedTour, ProposedTourSegment, TourSegmentType,
)
from leipzigerflow.planner.engine.tour_quality import TourQualityEvaluator


_POSTCODE = re.compile(r"(?<!\d)(\d{5})(?!\d)")


@dataclass(slots=True)
class _TourCluster:
    assignments: list[ProposedAssignment] = field(default_factory=list)
    region_keys: set[str] = field(default_factory=set)
    trailer_types: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)


class AutomaticTourBuilder:
    """Builds explainable daily tours from assignment proposals.

    Sprint 16.1 adds a deterministic clustering layer. Assignments remain bound
    to the resource chosen by the dispatcher, but are split into separate tours
    when region, date, time sequence or trailer requirements no longer fit.
    This keeps the result safe to apply while already providing TourBuilder-2.0
    style, transparent tour combinations.
    """

    MAX_GAP = timedelta(hours=6)

    def __init__(self):
        self.quality_evaluator = TourQualityEvaluator()

    def build(self, assignments: list[ProposedAssignment]) -> list[ProposedTour]:
        grouped: OrderedDict[tuple[int, int | None, int | None], list[ProposedAssignment]] = OrderedDict()
        for assignment in assignments:
            key = (
                int(assignment.vehicle_id),
                int(assignment.driver_id) if assignment.driver_id else None,
                int(assignment.source_tour_id) if assignment.source_tour_id else None,
            )
            grouped.setdefault(key, []).append(assignment)

        tours: list[ProposedTour] = []
        sequence = 1
        for (vehicle_id, driver_id, source_tour_id), items in grouped.items():
            ordered = sorted(items, key=lambda item: (item.loading_at, item.order_number))
            clusters = self._cluster(ordered)
            for cluster_index, cluster in enumerate(clusters, start=1):
                for position, item in enumerate(cluster.assignments, start=1):
                    item.proposed_tour_position = position
                source_number = cluster.assignments[0].source_tour_number if cluster.assignments else ""
                proposal_number = source_number or f"Vorschlag-{sequence:03d}"
                if source_number and len(clusters) > 1:
                    proposal_number = f"{source_number}-{cluster_index}"
                segments = self._build_segments(cluster.assignments)
                known_distances = [segment.distance_km for segment in segments if segment.distance_km is not None]
                quality = self.quality_evaluator.evaluate(cluster.assignments)
                tours.append(ProposedTour(
                    proposal_number=proposal_number,
                    vehicle_id=vehicle_id,
                    vehicle_label=cluster.assignments[0].vehicle_label,
                    driver_id=driver_id,
                    driver_label=cluster.assignments[0].driver_label,
                    source_tour_id=source_tour_id,
                    source_tour_number=source_number,
                    assignments=cluster.assignments,
                    cluster_label=self._cluster_label(cluster),
                    cluster_score=self._cluster_score(cluster),
                    cluster_reasons=cluster.reasons or ["Zeitlich und ressourcenseitig kompatible Auftragsfolge"],
                    total_distance_km=(sum(known_distances) if segments and len(known_distances) == len(segments) else None),
                    total_route_minutes=sum(segment.duration_minutes for segment in segments),
                    distance_estimated=any(a.route_estimated for a in cluster.assignments),
                    quality_score=quality.score,
                    quality_reasons=quality.reasons,
                    empty_transfer_minutes=quality.empty_transfer_minutes,
                    overnight_count=quality.overnight_count,
                    segments=segments,
                ))
                sequence += 1
        return tours

    @staticmethod
    def _build_segments(assignments: list[ProposedAssignment]) -> list[ProposedTourSegment]:
        segments: list[ProposedTourSegment] = []
        ordered = sorted(assignments, key=lambda item: (item.loading_at, item.order_number))
        for index, assignment in enumerate(ordered):
            transfer_minutes = max(0, int(assignment.transfer_minutes or 0))
            if transfer_minutes:
                segments.append(ProposedTourSegment(
                    segment_type=(TourSegmentType.START_EMPTY_RUN if index == 0 else TourSegmentType.EMPTY_RUN),
                    started_at=assignment.loading_at - timedelta(minutes=transfer_minutes),
                    ended_at=assignment.loading_at,
                    origin_label=assignment.start_location_label or (ordered[index - 1].unloading_location_label if index else "Heimatbasis"),
                    destination_label=assignment.loading_location_label,
                    duration_minutes=transfer_minutes,
                    distance_km=assignment.transfer_distance_km,
                    order_number=assignment.order_number,
                    estimated=assignment.transfer_route_estimated,
                ))
            transport_start = assignment.loading_at
            transport_end = assignment.available_again_at
            segments.append(ProposedTourSegment(
                segment_type=TourSegmentType.TRANSPORT,
                started_at=transport_start,
                ended_at=transport_end,
                origin_label=assignment.loading_location_label,
                destination_label=assignment.unloading_location_label,
                duration_minutes=max(0, round((transport_end - transport_start).total_seconds() / 60)),
                distance_km=assignment.route_distance_km,
                order_number=assignment.order_number,
                estimated=assignment.route_estimated,
            ))
        if ordered:
            last = ordered[-1]
            return_minutes = max(0, int(last.return_to_base_minutes or 0))
            if last.return_to_base_required and return_minutes:
                segments.append(ProposedTourSegment(
                    segment_type=TourSegmentType.RETURN_TO_BASE,
                    started_at=last.available_again_at,
                    ended_at=last.available_again_at + timedelta(minutes=return_minutes),
                    origin_label=last.unloading_location_label,
                    destination_label=last.home_base_location_label or "Heimatbasis",
                    duration_minutes=return_minutes,
                    distance_km=last.return_to_base_distance_km,
                    estimated=last.return_route_estimated,
                ))
        return segments

    def _cluster(self, assignments: list[ProposedAssignment]) -> list[_TourCluster]:
        clusters: list[_TourCluster] = []
        for assignment in assignments:
            best: _TourCluster | None = None
            best_score = -1
            for cluster in clusters:
                score, reasons = self._compatibility(cluster, assignment)
                if score > best_score and score >= 60:
                    best, best_score = cluster, score
                    best_reasons = reasons
            if best is None:
                region = self._region_key(assignment.unloading_postal_code or assignment.unloading_location_label)
                cluster = _TourCluster(
                    assignments=[assignment],
                    region_keys={region} if region else set(),
                    trailer_types=self._trailer_types(assignment),
                    reasons=[f"Neuer Cluster für Region {region}" if region else "Neuer eigenständiger Auftragscluster"],
                )
                clusters.append(cluster)
            else:
                best.assignments.append(assignment)
                region = self._region_key(assignment.unloading_postal_code or assignment.unloading_location_label)
                if region:
                    best.region_keys.add(region)
                best.trailer_types.update(self._trailer_types(assignment))
                for reason in best_reasons:
                    if reason not in best.reasons:
                        best.reasons.append(reason)
        return clusters

    def _compatibility(self, cluster: _TourCluster, assignment: ProposedAssignment) -> tuple[int, list[str]]:
        previous = cluster.assignments[-1]
        if previous.loading_at.date() != assignment.loading_at.date():
            return 0, ["Unterschiedliche Planungstage"]
        if assignment.loading_at < previous.loading_at:
            return 0, ["Zeitliche Reihenfolge nicht möglich"]
        gap = assignment.loading_at - previous.available_again_at
        if gap > self.MAX_GAP:
            return 20, [f"Zeitlücke von {round(gap.total_seconds() / 3600, 1)} Stunden zu groß"]

        score = 45
        reasons: list[str] = ["Zeitfenster liegen in einer sinnvollen Tagesfolge"]
        new_types = self._trailer_types(assignment)
        if not cluster.trailer_types or not new_types or cluster.trailer_types.intersection(new_types):
            score += 25
            reasons.append("Traileranforderungen sind kompatibel")
        else:
            score -= 35
            reasons.append("Abweichende Traileranforderungen")

        region = self._region_key(assignment.unloading_postal_code or assignment.unloading_location_label)
        if region and region in cluster.region_keys:
            score += 25
            reasons.append(f"Gemeinsame Entladeregion {region}")
        elif region and self._neighboring_region(region, cluster.region_keys):
            score += 15
            reasons.append(f"Benachbarte Entladeregion {region}")
        elif self._same_location(previous.unloading_location_label, assignment.loading_location_label):
            score += 25
            reasons.append("Folgeauftrag beginnt am vorherigen Entladeort")
        else:
            score += 5
            reasons.append("Regionale Verbindung nur eingeschränkt erkennbar")

        if gap.total_seconds() < 0:
            score -= 20
            reasons.append("Zeitliche Überschneidung muss geprüft werden")
        elif gap <= timedelta(hours=2):
            score += 10
            reasons.append("Kurzer Übergang zwischen den Aufträgen")
        return max(0, min(100, score)), reasons

    @staticmethod
    def _trailer_types(assignment: ProposedAssignment) -> set[str]:
        value = assignment.required_trailer_types or ""
        return {part.strip().casefold() for part in re.split(r"[,;/|+]", value) if part.strip()}

    @staticmethod
    def _region_key(label: str) -> str:
        match = _POSTCODE.search(label or "")
        return match.group(1)[:2] if match else ""

    @staticmethod
    def _neighboring_region(region: str, existing: set[str]) -> bool:
        if not region.isdigit():
            return False
        return any(item.isdigit() and abs(int(item) - int(region)) <= 1 for item in existing)

    @staticmethod
    def _same_location(left: str, right: str) -> bool:
        def normalize(value: str) -> str:
            return re.sub(r"\W+", " ", (value or "").casefold()).strip()
        return bool(left and right and normalize(left) == normalize(right))

    @staticmethod
    def _cluster_label(cluster: _TourCluster) -> str:
        regions = ", ".join(sorted(cluster.region_keys)) or "ohne PLZ-Region"
        trailers = ", ".join(sorted(value.title() for value in cluster.trailer_types)) or "flexibel"
        return f"Region {regions} · {trailers}"

    @staticmethod
    def _cluster_score(cluster: _TourCluster) -> int:
        if len(cluster.assignments) <= 1:
            return 70
        region_bonus = 15 if len(cluster.region_keys) <= 1 else max(0, 12 - 3 * (len(cluster.region_keys) - 1))
        trailer_bonus = 15 if len(cluster.trailer_types) <= 1 else max(0, 12 - 4 * (len(cluster.trailer_types) - 1))
        compactness = min(20, len(cluster.assignments) * 5)
        return min(100, 50 + region_bonus + trailer_bonus + compactness)
