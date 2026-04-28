-- Migration: Rename runs.duration_seconds to time_seconds
-- Created: 2026-04-28
--
-- The app code consistently uses `time_seconds` for runs, but Supabase
-- has the column named `duration_seconds` from the original schema.
-- This migration renames it to match.

ALTER TABLE runs RENAME COLUMN duration_seconds TO time_seconds;
