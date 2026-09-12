-- PROTACpilot Cognitive Memory — additive migration 0003
-- Dedupe / recurrence accounting reused from the Engram pattern.

ALTER TABLE memory_traces ADD COLUMN normalized_hash TEXT;
ALTER TABLE memory_traces ADD COLUMN duplicate_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE memory_traces ADD COLUMN last_seen_at TEXT;

CREATE INDEX IF NOT EXISTS idx_traces_normalized_hash ON memory_traces(normalized_hash, project_id, memory_type);
