-- Мастер-таблица товаров. PK = code.
CREATE TABLE IF NOT EXISTS products (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    application TEXT,
    price       REAL,
    source_file TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- Сырые описания из источников. UNIQUE(code, source) — один источник = одна запись.
CREATE TABLE IF NOT EXISTS source_descriptions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL,
    source          TEXT NOT NULL,
    raw_description TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(code, source),
    FOREIGN KEY (code) REFERENCES products(code)
);

-- AI-сгенерированные тексты. UNIQUE(code, text_type) — один тип = одна запись.
CREATE TABLE IF NOT EXISTS generated_texts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    code              TEXT NOT NULL,
    text_type         TEXT NOT NULL DEFAULT 'newdescriptiontop',
    content           TEXT NOT NULL,
    model_id          TEXT DEFAULT 'claude-sonnet-4-20250514',
    has_services_block INTEGER DEFAULT 0,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(code, text_type),
    FOREIGN KEY (code) REFERENCES products(code)
);

CREATE TRIGGER IF NOT EXISTS trg_products_updated
    AFTER UPDATE ON products
BEGIN
    UPDATE products SET updated_at = datetime('now') WHERE code = NEW.code;
END;

CREATE TRIGGER IF NOT EXISTS trg_source_desc_updated
    AFTER UPDATE ON source_descriptions
BEGIN
    UPDATE source_descriptions SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_generated_texts_updated
    AFTER UPDATE ON generated_texts
BEGIN
    UPDATE generated_texts SET updated_at = datetime('now') WHERE id = NEW.id;
END;
