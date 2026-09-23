-- PROTACpilot Cognitive Memory — additive migration 0002
-- Demonstrates the safe additive-migration pattern (confidence features).
-- Guarded by the migration runner's table_info check in db.py.

ALTER TABLE semantic_memories ADD COLUMN confidence_features_json TEXT;
ALTER TABLE memory_traces ADD COLUMN calibration_error REAL;
