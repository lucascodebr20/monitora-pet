ALTER TABLE human_reviews ADD COLUMN automatic INTEGER NOT NULL DEFAULT 0;

CREATE INDEX idx_reviews_automatic ON human_reviews(automatic);
