CREATE TABLE datasets (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    metadata JSONB NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    record_count INTEGER NOT NULL CHECK (record_count >= 0),
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    empty_count INTEGER NOT NULL CHECK (empty_count >= 0),
    files JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX datasets_project_idx ON datasets(project_id, created_at DESC);
CREATE TABLE dataset_jobs (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    settings JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','cleaning','deduplicating','splitting','completed','failed','cancelled')),
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    worker_id UUID,
    heartbeat_at TIMESTAMPTZ,
    error TEXT,
    result_version_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX dataset_one_active_job ON dataset_jobs(dataset_id)
    WHERE status IN ('queued','cleaning','deduplicating','splitting');
CREATE INDEX dataset_jobs_queue_idx ON dataset_jobs(created_at) WHERE status = 'queued';
CREATE TABLE dataset_versions (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    job_id UUID NOT NULL UNIQUE REFERENCES dataset_jobs(id),
    version INTEGER NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(dataset_id, version)
);
ALTER TABLE dataset_jobs ADD CONSTRAINT dataset_job_result_fk
    FOREIGN KEY (result_version_id) REFERENCES dataset_versions(id);
