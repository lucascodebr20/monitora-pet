CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE watched_folders (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_scanned_at TEXT,
    UNIQUE (camera_id, path)
);

ALTER TABLE recordings ADD COLUMN time_source TEXT NOT NULL DEFAULT 'PROTOCOL'
    CHECK (time_source IN ('PROTOCOL', 'FILENAME', 'MODIFIED', 'MANUAL'));
