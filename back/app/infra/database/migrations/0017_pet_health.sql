CREATE TABLE pet_food_periods (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    food_type TEXT NOT NULL CHECK (food_type IN ('DRY', 'WET', 'OTHER')),
    offered_amount TEXT NOT NULL DEFAULT '',
    started_on TEXT NOT NULL,
    ended_on TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE pet_weights (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    measured_on TEXT NOT NULL,
    weight_kg REAL NOT NULL CHECK (weight_kg > 0),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE pet_exams (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    exam_type TEXT NOT NULL CHECK (exam_type IN ('BLOOD', 'URINE', 'FECES', 'IMAGING', 'PRESCRIPTION', 'REPORT', 'OTHER')),
    performed_on TEXT,
    laboratory TEXT NOT NULL DEFAULT '',
    professional TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    transcription TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE pet_treatments (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body_region TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL DEFAULT '',
    started_on TEXT NOT NULL,
    ended_on TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE pet_treatment_entries (
    id TEXT PRIMARY KEY,
    treatment_id TEXT NOT NULL REFERENCES pet_treatments(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE pet_doses (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    treatment_id TEXT REFERENCES pet_treatments(id) ON DELETE SET NULL,
    kind TEXT NOT NULL CHECK (kind IN ('VACCINE', 'MEDICATION', 'ANTIPARASITIC')),
    name TEXT NOT NULL,
    dose TEXT NOT NULL DEFAULT '',
    given_on TEXT NOT NULL,
    next_due_on TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE pet_health_attachments (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    exam_id TEXT REFERENCES pet_exams(id) ON DELETE CASCADE,
    entry_id TEXT REFERENCES pet_treatment_entries(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    file_path TEXT NOT NULL,
    thumbnail_path TEXT,
    original_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK ((exam_id IS NULL) <> (entry_id IS NULL))
);

CREATE INDEX idx_pet_food_periods_pet ON pet_food_periods(pet_id, started_on DESC);
CREATE INDEX idx_pet_weights_pet ON pet_weights(pet_id, measured_on DESC);
CREATE INDEX idx_pet_exams_pet ON pet_exams(pet_id, performed_on DESC);
CREATE INDEX idx_pet_treatments_pet ON pet_treatments(pet_id, started_on DESC);
CREATE INDEX idx_pet_treatment_entries_treatment ON pet_treatment_entries(treatment_id, observed_at DESC);
CREATE INDEX idx_pet_doses_pet ON pet_doses(pet_id, given_on DESC);
CREATE INDEX idx_pet_doses_due ON pet_doses(next_due_on);
CREATE INDEX idx_pet_health_attachments_exam ON pet_health_attachments(exam_id, position);
CREATE INDEX idx_pet_health_attachments_entry ON pet_health_attachments(entry_id, position);
CREATE INDEX idx_pet_health_attachments_pet ON pet_health_attachments(pet_id);
