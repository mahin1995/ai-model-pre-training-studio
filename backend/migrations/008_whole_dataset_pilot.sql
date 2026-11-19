ALTER TABLE model_configs ADD COLUMN training_kind TEXT NOT NULL DEFAULT 'smoke'
    CHECK (training_kind IN ('smoke', 'pilot'));
ALTER TABLE smoke_runs ADD COLUMN training_kind TEXT NOT NULL DEFAULT 'smoke'
    CHECK (training_kind IN ('smoke', 'pilot'));
CREATE INDEX training_runs_kind_idx ON smoke_runs(project_id, training_kind, created_at DESC);
