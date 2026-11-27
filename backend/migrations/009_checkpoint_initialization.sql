ALTER TABLE smoke_runs
    ADD COLUMN initial_checkpoint_id UUID REFERENCES smoke_checkpoints(id),
    ADD CONSTRAINT smoke_initialized_run_has_parent
        CHECK (initial_checkpoint_id IS NULL OR parent_run_id IS NOT NULL);
