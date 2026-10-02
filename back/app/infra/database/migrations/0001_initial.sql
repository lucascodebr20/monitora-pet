CREATE TABLE cameras (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ip TEXT NOT NULL UNIQUE,
    manufacturer TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    onvif_port INTEGER NOT NULL DEFAULT 8899,
    rtsp_url TEXT,
    credential_ref TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE zones (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    polygon TEXT NOT NULL,
    minimum_presence_seconds REAL NOT NULL DEFAULT 3,
    absence_tolerance_seconds REAL NOT NULL DEFAULT 1,
    cooldown_seconds REAL NOT NULL DEFAULT 10,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL REFERENCES cameras(id),
    zone_id TEXT NOT NULL REFERENCES zones(id),
    started_at TEXT NOT NULL,
    confirmed_at TEXT,
    ended_at TEXT,
    duration_seconds REAL NOT NULL DEFAULT 0,
    confidence REAL,
    activity TEXT NOT NULL DEFAULT 'UNCERTAIN',
    snapshot_path TEXT,
    clip_path TEXT,
    end_reason TEXT,
    engine_version TEXT NOT NULL DEFAULT '1',
    created_at TEXT NOT NULL
);

CREATE TABLE human_reviews (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    corrected_activity TEXT,
    cat_name TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE notice_rules (
    id TEXT PRIMARY KEY,
    zone_type TEXT NOT NULL,
    max_hours_without_event REAL NOT NULL,
    repeat_hours REAL NOT NULL DEFAULT 4,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_events_started_at ON events(started_at DESC);
CREATE INDEX idx_events_camera ON events(camera_id);
CREATE INDEX idx_events_zone ON events(zone_id);
CREATE INDEX idx_reviews_event ON human_reviews(event_id, created_at DESC);
