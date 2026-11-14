CREATE TABLE tokenizer_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id),
    settings JSONB NOT NULL,
    source_snapshot JSONB NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','validating','training','encoding','packing','verifying','completed','failed','cancelled')),
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    worker_id UUID,
    heartbeat_at TIMESTAMPTZ,
    manifest JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX tokenizer_runs_project_idx ON tokenizer_runs(project_id, created_at DESC);
CREATE INDEX tokenizer_queue_idx ON tokenizer_runs(created_at) WHERE status='queued';
CREATE TABLE sequence_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id),
    tokenizer_run_id UUID NOT NULL REFERENCES tokenizer_runs(id),
    settings JSONB NOT NULL,
    source_snapshot JSONB NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','validating','training','encoding','packing','verifying','completed','failed','cancelled')),
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    worker_id UUID,
    heartbeat_at TIMESTAMPTZ,
    manifest JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX sequence_runs_project_idx ON sequence_runs(project_id, created_at DESC);
CREATE INDEX sequence_queue_idx ON sequence_runs(created_at) WHERE status='queued';
