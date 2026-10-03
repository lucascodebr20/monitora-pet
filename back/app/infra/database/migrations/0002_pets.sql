CREATE TABLE pets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    species TEXT NOT NULL CHECK (species IN ('CAT', 'DOG')),
    description TEXT NOT NULL DEFAULT '',
    photo_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE pet_reference_images (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    event_id TEXT REFERENCES events(id) ON DELETE SET NULL,
    image_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

ALTER TABLE events ADD COLUMN pet_id TEXT REFERENCES pets(id) ON DELETE SET NULL;
ALTER TABLE events ADD COLUMN detected_species TEXT NOT NULL DEFAULT 'CAT' CHECK (detected_species IN ('CAT', 'DOG'));
ALTER TABLE events ADD COLUMN pet_capture_path TEXT;
ALTER TABLE human_reviews ADD COLUMN pet_id TEXT REFERENCES pets(id) ON DELETE SET NULL;

CREATE INDEX idx_events_pet ON events(pet_id, started_at DESC);
CREATE INDEX idx_pet_reference_images_pet ON pet_reference_images(pet_id, created_at DESC);
