CREATE TABLE event_highlights (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    note TEXT,
    created_at TEXT NOT NULL
);
