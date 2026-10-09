from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infra.ai.identification_calibration import search_thresholds  # noqa: E402
from app.infra.ai.pet_identifier import PetIdentifier  # noqa: E402
from app.infra.media.pet_image_store import PetImageStore  # noqa: E402


def production(db: sqlite3.Connection, since: str) -> None:
    rows = db.execute(
        """SELECT a.method, a.decision, a.selected_pet_id, r.pet_id,
                  (SELECT pet_id FROM pet_identification_scores s WHERE s.analysis_id = a.id AND s.rank = 1)
           FROM pet_identification_analyses a
           JOIN human_reviews r ON r.event_id = a.event_id
           JOIN events e ON e.id = a.event_id
           WHERE r.decision = 'CONFIRMED' AND r.automatic = 0 AND r.pet_id IS NOT NULL AND e.started_at >= ?""",
        (since,),
    ).fetchall()
    by_method: dict[str, list[tuple]] = defaultdict(list)
    for method, *rest in rows:
        by_method[method].append(tuple(rest))
    print(f"Producao (eventos desde {since or 'o inicio'}, revisao humana CONFIRMED)")
    for method, items in sorted(by_method.items()):
        matched = [item for item in items if item[0] == "MATCHED"]
        correct = sum(item[1] == item[2] for item in matched)
        top1 = sum(item[3] == item[2] for item in items)
        print(f"  {method:26} revisados {len(items):4}  acerto efetivo {correct}/{len(items)} = "
              f"{correct / len(items):6.1%}  erros {len(matched) - correct}  "
              f"nao identificados {len(items) - len(matched)}")
        print(f"  {'':26} top-1 {top1 / len(items):6.1%}  "
              f"precisao MATCHED {correct}/{len(matched)} = {correct / max(1, len(matched)):6.1%}  "
              f"cobertura {len(matched) / len(items):5.0%}")
        missed = Counter(item[0] for item in items if item[0] != "MATCHED")
        if missed:
            print(f"  {'':26} nao identificados por motivo: "
                  + ", ".join(f"{decision} {count}" for decision, count in missed.most_common()))


class TimeBoundPets:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.pets = [dict(zip(("id", "photo_path", "species"), row))
                     for row in db.execute("SELECT id, photo_path, species FROM pets")]
        self.references = db.execute("SELECT pet_id, event_id, image_path, created_at FROM pet_reference_images").fetchall()
        self.cutoff = self.exclude = ""

    def list_by_species(self, species: str) -> list[dict]:
        return [pet for pet in self.pets if pet["species"] == species]

    def list_reference_images(self, pet_id: str) -> list[dict]:
        return [{"image_path": path} for owner, event_id, path, created_at in self.references
                if owner == pet_id and created_at < self.cutoff and event_id != self.exclude]


def replay(db: sqlite3.Connection, data: Path, since: str) -> None:
    pets = TimeBoundPets(db)
    identifier = PetIdentifier(pets, PetImageStore(data, data / "pets"), None,
                               data / "models" / "mobilenetv2_embedding.onnx")
    events = db.execute(
        """SELECT e.id, e.started_at, e.pet_capture_path, e.detected_species, r.pet_id
           FROM events e JOIN human_reviews r ON r.event_id = e.id
           WHERE r.decision = 'CONFIRMED' AND r.automatic = 0 AND r.pet_id IS NOT NULL
             AND e.pet_capture_path IS NOT NULL AND e.started_at >= ?
           ORDER BY e.started_at""",
        (since,),
    ).fetchall()
    samples = []
    for event_id, started_at, capture, species, pet_id in events:
        pets.cutoff, pets.exclude = started_at, event_id
        scores = identifier.analyze(capture, species).scores
        if len(scores) >= 2:
            best, second = scores[0], scores[1]
            samples.append((best["confidence"], best["confidence"] - second["confidence"], best["pet_id"] == pet_id))
    if not samples:
        print("Replay: nenhum evento avaliavel")
        return
    print(f"\nReplay de {identifier.METHOD} na captura salva ({len(samples)} eventos)")
    print(f"  top-1 {sum(item[2] for item in samples) / len(samples):.1%}")
    for target in (0.95, 0.98):
        thresholds = search_thresholds(samples, target)
        if thresholds is None:
            print(f"  alvo {target:.0%}: inalcancavel")
            continue
        accepted = [item for item in samples if item[0] >= thresholds[0] and item[1] >= thresholds[1]]
        print(f"  alvo {target:.0%}: limiares {thresholds}  cobertura {len(accepted) / len(samples):.0%}")
    default = [item for item in samples
               if item[0] >= identifier.MINIMUM_SIMILARITY and item[1] >= identifier.MINIMUM_MARGIN]
    if default:
        print(f"  limiares padrao: cobertura {len(default) / len(samples):.0%}  "
              f"precisao {sum(item[2] for item in default) / len(default):.1%}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mede o acerto da identificacao de pets contra as revisoes humanas.")
    parser.add_argument("data", type=Path, help="pasta com mp.sqlite3 (ou monitorapet.sqlite3), pets/ e models/")
    parser.add_argument("--since", default="", help="so eventos a partir desta data ISO (ex.: 2026-10-08)")
    parser.add_argument("--no-replay", action="store_true", help="so a medida de producao")
    args = parser.parse_args()
    database = next(path for name in ("mp.sqlite3", "mp_snapshot.sqlite3", "monitorapet.sqlite3")
                    if (path := args.data / name).is_file())
    db = sqlite3.connect(database)
    production(db, args.since)
    if not args.no_replay:
        replay(db, args.data, args.since)


if __name__ == "__main__":
    main()
