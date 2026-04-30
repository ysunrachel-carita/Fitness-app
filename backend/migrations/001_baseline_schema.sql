-- Migration: Baseline Schema
-- Created: 2026-04-29
-- Description: Unified schema for the Fitness App (Postgres-only)
-- Derived from: Supabase schema dump and app.py requirements

-- 1. Tables

CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    username text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    display_name text,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.exercises (
    id SERIAL PRIMARY KEY,
    name text UNIQUE NOT NULL,
    category text NOT NULL,
    canonical_key text UNIQUE
);

CREATE TABLE IF NOT EXISTS public.workout_sessions (
    id SERIAL PRIMARY KEY,
    user_id integer NOT NULL REFERENCES public.users(id),
    date timestamp without time zone NOT NULL,
    title text,
    notes text,
    context text,
    time_cap_minutes integer,
    emom_interval integer,
    emom_duration integer,
    result text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.lift_sessions (
    id SERIAL PRIMARY KEY,
    user_id integer NOT NULL REFERENCES public.users(id),
    exercise_id integer NOT NULL REFERENCES public.exercises(id),
    workout_session_id integer REFERENCES public.workout_sessions(id) ON DELETE CASCADE,
    notes text,
    date timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE public.lift_sessions IS 'Simple strength logging (log_lifts page)';

CREATE TABLE IF NOT EXISTS public.lift_sets (
    id SERIAL PRIMARY KEY,
    lift_session_id integer NOT NULL REFERENCES public.lift_sessions(id) ON DELETE CASCADE,
    weight_kg real NOT NULL,
    reps integer NOT NULL,
    order_index integer NOT NULL,
    rpe real,
    notes text,
    UNIQUE (lift_session_id, order_index)
);
COMMENT ON TABLE public.lift_sets IS 'Sets for lift_sessions';

CREATE TABLE IF NOT EXISTS public.set_groups (
    id SERIAL PRIMARY KEY,
    workout_session_id integer NOT NULL REFERENCES public.workout_sessions(id) ON DELETE CASCADE,
    order_index integer NOT NULL,
    type text,
    pattern_index integer,
    completed boolean DEFAULT true,
    shared_weight_kg real,
    rest_seconds integer
);
COMMENT ON TABLE public.set_groups IS 'Rounds / supersets inside workout';

CREATE TABLE IF NOT EXISTS public.set_components (
    id SERIAL PRIMARY KEY,
    set_group_id integer NOT NULL REFERENCES public.set_groups(id) ON DELETE CASCADE,
    exercise_id integer NOT NULL REFERENCES public.exercises(id),
    reps integer,
    weight_kg real,
    rpe real,
    notes text,
    time_seconds integer,
    distance_meters real,
    calories numeric,
    height_inch numeric,
    target_type text NOT NULL
);
COMMENT ON TABLE public.set_components IS 'Individual exercise entries';

CREATE TABLE IF NOT EXISTS public.runs (
    id SERIAL PRIMARY KEY,
    user_id integer NOT NULL REFERENCES public.users(id),
    distance_km real NOT NULL,
    time_seconds integer NOT NULL,
    unit text DEFAULT 'km'::text NOT NULL,
    run_type text DEFAULT 'Run'::text NOT NULL,
    date timestamp without time zone NOT NULL,
    notes text,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.wods (
    id SERIAL PRIMARY KEY,
    user_id integer NOT NULL REFERENCES public.users(id),
    name text,
    workout_text text NOT NULL,
    result text,
    notes text,
    date timestamp without time zone NOT NULL,
    wod_type text,
    time_cap_minutes integer,
    emom_interval integer,
    emom_duration integer
);

CREATE TABLE IF NOT EXISTS public.user_profiles (
    user_id integer PRIMARY KEY REFERENCES public.users(id),
    weight real,
    height real,
    preferred_unit text DEFAULT 'kg'::text,
    goal text,
    training_frequency integer DEFAULT 3,
    photo_path text,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.wins (
    id SERIAL PRIMARY KEY,
    user_id integer NOT NULL REFERENCES public.users(id),
    category TEXT NOT NULL,
    entry TEXT NOT NULL,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    description text
);

-- 2. Indexes

CREATE INDEX IF NOT EXISTS idx_lift_sets_lift_session_id ON public.lift_sets USING btree (lift_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.lift_sessions USING btree (user_id);
CREATE INDEX IF NOT EXISTS idx_set_entries_session_id ON public.lift_sets USING btree (lift_session_id);
