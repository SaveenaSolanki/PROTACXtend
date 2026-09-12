-- PROTACpilot Cognitive Memory — initial schema (Phase 1)
-- Local-first: SQLite + FTS5. Structured tables; JSON only for flexible extras.

PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────────────────
-- Projects & sessions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    created_at    TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    project_id    TEXT REFERENCES projects(id) ON DELETE SET NULL,
    goal          TEXT,
    status        TEXT NOT NULL DEFAULT 'open',
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    summary       TEXT,
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id, started_at DESC);

CREATE TABLE IF NOT EXISTS source_documents (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    doc_type      TEXT,
    doi           TEXT,
    pmid          TEXT,
    url           TEXT,
    path          TEXT,
    project_id    TEXT REFERENCES projects(id) ON DELETE SET NULL,
    metadata_json TEXT,
    created_at    TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Working memory (short-lived, TTL)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS working_memory (
    id             TEXT PRIMARY KEY,
    session_id     TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    project_id     TEXT REFERENCES projects(id) ON DELETE SET NULL,
    key            TEXT NOT NULL,
    content        TEXT NOT NULL,
    goal_relevance REAL NOT NULL DEFAULT 0.0,
    salience       REAL NOT NULL DEFAULT 0.0,
    created_at     TEXT NOT NULL,
    expires_at     TEXT,
    metadata_json  TEXT
);
CREATE INDEX IF NOT EXISTS idx_working_session ON working_memory(session_id, expires_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- Universal memory trace (shared base record)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memory_traces (
    id                    TEXT PRIMARY KEY,
    memory_type           TEXT NOT NULL,          -- episodic|semantic|procedural|prospective|negative|working
    title                 TEXT NOT NULL,
    content               TEXT NOT NULL,
    project_id            TEXT REFERENCES projects(id) ON DELETE SET NULL,
    session_id            TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    status                TEXT NOT NULL DEFAULT 'active',
    scope                 TEXT,                   -- human-readable scope
    scope_json            TEXT,                   -- machine-readable scope
    topic_key             TEXT,
    context_fingerprint   TEXT,

    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    last_accessed_at      TEXT,
    deleted_at            TEXT,

    salience              REAL NOT NULL DEFAULT 0.0,
    novelty               REAL NOT NULL DEFAULT 0.0,
    goal_relevance        REAL NOT NULL DEFAULT 0.0,
    surprise              REAL NOT NULL DEFAULT 0.0,
    evidence_strength     REAL NOT NULL DEFAULT 0.0,
    confidence            REAL NOT NULL DEFAULT 0.0,
    memory_strength       REAL NOT NULL DEFAULT 1.0,

    retrieval_count          INTEGER NOT NULL DEFAULT 0,
    successful_retrieval_count INTEGER NOT NULL DEFAULT 0,

    review_after          TEXT,
    supersedes_id         TEXT,
    version               INTEGER NOT NULL DEFAULT 1,

    source_type           TEXT,
    source_id             TEXT,

    encoding_score        REAL,
    encoding_breakdown_json TEXT,

    -- denormalised search fields (kept in sync by the application)
    search_context        TEXT,
    search_entities       TEXT,

    metadata_json         TEXT
);
CREATE INDEX IF NOT EXISTS idx_traces_type    ON memory_traces(memory_type, status);
CREATE INDEX IF NOT EXISTS idx_traces_project ON memory_traces(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_session ON memory_traces(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_topic   ON memory_traces(topic_key, project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_fp      ON memory_traces(context_fingerprint);
CREATE INDEX IF NOT EXISTS idx_traces_review  ON memory_traces(review_after);
CREATE INDEX IF NOT EXISTS idx_traces_deleted ON memory_traces(deleted_at);

-- FTS5 over memory_traces (external content). Queries additionally filter by
-- status/deleted_at, so soft-deleted and archived rows never surface.
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    title,
    content,
    scope,
    search_context,
    search_entities,
    content='memory_traces',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS memory_traces_ai AFTER INSERT ON memory_traces BEGIN
    INSERT INTO memory_fts(rowid, title, content, scope, search_context, search_entities)
    VALUES (new.rowid, new.title, new.content, new.scope, new.search_context, new.search_entities);
END;
CREATE TRIGGER IF NOT EXISTS memory_traces_ad AFTER DELETE ON memory_traces BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, title, content, scope, search_context, search_entities)
    VALUES ('delete', old.rowid, old.title, old.content, old.scope, old.search_context, old.search_entities);
END;
CREATE TRIGGER IF NOT EXISTS memory_traces_au AFTER UPDATE ON memory_traces BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, title, content, scope, search_context, search_entities)
    VALUES ('delete', old.rowid, old.title, old.content, old.scope, old.search_context, old.search_entities);
    INSERT INTO memory_fts(rowid, title, content, scope, search_context, search_entities)
    VALUES (new.rowid, new.title, new.content, new.scope, new.search_context, new.search_entities);
END;

-- ─────────────────────────────────────────────────────────────────────────────
-- Typed satellite memories
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS episodic_memories (
    trace_id              TEXT PRIMARY KEY REFERENCES memory_traces(id) ON DELETE CASCADE,
    event_type            TEXT NOT NULL,
    prediction_id         TEXT,
    outcome_id            TEXT,
    observed_json         TEXT,   -- raw observation (never rewritten)
    interpretation        TEXT,   -- separate from observation
    context_json          TEXT,
    source_json           TEXT,
    context_fingerprint   TEXT,
    is_negative           INTEGER NOT NULL DEFAULT 0,
    encoding_score        REAL,
    encoding_breakdown_json TEXT
);

CREATE TABLE IF NOT EXISTS semantic_memories (
    trace_id               TEXT PRIMARY KEY REFERENCES memory_traces(id) ON DELETE CASCADE,
    claim                  TEXT NOT NULL,
    topic_key              TEXT,
    scope_json             TEXT,
    confidence             REAL NOT NULL DEFAULT 0.0,
    n_supporting           INTEGER NOT NULL DEFAULT 0,
    n_contradicting        INTEGER NOT NULL DEFAULT 0,
    n_independent_sources  INTEGER NOT NULL DEFAULT 0,
    n_experimental         INTEGER NOT NULL DEFAULT 0,
    n_computational        INTEGER NOT NULL DEFAULT 0,
    n_literature           INTEGER NOT NULL DEFAULT 0,
    replication_count      INTEGER NOT NULL DEFAULT 0,
    source_quality         REAL NOT NULL DEFAULT 0.0,
    context_consistency    REAL NOT NULL DEFAULT 0.0,
    prediction_accuracy    REAL NOT NULL DEFAULT 0.0,
    version                INTEGER NOT NULL DEFAULT 1,
    supersedes_id          TEXT,
    consolidation_event_id TEXT,
    provisional            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS procedural_memories (
    trace_id       TEXT PRIMARY KEY REFERENCES memory_traces(id) ON DELETE CASCADE,
    workflow_name  TEXT NOT NULL,
    steps_json     TEXT NOT NULL,
    domain         TEXT,
    preconditions  TEXT,
    success_count  INTEGER NOT NULL DEFAULT 0,
    failure_count  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prospective_memories (
    trace_id          TEXT PRIMARY KEY REFERENCES memory_traces(id) ON DELETE CASCADE,
    task_id           TEXT,
    trigger           TEXT,
    due_at            TEXT,
    related_memory_id TEXT,
    status            TEXT NOT NULL DEFAULT 'open',
    priority          REAL NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_prospective_status ON prospective_memories(status, due_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- Entities & associative graph
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entities (
    id             TEXT PRIMARY KEY,
    entity_type    TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    canonical_id   TEXT,            -- UniProt / InChIKey / accession / ...
    properties_json TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type, canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_canonical_id ON entities(canonical_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_identity
    ON entities(entity_type, canonical_name, ifnull(canonical_id, ''));

CREATE TABLE IF NOT EXISTS entity_aliases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias      TEXT NOT NULL,
    alias_type TEXT,
    source     TEXT,
    UNIQUE(entity_id, alias)
);
CREATE INDEX IF NOT EXISTS idx_alias_alias ON entity_aliases(alias);

CREATE TABLE IF NOT EXISTS memory_entities (
    memory_id  TEXT NOT NULL REFERENCES memory_traces(id) ON DELETE CASCADE,
    entity_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'mentioned',
    confidence REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (memory_id, entity_id, role)
);
CREATE INDEX IF NOT EXISTS idx_mem_entities_entity ON memory_entities(entity_id);

CREATE TABLE IF NOT EXISTS memory_relations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source_memory_id  TEXT NOT NULL REFERENCES memory_traces(id) ON DELETE CASCADE,
    target_memory_id  TEXT NOT NULL REFERENCES memory_traces(id) ON DELETE CASCADE,
    relation_type     TEXT NOT NULL,
    confidence        REAL NOT NULL DEFAULT 0.5,
    created_by        TEXT,
    created_at        TEXT NOT NULL,
    rationale         TEXT,
    metadata_json     TEXT,
    UNIQUE(source_memory_id, target_memory_id, relation_type)
);
CREATE INDEX IF NOT EXISTS idx_rel_source ON memory_relations(source_memory_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_rel_target ON memory_relations(target_memory_id, relation_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- Evidence & provenance
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence_items (
    id             TEXT PRIMARY KEY,
    evidence_type  TEXT NOT NULL,
    title          TEXT,
    description    TEXT,
    source_type    TEXT,
    source_ref     TEXT,
    doi            TEXT,
    pmid           TEXT,
    url            TEXT,
    pdb            TEXT,
    accession      TEXT,
    file_path      TEXT,
    dataset_row_id TEXT,
    experiment_id  TEXT,
    notebook_id    TEXT,
    model_name     TEXT,
    model_version  TEXT,
    timestamp      TEXT,
    quality        REAL NOT NULL DEFAULT 0.5,
    payload_json   TEXT,
    project_id     TEXT REFERENCES projects(id) ON DELETE SET NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence_items(evidence_type);
CREATE INDEX IF NOT EXISTS idx_evidence_exp  ON evidence_items(experiment_id);

CREATE TABLE IF NOT EXISTS memory_evidence (
    memory_id        TEXT NOT NULL REFERENCES memory_traces(id) ON DELETE CASCADE,
    evidence_id      TEXT NOT NULL REFERENCES evidence_items(id) ON DELETE CASCADE,
    stance           TEXT NOT NULL DEFAULT 'supports',   -- supports|contradicts|context
    weight           REAL NOT NULL DEFAULT 1.0,
    independent_group TEXT,
    created_at       TEXT NOT NULL,
    PRIMARY KEY (memory_id, evidence_id, stance)
);
CREATE INDEX IF NOT EXISTS idx_mem_evidence_memory ON memory_evidence(memory_id, stance);

-- ─────────────────────────────────────────────────────────────────────────────
-- Predictions & outcomes (stored BEFORE the outcome exists)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prediction_events (
    id                   TEXT PRIMARY KEY,
    project_id           TEXT REFERENCES projects(id) ON DELETE SET NULL,
    session_id           TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    candidate_id         TEXT,
    prediction_type      TEXT NOT NULL,     -- numeric|classification|probabilistic
    metric               TEXT,
    predicted_value      REAL,
    predicted_class      TEXT,
    predicted_probability REAL,
    confidence           REAL NOT NULL DEFAULT 0.5,
    scale                REAL,
    context_json         TEXT,
    created_at           TEXT NOT NULL,
    resolved             INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pred_resolved ON prediction_events(resolved, created_at DESC);

CREATE TABLE IF NOT EXISTS outcome_events (
    id                   TEXT PRIMARY KEY,
    prediction_id        TEXT REFERENCES prediction_events(id) ON DELETE CASCADE,
    observed_value       REAL,
    observed_class       TEXT,
    observed_probability REAL,
    outcome_type         TEXT,
    evidence_id          TEXT REFERENCES evidence_items(id) ON DELETE SET NULL,
    prediction_error     REAL,
    error_method         TEXT,
    notes                TEXT,
    created_at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcome_pred ON outcome_events(prediction_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Access log, consolidation, reconsolidation, versions, events
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memory_access_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id       TEXT NOT NULL REFERENCES memory_traces(id) ON DELETE CASCADE,
    session_id      TEXT,
    query           TEXT,
    retrieved_at    TEXT NOT NULL,
    rank            INTEGER,
    score           REAL,
    components_json TEXT,
    was_useful      INTEGER,
    used_for        TEXT,
    feedback_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_access_memory ON memory_access_log(memory_id, retrieved_at DESC);

CREATE TABLE IF NOT EXISTS consolidation_events (
    id                TEXT PRIMARY KEY,
    created_at        TEXT NOT NULL,
    project_id        TEXT,
    session_id        TEXT,
    episode_ids_json  TEXT NOT NULL,
    topic_key         TEXT,
    semantic_memory_id TEXT,
    decision          TEXT NOT NULL,
    rationale         TEXT,
    config_json       TEXT
);

CREATE TABLE IF NOT EXISTS reconsolidation_events (
    id                 TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    semantic_memory_id TEXT NOT NULL,
    trigger            TEXT,
    new_evidence_json  TEXT,
    old_claim          TEXT,
    new_claim          TEXT,
    outcome            TEXT NOT NULL,
    confidence_before  REAL,
    confidence_after   REAL,
    rationale          TEXT,
    version_before     INTEGER,
    version_after      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reconsolidation_mem ON reconsolidation_events(semantic_memory_id, created_at DESC);

CREATE TABLE IF NOT EXISTS memory_versions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id    TEXT NOT NULL REFERENCES memory_traces(id) ON DELETE CASCADE,
    version      INTEGER NOT NULL,
    content      TEXT,
    confidence   REAL,
    status       TEXT,
    scope_json   TEXT,
    snapshot_json TEXT,
    created_at   TEXT NOT NULL,
    reason       TEXT,
    UNIQUE(memory_id, version)
);

CREATE TABLE IF NOT EXISTS memory_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id    TEXT,
    event_type   TEXT NOT NULL,
    detail_json  TEXT,
    session_id   TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_memory ON memory_events(memory_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON memory_events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS replay_events (
    id                 TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    trigger            TEXT,
    session_id         TEXT,
    project_id         TEXT,
    candidate_ids_json TEXT,
    findings_json      TEXT,
    status             TEXT NOT NULL DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS conflict_verdicts (
    id              TEXT PRIMARY KEY,
    memory_a        TEXT NOT NULL,
    memory_b        TEXT NOT NULL,
    verdict         TEXT NOT NULL,
    rationale       TEXT,
    context_diff_json TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(memory_a, memory_b, verdict)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Prospective tasks
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id                TEXT PRIMARY KEY,
    project_id        TEXT REFERENCES projects(id) ON DELETE SET NULL,
    session_id        TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    status            TEXT NOT NULL DEFAULT 'open',
    due_at            TEXT,
    related_memory_id TEXT,
    priority          REAL NOT NULL DEFAULT 0.0,
    created_at        TEXT NOT NULL,
    resolved_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, due_at);
