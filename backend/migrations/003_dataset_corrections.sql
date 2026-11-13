ALTER TABLE dataset_jobs ADD COLUMN correction_input JSONB;

CREATE TABLE dataset_correction_drafts (
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    base_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
    edits JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_id, base_version_id)
);
