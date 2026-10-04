ALTER TABLE pet_identification_analyses
ADD COLUMN method TEXT NOT NULL DEFAULT 'appearance-histogram-v1';

ALTER TABLE pet_identification_calibrations
ADD COLUMN method TEXT NOT NULL DEFAULT 'appearance-histogram-v1';

CREATE INDEX idx_pet_identification_analyses_method_reviewed
ON pet_identification_analyses(method, reviewed_at);

CREATE INDEX idx_pet_identification_calibrations_method
ON pet_identification_calibrations(method, id DESC);
