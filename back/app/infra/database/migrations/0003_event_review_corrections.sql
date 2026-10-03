ALTER TABLE events ADD COLUMN corrected_zone_type TEXT
    CHECK (corrected_zone_type IS NULL OR corrected_zone_type IN ('WATER', 'FOOD', 'LITTER'));

CREATE INDEX idx_events_corrected_zone_type ON events(corrected_zone_type, started_at DESC);
