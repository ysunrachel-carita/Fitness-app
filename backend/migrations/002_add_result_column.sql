-- Migration: Cleanup workout_sessions
-- Created: 2026-04-30
-- Description: Adds missing 'result' column and removes unused 'type' column

ALTER TABLE public.workout_sessions ADD COLUMN IF NOT EXISTS result TEXT;
ALTER TABLE public.workout_sessions DROP COLUMN IF EXISTS type;
