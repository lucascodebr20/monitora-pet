from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.domain.clock import local_today, utc_bounds_for_local_date
from app.domain.errors import EntityConflictError, EntityNotFoundError, InvalidDomainValueError
from app.infra.media.health_file_store import HealthFileStore
from app.infra.repositories.pet_health_repository import PetHealthRepository
from app.infra.repositories.pet_repository import PetRepository

REMINDER_WINDOW_DAYS = 14
DEFAULT_TIMELINE_DAYS = 30
MAX_TIMELINE_DAYS = 366
MAX_WEIGHT_KG = 150.0
CONFIRMED_DECISIONS = {"CONFIRMED", "CORRECTED", "MULTIPLE_PETS"}
DISCARDED_DECISIONS = {"FALSE_POSITIVE", "NO_ACTION"}
ZONE_LABELS = {"FOOD": "comida", "WATER": "água", "LITTER": "caixa de areia", "CUSTOM": "outras áreas"}
FOOD_TYPE_LABELS = {"DRY": "seca", "WET": "úmida", "OTHER": "outro"}
DOSE_KIND_LABELS = {"VACCINE": "Vacina", "MEDICATION": "Remédio", "ANTIPARASITIC": "Antiparasitário"}


def parse_day(value: str | None, field: str, *, required: bool = True) -> str | None:
    if not value:
        if required:
            raise InvalidDomainValueError(f"Informe {field}.")
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise InvalidDomainValueError(f"Data inválida em {field}.") from error


def parse_instant(value: str, field: str) -> str:
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidDomainValueError(f"Data e hora inválidas em {field}.") from error
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.astimezone(timezone.utc).isoformat()


def display_day(day: str) -> str:
    return date.fromisoformat(day).strftime("%d/%m/%Y")


def local_day(instant: str) -> str:
    return datetime.fromisoformat(instant).astimezone().date().isoformat()


class PetHealthService:
    def __init__(self, repository: PetHealthRepository, pets: PetRepository, files: HealthFileStore) -> None:
        self.repository = repository
        self.pets = pets
        self.files = files

    def _pet(self, pet_id: str) -> dict[str, Any]:
        pet = self.pets.get(pet_id)
        if not pet:
            raise EntityNotFoundError("Pet não encontrado.")
        return pet

    def _record(self, kind: str, pet_id: str, record_id: str, label: str) -> dict[str, Any]:
        self._pet(pet_id)
        record = self.repository.get(kind, pet_id, record_id)
        if not record:
            raise EntityNotFoundError(f"{label} não encontrado.")
        return record

    @staticmethod
    def _period(start: str | None, end: str | None) -> None:
        if start and end and end < start:
            raise InvalidDomainValueError("A data de fim não pode ser anterior à de início.")

    def list(self, kind: str, pet_id: str) -> list[dict[str, Any]]:
        self._pet(pet_id)
        records = self.repository.list(kind, pet_id)
        if kind == "exam":
            self._attach(pet_id, records, "exam_id")
        if kind == "treatment":
            self._expand_treatments(pet_id, records)
        return records

    def food_values(self, values: dict[str, Any]) -> dict[str, Any]:
        started_on = parse_day(values["started_on"], "a data de início")
        ended_on = parse_day(values.get("ended_on"), "a data de fim", required=False)
        self._period(started_on, ended_on)
        return {
            "name": values["name"].strip(), "brand": values.get("brand", "").strip(),
            "food_type": values["food_type"], "offered_amount": values.get("offered_amount", "").strip(),
            "started_on": started_on, "ended_on": ended_on, "notes": values.get("notes", "").strip(),
        }

    def create_food(self, pet_id: str, values: dict[str, Any], replace_current: bool) -> dict[str, Any]:
        self._pet(pet_id)
        prepared = self.food_values(values)
        if replace_current:
            self.repository.finish_open_food(pet_id, prepared["started_on"])
        return self.repository.create("food", pet_id, prepared)

    def update_food(self, pet_id: str, food_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._record("food", pet_id, food_id, "Alimento")
        return self.repository.update("food", pet_id, food_id, self.food_values(values)) or {}

    def create_weight(self, pet_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._pet(pet_id)
        weight = float(values["weight_kg"])
        if not 0 < weight <= MAX_WEIGHT_KG:
            raise InvalidDomainValueError("Informe um peso entre 0 e 150 kg.")
        return self.repository.create("weight", pet_id, {
            "measured_on": parse_day(values["measured_on"], "a data da pesagem"),
            "weight_kg": round(weight, 3), "notes": values.get("notes", "").strip(),
        })

    def exam_values(self, values: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": values["title"].strip(), "exam_type": values["exam_type"],
            "performed_on": parse_day(values.get("performed_on"), "a data do exame", required=False),
            "laboratory": values.get("laboratory", "").strip(), "professional": values.get("professional", "").strip(),
            "notes": values.get("notes", "").strip(), "transcription": values.get("transcription", "").strip(),
        }

    def create_exam(self, pet_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._pet(pet_id)
        exam = self.repository.create("exam", pet_id, self.exam_values(values))
        exam["attachments"] = []
        return exam

    def update_exam(self, pet_id: str, exam_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._record("exam", pet_id, exam_id, "Exame")
        exam = self.repository.update("exam", pet_id, exam_id, self.exam_values(values)) or {}
        self._attach(pet_id, [exam], "exam_id")
        return exam

    def treatment_values(self, values: dict[str, Any]) -> dict[str, Any]:
        started_on = parse_day(values["started_on"], "a data de início")
        ended_on = parse_day(values.get("ended_on"), "a data de encerramento", required=False)
        self._period(started_on, ended_on)
        return {
            "title": values["title"].strip(), "body_region": values.get("body_region", "").strip(),
            "description": values.get("description", "").strip(),
            "instructions": values.get("instructions", "").strip(),
            "started_on": started_on, "ended_on": ended_on,
        }

    def create_treatment(self, pet_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._pet(pet_id)
        treatment = self.repository.create("treatment", pet_id, self.treatment_values(values))
        self._expand_treatments(pet_id, [treatment])
        return treatment

    def update_treatment(self, pet_id: str, treatment_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._record("treatment", pet_id, treatment_id, "Tratamento")
        treatment = self.repository.update("treatment", pet_id, treatment_id, self.treatment_values(values)) or {}
        self._expand_treatments(pet_id, [treatment])
        return treatment

    def create_entry(self, pet_id: str, treatment_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._record("treatment", pet_id, treatment_id, "Tratamento")
        entry = self.repository.create_entry(
            treatment_id, parse_instant(values["observed_at"], "o momento observado"), values.get("notes", "").strip()
        )
        entry["attachments"] = []
        return entry

    def delete_entry(self, pet_id: str, treatment_id: str, entry_id: str) -> None:
        self._entry(pet_id, treatment_id, entry_id)
        self.files.remove(self.repository.delete_entry(entry_id))

    def _entry(self, pet_id: str, treatment_id: str, entry_id: str) -> dict[str, Any]:
        self._pet(pet_id)
        entry = self.repository.get_entry(pet_id, treatment_id, entry_id)
        if not entry:
            raise EntityNotFoundError("Registro de evolução não encontrado.")
        return entry

    def dose_values(self, pet_id: str, values: dict[str, Any]) -> dict[str, Any]:
        given_on = parse_day(values["given_on"], "a data de aplicação")
        next_due_on = parse_day(values.get("next_due_on"), "a próxima dose", required=False)
        if next_due_on and next_due_on < given_on:
            raise InvalidDomainValueError("A próxima dose não pode ser antes da aplicação.")
        treatment_id = values.get("treatment_id") or None
        if treatment_id:
            self._record("treatment", pet_id, treatment_id, "Tratamento")
        return {
            "kind": values["kind"], "name": values["name"].strip(), "dose": values.get("dose", "").strip(),
            "given_on": given_on, "next_due_on": next_due_on, "notes": values.get("notes", "").strip(),
            "treatment_id": treatment_id,
        }

    def create_dose(self, pet_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._pet(pet_id)
        return self.repository.create("dose", pet_id, self.dose_values(pet_id, values))

    def update_dose(self, pet_id: str, dose_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._record("dose", pet_id, dose_id, "Aplicação")
        return self.repository.update("dose", pet_id, dose_id, self.dose_values(pet_id, values)) or {}

    def delete(self, kind: str, pet_id: str, record_id: str) -> None:
        self._record(kind, pet_id, record_id, "Registro")
        self.files.remove(self.repository.delete(kind, pet_id, record_id))

    def add_attachment(self, pet_id: str, content: bytes, original_name: str, *,
                       exam_id: str | None = None, treatment_id: str | None = None,
                       entry_id: str | None = None) -> dict[str, Any]:
        if exam_id:
            self._record("exam", pet_id, exam_id, "Exame")
        else:
            self._entry(pet_id, treatment_id or "", entry_id or "")
        try:
            stored = self.files.save(content)
        except ValueError as error:
            raise InvalidDomainValueError(str(error)) from error
        if self.repository.find_attachment_by_hash(pet_id, stored.sha256, exam_id=exam_id, entry_id=entry_id):
            self.files.remove([stored.file_path, stored.thumbnail_path])
            raise EntityConflictError("Este arquivo já foi anexado aqui.")
        attachment = self.repository.create_attachment(pet_id, {
            "exam_id": exam_id, "entry_id": entry_id, "file_path": stored.file_path,
            "thumbnail_path": stored.thumbnail_path, "original_name": Path(original_name or "arquivo").name[:200],
            "media_type": stored.media_type, "size_bytes": stored.size_bytes, "sha256": stored.sha256,
        })
        return self._public_attachment(pet_id, attachment)

    def attachment_file(self, pet_id: str, attachment_id: str, thumbnail: bool) -> tuple[Path, str, str]:
        self._pet(pet_id)
        attachment = self.repository.get_attachment(pet_id, attachment_id)
        if not attachment:
            raise EntityNotFoundError("Arquivo não encontrado.")
        relative = attachment["thumbnail_path"] if thumbnail and attachment["thumbnail_path"] else attachment["file_path"]
        path = self.files.resolve(relative)
        if not path.is_file():
            raise EntityNotFoundError("O arquivo não está mais disponível no disco.")
        media_type = "image/jpeg" if relative == attachment["thumbnail_path"] else attachment["media_type"]
        return path, media_type, attachment["original_name"]

    def delete_attachment(self, pet_id: str, attachment_id: str) -> None:
        self._pet(pet_id)
        attachment = self.repository.get_attachment(pet_id, attachment_id)
        if not attachment:
            raise EntityNotFoundError("Arquivo não encontrado.")
        self.repository.delete_attachment(pet_id, attachment_id)
        self.files.remove([attachment["file_path"], attachment["thumbnail_path"]])

    def pet_files(self, pet_id: str) -> list[str | None]:
        return self.repository.pet_file_paths(pet_id)

    def remove_files(self, paths: list[str | None]) -> None:
        self.files.remove(paths)

    @staticmethod
    def _public_attachment(pet_id: str, attachment: dict[str, Any]) -> dict[str, Any]:
        url = f"/api/pets/{pet_id}/health/attachments/{attachment['id']}"
        return {
            "id": attachment["id"], "original_name": attachment["original_name"],
            "media_type": attachment["media_type"], "size_bytes": attachment["size_bytes"],
            "created_at": attachment["created_at"], "position": attachment["position"],
            "url": url, "thumbnail_url": f"{url}?thumbnail=1" if attachment["thumbnail_path"] else None,
        }

    def _attach(self, pet_id: str, records: list[dict[str, Any]], owner: str) -> None:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        ids = [record["id"] for record in records]
        attachments = (self.repository.list_attachments(pet_id, exam_ids=ids) if owner == "exam_id"
                       else self.repository.list_attachments(pet_id, entry_ids=ids))
        for attachment in attachments:
            grouped[attachment[owner]].append(self._public_attachment(pet_id, attachment))
        for record in records:
            record["attachments"] = grouped.get(record["id"], [])

    def _expand_treatments(self, pet_id: str, treatments: list[dict[str, Any]]) -> None:
        doses = self.repository.list("dose", pet_id)
        for treatment in treatments:
            entries = self.repository.list_entries(treatment["id"])
            self._attach(pet_id, entries, "entry_id")
            treatment["entries"] = entries
            treatment["doses"] = [dose for dose in doses if dose["treatment_id"] == treatment["id"]]

    def reminders(self, today: date | None = None, pet_id: str | None = None) -> list[dict[str, Any]]:
        today = today or local_today()
        reminders = []
        for dose in self.repository.due_doses((today + timedelta(days=REMINDER_WINDOW_DAYS)).isoformat()):
            if pet_id and dose["pet_id"] != pet_id:
                continue
            days = (date.fromisoformat(dose["next_due_on"]) - today).days
            reminders.append({**dose, "days_until_due": days, "overdue": days < 0})
        return reminders

    def summary(self, pet_id: str, today: date | None = None) -> dict[str, Any]:
        self._pet(pet_id)
        today_text = (today or local_today()).isoformat()
        food = [item for item in self.repository.list("food", pet_id)
                if item["started_on"] <= today_text and (not item["ended_on"] or item["ended_on"] >= today_text)]
        weights = self.repository.list("weight", pet_id)
        treatments = [item for item in self.repository.list("treatment", pet_id) if not item["ended_on"]]
        exams = self.repository.list("exam", pet_id)[:3]
        self._attach(pet_id, exams, "exam_id")
        return {
            "current_food": food,
            "latest_weight": weights[0] if weights else None,
            "previous_weight": weights[1] if len(weights) > 1 else None,
            "active_treatments": treatments,
            "recent_exams": exams,
            "reminders": self.reminders(today, pet_id),
        }

    def timeline(self, pet_id: str, start: str | None, end: str | None, today: date | None = None) -> dict[str, Any]:
        self._pet(pet_id)
        end_day = date.fromisoformat(parse_day(end, "o fim", required=False) or (today or local_today()).isoformat())
        start_day = date.fromisoformat(
            parse_day(start, "o início", required=False) or (end_day - timedelta(days=DEFAULT_TIMELINE_DAYS - 1)).isoformat()
        )
        if start_day > end_day or (end_day - start_day).days >= MAX_TIMELINE_DAYS:
            raise InvalidDomainValueError("Escolha um período de até um ano, com início antes do fim.")
        first, last = start_day.isoformat(), end_day.isoformat()
        items: list[dict[str, Any]] = []

        def add(day: str | None, kind: str, title: str, detail: str = "", record_id: str | None = None,
                at: str | None = None) -> None:
            if day and first <= day <= last:
                items.append({"date": day, "at": at, "kind": kind, "title": title, "detail": detail, "record_id": record_id})

        for food in self.repository.list("food", pet_id):
            label = " · ".join(part for part in (food["brand"], FOOD_TYPE_LABELS[food["food_type"]], food["offered_amount"]) if part)
            add(food["started_on"], "FOOD_START", f"Começou: {food['name']}", label, food["id"])
            add(food["ended_on"], "FOOD_END", f"Parou: {food['name']}", label, food["id"])
        for weight in self.repository.list("weight", pet_id):
            add(weight["measured_on"], "WEIGHT", f"Peso: {weight['weight_kg']:g} kg".replace(".", ","), weight["notes"], weight["id"])
        exams = self.repository.list("exam", pet_id)
        self._attach(pet_id, exams, "exam_id")
        for exam in exams:
            files = len(exam["attachments"])
            detail = " · ".join(part for part in (exam["laboratory"], f"{files} arquivo(s)" if files else "") if part)
            add(exam["performed_on"] or local_day(exam["created_at"]), "EXAM", exam["title"], detail, exam["id"])
        for dose in self.repository.list("dose", pet_id):
            detail = " · ".join(part for part in (dose["dose"], f"próxima: {display_day(dose['next_due_on'])}" if dose["next_due_on"] else "") if part)
            add(dose["given_on"], dose["kind"], f"{DOSE_KIND_LABELS[dose['kind']]}: {dose['name']}", detail, dose["id"])
        for treatment in self.repository.list("treatment", pet_id):
            add(treatment["started_on"], "TREATMENT_START", f"Início do tratamento: {treatment['title']}",
                treatment["body_region"], treatment["id"])
            add(treatment["ended_on"], "TREATMENT_END", f"Fim do tratamento: {treatment['title']}", "", treatment["id"])
            for entry in self.repository.list_entries(treatment["id"]):
                add(local_day(entry["observed_at"]), "TREATMENT_ENTRY", f"Evolução: {treatment['title']}",
                    entry["notes"], treatment["id"], entry["observed_at"])
        items += self._camera_days(pet_id, first, last)
        items.sort(key=lambda item: (item["date"], item["at"] or "", item["kind"] != "CAMERA_DAY"), reverse=True)
        return {"start": first, "end": last, "items": items}

    def _camera_days(self, pet_id: str, first: str, last: str) -> list[dict[str, Any]]:
        start, _ = utc_bounds_for_local_date(first)
        _, end = utc_bounds_for_local_date(last)
        days: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for event in self.repository.camera_events(pet_id, start, end):
            if event["decision"] in DISCARDED_DECISIONS:
                continue
            counts = days[local_day(event["started_at"])][event["zone_type"]]
            counts[0] += 1
            counts[1] += int(event["decision"] in CONFIRMED_DECISIONS)
        items = []
        for day, zones in days.items():
            counts = {zone: {"detected": values[0], "confirmed": values[1]} for zone, values in zones.items()}
            parts = [f"{values[0]}× {ZONE_LABELS.get(zone, zone.lower())}" for zone, values in sorted(zones.items())]
            items.append({"date": day, "at": None, "kind": "CAMERA_DAY", "title": "Rotina nas câmeras",
                          "detail": " · ".join(parts), "record_id": None, "counts": counts})
        return items
