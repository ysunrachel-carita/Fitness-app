-- Migration: Fix workout schema and add missing columns
-- Created: 2026-05-11
-- Description: Adds title to set_groups and syncs set_components columns

-- 1. Update set_groups
ALTER TABLE set_groups ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE set_groups ADD COLUMN IF NOT EXISTS rest_seconds INTEGER;

-- 2. Update set_components
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS weight_percent FLOAT;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS distance_meters FLOAT;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS order_index INTEGER;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS sets INTEGER;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS shuttle_distance FLOAT;

-- Ensure target_type is present (it should be from baseline)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='set_components' AND column_name='target_type') THEN
        ALTER TABLE set_components ADD COLUMN target_type TEXT;
    END IF;
END $$;
