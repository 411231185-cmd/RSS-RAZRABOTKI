CREATE TABLE IF NOT EXISTS validation_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    text_type   TEXT NOT NULL DEFAULT 'newdescriptiontop',
    is_valid    INTEGER NOT NULL DEFAULT 0,
    errors      TEXT,
    checked_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(code, text_type)
);

CREATE INDEX IF NOT EXISTS idx_validation_invalid
    ON validation_results(is_valid) WHERE is_valid = 0;