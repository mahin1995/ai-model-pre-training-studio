CREATE TABLE model_config_revisions (
    project_id UUID PRIMARY KEY REFERENCES projects(id),
    last_revision INTEGER NOT NULL
);
CREATE TABLE model_configs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    revision INTEGER NOT NULL,
    name TEXT NOT NULL,
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id),
    tokenizer_run_id UUID NOT NULL REFERENCES tokenizer_runs(id),
    sequence_run_id UUID NOT NULL REFERENCES sequence_runs(id),
    configuration JSONB NOT NULL,
    source_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, revision)
);
