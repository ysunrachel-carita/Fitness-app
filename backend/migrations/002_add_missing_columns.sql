-- Migration: Add missing columns to users and workout tables
-- Created: 2026-04-28
-- Target: Remote Supabase (Postgres)
--
-- This migration ensures the production database has all the columns
-- required for the latest dashboard and workout features.

-- 1. Add display_name to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;

-- 2. Add missing columns to workout_sessions
ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS type TEXT;
ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS context TEXT;
ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS time_cap_minutes INTEGER;
ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS emom_interval INTEGER;
ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS emom_duration INTEGER;

-- 3. Add missing columns to set_groups
ALTER TABLE set_groups ADD COLUMN IF NOT EXISTS type TEXT;
ALTER TABLE set_groups ADD COLUMN IF NOT EXISTS rest_seconds INTEGER;

-- 4. Add missing columns to set_components
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS target_type TEXT NOT NULL DEFAULT 'reps';
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS time_seconds INTEGER;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS distance_meters REAL;
ALTER TABLE set_components ADD COLUMN IF NOT EXISTS calories REAL;
