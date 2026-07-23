-- Migration 018: Temporizador de reativação automática do SDR por inatividade humana

ALTER TABLE stores ADD COLUMN sdr_auto_reactivate_minutes INTEGER DEFAULT 30;
ALTER TABLE conversations ADD COLUMN last_human_activity_at TIMESTAMP;
