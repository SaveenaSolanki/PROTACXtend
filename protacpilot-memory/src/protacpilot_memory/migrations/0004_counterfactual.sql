-- PROTACpilot Cognitive Memory — additive migration 0004
-- Counterfactual analyses are separate reasoning artifacts; they never rewrite
-- observations or evidence.

CREATE TABLE IF NOT EXISTS counterfactual_analyses (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    project_id    TEXT,
    session_id    TEXT,
    prediction_id TEXT,
    outcome_id    TEXT,
    episode_id    TEXT,
    question      TEXT,
    analysis_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_counterfactual_pred ON counterfactual_analyses(prediction_id);
