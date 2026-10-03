CREATE TABLE pet_identification_analyses (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    species TEXT NOT NULL,
    capture_path TEXT,
    decision TEXT NOT NULL,
    selected_pet_id TEXT REFERENCES pets(id) ON DELETE SET NULL,
    selected_confidence REAL,
    minimum_similarity REAL NOT NULL,
    minimum_margin REAL NOT NULL,
    reviewed_pet_id TEXT REFERENCES pets(id) ON DELETE SET NULL,
    reviewed_at TEXT,
    was_correct INTEGER CHECK (was_correct IS NULL OR was_correct IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE pet_identification_scores (
    analysis_id TEXT NOT NULL REFERENCES pet_identification_analyses(id) ON DELETE CASCADE,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    confidence REAL NOT NULL,
    reference_count INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    PRIMARY KEY (analysis_id, pet_id)
);

CREATE TABLE pet_identification_calibrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    minimum_similarity REAL NOT NULL,
    minimum_margin REAL NOT NULL,
    interaction_count INTEGER NOT NULL,
    accuracy REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_pet_identification_analyses_created
    ON pet_identification_analyses(created_at DESC);
CREATE INDEX idx_pet_identification_scores_analysis
    ON pet_identification_scores(analysis_id, rank);
