CREATE TABLE monitoring_sessions (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_monitoring_sessions_camera ON monitoring_sessions(camera_id, started_at);

CREATE TABLE recordings (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    origin TEXT NOT NULL CHECK (origin IN ('FOLDER', 'CAMERA')),
    path TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'DONE', 'FAILED', 'SKIPPED')),
    processed_seconds REAL NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    UNIQUE (camera_id, fingerprint)
);

CREATE INDEX idx_recordings_status ON recordings(status, started_at);
CREATE INDEX idx_recordings_camera ON recordings(camera_id, started_at);

ALTER TABLE events ADD COLUMN source TEXT NOT NULL DEFAULT 'LIVE'
    CHECK (source IN ('LIVE', 'RECORDING'));

ALTER TABLE events ADD COLUMN recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL;

CREATE INDEX idx_events_recording ON events(recording_id);
