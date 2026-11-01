CREATE TABLE projects (
    id UUID PRIMARY KEY,
    document JSONB NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX projects_updated_at_idx ON projects (updated_at DESC, id);
