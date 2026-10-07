ALTER TABLE cameras ADD COLUMN source_kind TEXT NOT NULL DEFAULT 'NETWORK'
    CHECK (source_kind IN ('NETWORK', 'MANUAL'));

ALTER TABLE cameras ADD COLUMN recording_support TEXT NOT NULL DEFAULT 'UNKNOWN'
    CHECK (recording_support IN ('UNKNOWN', 'NONE', 'ONVIF_REPLAY'));

ALTER TABLE cameras ADD COLUMN clock_offset_seconds REAL NOT NULL DEFAULT 0;

ALTER TABLE cameras ADD COLUMN last_synced_at TEXT;
