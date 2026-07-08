-- 005_lgpd.sql — Consentimento explícito + trilha de auditoria LGPD (PostgreSQL).

ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS consent TEXT NOT NULL DEFAULT 'pending'
    CHECK(consent IN ('pending','opted_in','opted_out'));
ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS consent_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS formulaos_lgpd_audit (
    id SERIAL PRIMARY KEY,
    actor_user_id INTEGER REFERENCES formulaos_users(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK(action IN ('export','delete','consent_in','consent_out')),
    subject_phone TEXT,
    details_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lgpd_audit_phone ON formulaos_lgpd_audit(subject_phone);
