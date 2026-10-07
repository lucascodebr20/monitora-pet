CREATE TABLE event_highlights (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_event_highlights_created ON event_highlights(created_at DESC);
