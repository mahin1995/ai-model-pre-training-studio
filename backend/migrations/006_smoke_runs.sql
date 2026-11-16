CREATE TABLE smoke_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    model_config_id UUID NOT NULL REFERENCES model_configs(id),
    parent_run_id UUID REFERENCES smoke_runs(id),
    resume_checkpoint_id UUID,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','validating','initializing','training','verifying','completed','failed','cancelled')),
    storage_key TEXT NOT NULL UNIQUE,
    configuration JSONB NOT NULL,
    source_snapshot JSONB NOT NULL,
    runtime_snapshot JSONB NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}',
    manifest JSONB,
    verdict TEXT CHECK(verdict IN ('passed','needs-attention','failed')),
    error TEXT,
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    worker_id UUID,
    heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE TABLE smoke_checkpoints (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES smoke_runs(id),
    step INTEGER NOT NULL CHECK(step > 0),
    storage_key TEXT NOT NULL UNIQUE,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(run_id,step)
);
ALTER TABLE smoke_runs ADD CONSTRAINT smoke_resume_checkpoint_fk FOREIGN KEY(resume_checkpoint_id) REFERENCES smoke_checkpoints(id);
CREATE INDEX smoke_runs_project_idx ON smoke_runs(project_id, created_at DESC);
CREATE INDEX smoke_runs_queue_idx ON smoke_runs(created_at) WHERE status='queued';
