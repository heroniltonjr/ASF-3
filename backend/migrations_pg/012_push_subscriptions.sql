-- 012_push_subscriptions.sql — Tabela de inscrições para notificações Web Push (PostgreSQL).

CREATE TABLE IF NOT EXISTS formulaos_push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES formulaos_users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_push_subs_user ON formulaos_push_subscriptions(user_id);
