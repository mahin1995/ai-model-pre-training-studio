CREATE TABLE prompt_sets (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    last_version INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    language TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE prompt_set_versions (
    id UUID PRIMARY KEY,
    prompt_set_id UUID NOT NULL REFERENCES prompt_sets(id),
    version INTEGER NOT NULL,
    document JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(prompt_set_id,version)
);
CREATE TABLE inference_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    kind TEXT NOT NULL CHECK(kind IN ('generation','evaluation')),
    training_run_id UUID NOT NULL REFERENCES smoke_runs(id),
    prompt_set_version_id UUID REFERENCES prompt_set_versions(id),
    external_dataset_id UUID REFERENCES datasets(id),
    external_dataset_version_id UUID REFERENCES dataset_versions(id),
    settings JSONB NOT NULL,
    source_snapshot JSONB NOT NULL,
    runtime_snapshot JSONB NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','validating','loading','running','verifying','completed','failed','cancelled')),
    metrics JSONB NOT NULL DEFAULT '{}',
    manifest JSONB,
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    worker_id UUID,
    heartbeat_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE TABLE inference_checkpoint_refs (
    inference_run_id UUID NOT NULL REFERENCES inference_runs(id),
    checkpoint_id UUID NOT NULL REFERENCES smoke_checkpoints(id),
    PRIMARY KEY(inference_run_id,checkpoint_id)
);
CREATE TABLE inference_annotations (
    run_id UUID NOT NULL REFERENCES inference_runs(id),
    checkpoint_id UUID NOT NULL REFERENCES smoke_checkpoints(id),
    prompt_index INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(run_id,checkpoint_id,prompt_index)
);
CREATE INDEX inference_runs_project_idx ON inference_runs(project_id,kind,created_at DESC);
CREATE INDEX inference_runs_queue_idx ON inference_runs(created_at) WHERE status='queued';
