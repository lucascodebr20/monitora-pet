ALTER TABLE pet_identification_calibrations ADD COLUMN species TEXT NOT NULL DEFAULT 'CAT'
    CHECK (species IN ('CAT', 'DOG'));

CREATE INDEX idx_pet_identification_calibrations_species
    ON pet_identification_calibrations(method, species, id DESC);
