-- Migration: Add missing columns to sync local schema with remote database
-- Date: 2026-05-03

-- 1. Gracefully rename 'entry' to 'content' in the 'wins' table to preserve data
DO $$
BEGIN
  IF EXISTS(SELECT 1
    FROM information_schema.columns
    WHERE table_name='wins' and column_name='entry')
  THEN
      ALTER TABLE wins RENAME COLUMN entry TO content;
  END IF;
END $$;

-- 2. Add missing columns to set_components
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS order_index INTEGER;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS sets INTEGER;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS calories INTEGER;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS distance_km FLOAT;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS distance_meters FLOAT;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS time_seconds INTEGER;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS shuttle_distance FLOAT;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS target_type TEXT;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS height_inch FLOAT;

-- 3. Add missing columns to lift_sets
ALTER TABLE lift_sets ADD COLUMN IF NOT EXISTS order_index INTEGER;

-- 4. Add missing columns to wins (skip if they already exist)
ALTER TABLE wins ADD COLUMN IF NOT EXISTS content TEXT;
ALTER TABLE wins ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'PR';
ALTER TABLE wins ADD COLUMN IF NOT EXISTS date DATE;
