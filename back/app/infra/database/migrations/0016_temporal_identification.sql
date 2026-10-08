ALTER TABLE pet_identification_analyses ADD COLUMN observation_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE pet_identification_analyses ADD COLUMN identification_stage TEXT NOT NULL DEFAULT 'FINAL';
ALTER TABLE pet_identification_analyses ADD COLUMN initial_selected_pet_id TEXT REFERENCES pets(id) ON DELETE SET NULL;
ALTER TABLE pet_identification_analyses ADD COLUMN initial_decision TEXT;
ALTER TABLE pet_identification_analyses ADD COLUMN initial_confidence REAL;
