-- Migration: Baseline — current schema already exists
-- Created:   2026-04-28
--
-- This migration is intentionally empty.
-- It marks the current schema state as the starting point for the
-- migration system. All tables (users, exercises, lift_sessions,
-- lift_sets, workout_sessions, set_groups, set_components, runs,
-- wods, user_profiles) already exist in both local and remote DBs.
--
-- Future schema changes should be added as new migration files:
--   python migrate.py new "your description here"

SELECT 1; -- no-op, ensures valid SQL
