-- 005_lgpd.sql — Consentimento explícito + trilha de auditoria LGPD.

ALTER TABLE conversations ADD COLUMN consent TEXT NOT NULL DEFAULT 'pending'
    CHECK(consent IN ('pending','opted_in','opted_out'));
ALTER TABLE conversations ADD COLUMN consent_at TEXT;

CREATE TABLE IF NOT EXISTS lgpd_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK(action IN ('export','delete','consent_in','consent_out')),
    subject_phone TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lgpd_audit_phone ON lgpd_audit(subject_phone);
