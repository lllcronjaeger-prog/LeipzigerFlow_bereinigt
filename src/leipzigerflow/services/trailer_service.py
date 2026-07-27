from sqlalchemy.orm import Session
from leipzigerflow.database.repositories.trailer_repository import TrailerRepository
from leipzigerflow.models.trailer import Trailer, TrailerType
from leipzigerflow.models.resource_absence import TrailerAbsence


class TrailerService:
    def __init__(self, session: Session): self.repository = TrailerRepository(session)
    def get_all(self): return self.repository.get_all()
    def get(self, trailer_id): return self.repository.get(trailer_id)
    def add(self, trailer): self._validate(trailer); self.repository.add(trailer)
    def update(self, trailer): self._validate(trailer); self.repository.update(trailer)
    def delete(self, trailer): self.repository.delete(trailer)
    def replace_absences(self, trailer, drafts):
        trailer.absences.clear()
        for draft in drafts:
            trailer.absences.append(TrailerAbsence(
                starts_at=draft.starts_at, ends_at=draft.ends_at, reason=draft.reason,
                remarks=draft.remarks, active=draft.active,
            ))
        self.repository.update(trailer)

    def _validate(self, trailer: Trailer):
        trailer.trailer_number = trailer.trailer_number.strip().upper()
        trailer.license_plate = trailer.license_plate.strip().upper()
        trailer.location = trailer.location.strip()
        trailer.remarks = trailer.remarks.strip()
        if not trailer.trailer_number: raise ValueError("Bitte eine Trailernummer eingeben.")
        if not trailer.license_plate: raise ValueError("Bitte ein Kennzeichen eingeben.")
        if trailer.trailer_type not in TrailerType.values(): raise ValueError("Bitte einen gültigen Trailertyp auswählen.")
        existing=self.repository.get_by_number(trailer.trailer_number)
        if existing and existing.id != trailer.id: raise ValueError("Diese Trailernummer existiert bereits.")
        existing=self.repository.get_by_license_plate(trailer.license_plate)
        if existing and existing.id != trailer.id: raise ValueError("Dieses Trailer-Kennzeichen existiert bereits.")
