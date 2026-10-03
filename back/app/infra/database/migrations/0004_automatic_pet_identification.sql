ALTER TABLE events ADD COLUMN automatically_identified_pet_id TEXT REFERENCES pets(id) ON DELETE SET NULL;
ALTER TABLE events ADD COLUMN pet_identification_confidence REAL CHECK (
    pet_identification_confidence IS NULL OR
    (pet_identification_confidence >= 0 AND pet_identification_confidence <= 1)
);
ALTER TABLE events ADD COLUMN pet_identification_method TEXT;

CREATE INDEX idx_events_automatic_pet
    ON events(automatically_identified_pet_id, started_at DESC);
