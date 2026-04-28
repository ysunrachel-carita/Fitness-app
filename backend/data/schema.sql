


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."exercise_sessions" (
    "id" integer NOT NULL,
    "user_id" integer NOT NULL,
    "exercise_id" integer NOT NULL,
    "notes" "text",
    "date" "text" NOT NULL,
    "created_at" "text" NOT NULL
);


ALTER TABLE "public"."exercise_sessions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."lift_sessions" (
    "id" integer NOT NULL,
    "user_id" integer NOT NULL,
    "exercise_id" integer NOT NULL,
    "notes" "text",
    "date" timestamp without time zone NOT NULL,
    "created_at" timestamp without time zone NOT NULL,
    "workout_session_id" integer
);


ALTER TABLE "public"."lift_sessions" OWNER TO "postgres";


COMMENT ON TABLE "public"."lift_sessions" IS 'Simple strength logging (log_lifts page)';



CREATE SEQUENCE IF NOT EXISTS "public"."exercise_sessions_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."exercise_sessions_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."exercise_sessions_id_seq" OWNED BY "public"."lift_sessions"."id";



CREATE SEQUENCE IF NOT EXISTS "public"."exercise_sessions_new_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."exercise_sessions_new_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."exercise_sessions_new_id_seq" OWNED BY "public"."exercise_sessions"."id";



CREATE TABLE IF NOT EXISTS "public"."exercises" (
    "id" integer NOT NULL,
    "name" "text" NOT NULL,
    "category" "text" NOT NULL,
    "canonical_key" "text"
);


ALTER TABLE "public"."exercises" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."exercises_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."exercises_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."exercises_id_seq" OWNED BY "public"."exercises"."id";



CREATE TABLE IF NOT EXISTS "public"."lift_sets" (
    "id" integer NOT NULL,
    "lift_session_id" integer NOT NULL,
    "weight_kg" real NOT NULL,
    "reps" integer NOT NULL,
    "order_index" integer NOT NULL,
    "rpe" real,
    "notes" "text"
);


ALTER TABLE "public"."lift_sets" OWNER TO "postgres";


COMMENT ON TABLE "public"."lift_sets" IS 'Sets for lift_sessions';



CREATE TABLE IF NOT EXISTS "public"."runs" (
    "id" integer NOT NULL,
    "user_id" integer NOT NULL,
    "distance_km" real NOT NULL,
    "duration_seconds" integer NOT NULL,
    "unit" "text" DEFAULT 'km'::"text" NOT NULL,
    "date" timestamp without time zone NOT NULL,
    "notes" "text",
    "created_at" timestamp without time zone NOT NULL,
    "run_type" "text" DEFAULT 'Run'::"text" NOT NULL
);


ALTER TABLE "public"."runs" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."runs_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."runs_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."runs_id_seq" OWNED BY "public"."runs"."id";



CREATE TABLE IF NOT EXISTS "public"."set_components" (
    "id" integer NOT NULL,
    "set_group_id" integer NOT NULL,
    "exercise_id" integer NOT NULL,
    "reps" integer,
    "weight_kg" real,
    "rpe" real,
    "notes" "text",
    "time_seconds" integer,
    "distance_meters" real,
    "calories" numeric,
    "height_inch" numeric,
    "target_type" "text" NOT NULL
);


ALTER TABLE "public"."set_components" OWNER TO "postgres";


COMMENT ON TABLE "public"."set_components" IS 'Individual exercise entries';



CREATE SEQUENCE IF NOT EXISTS "public"."set_components_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."set_components_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."set_components_id_seq" OWNED BY "public"."set_components"."id";



CREATE TABLE IF NOT EXISTS "public"."set_entries" (
    "id" integer NOT NULL,
    "session_id" integer NOT NULL,
    "weight_kg" real NOT NULL,
    "reps" integer NOT NULL,
    "order_index" integer NOT NULL,
    "rpe" real,
    "notes" "text"
);


ALTER TABLE "public"."set_entries" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."set_entries_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."set_entries_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."set_entries_id_seq" OWNED BY "public"."lift_sets"."id";



CREATE SEQUENCE IF NOT EXISTS "public"."set_entries_id_seq1"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."set_entries_id_seq1" OWNER TO "postgres";


ALTER SEQUENCE "public"."set_entries_id_seq1" OWNED BY "public"."set_entries"."id";



CREATE TABLE IF NOT EXISTS "public"."set_groups" (
    "id" integer NOT NULL,
    "workout_session_id" integer NOT NULL,
    "order_index" integer NOT NULL,
    "type" "text",
    "pattern_index" integer,
    "completed" boolean DEFAULT true,
    "shared_weight_kg" real,
    "rest_seconds" integer
);


ALTER TABLE "public"."set_groups" OWNER TO "postgres";


COMMENT ON TABLE "public"."set_groups" IS 'Rounds / supersets inside workout';



CREATE SEQUENCE IF NOT EXISTS "public"."set_groups_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."set_groups_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."set_groups_id_seq" OWNED BY "public"."set_groups"."id";



CREATE TABLE IF NOT EXISTS "public"."user_profiles" (
    "user_id" integer NOT NULL,
    "weight" real,
    "height" real,
    "preferred_unit" "text" DEFAULT 'kg'::"text",
    "goal" "text",
    "training_frequency" integer DEFAULT 3,
    "created_at" timestamp without time zone NOT NULL,
    "updated_at" timestamp without time zone NOT NULL,
    "photo_path" "text"
);


ALTER TABLE "public"."user_profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."users" (
    "id" integer NOT NULL,
    "username" "text" NOT NULL,
    "password_hash" "text" NOT NULL,
    "created_at" timestamp without time zone NOT NULL,
    "display_name" "text"
);


ALTER TABLE "public"."users" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."users_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."users_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."users_id_seq" OWNED BY "public"."users"."id";



CREATE TABLE IF NOT EXISTS "public"."wods" (
    "id" integer NOT NULL,
    "user_id" integer NOT NULL,
    "name" "text",
    "workout_text" "text" NOT NULL,
    "result" "text",
    "notes" "text",
    "date" timestamp without time zone NOT NULL,
    "wod_type" "text",
    "time_cap_minutes" integer,
    "emom_interval" integer,
    "emom_duration" integer
);


ALTER TABLE "public"."wods" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."wods_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."wods_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."wods_id_seq" OWNED BY "public"."wods"."id";



CREATE TABLE IF NOT EXISTS "public"."workout_sessions" (
    "id" integer NOT NULL,
    "user_id" integer NOT NULL,
    "date" timestamp without time zone NOT NULL,
    "title" "text",
    "notes" "text",
    "created_at" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    "context" "text",
    "time_cap_minutes" integer,
    "emom_interval" integer,
    "emom_duration" integer
);


ALTER TABLE "public"."workout_sessions" OWNER TO "postgres";


COMMENT ON TABLE "public"."workout_sessions" IS 'Workout logging (log_workout page)';



CREATE SEQUENCE IF NOT EXISTS "public"."workout_sessions_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."workout_sessions_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."workout_sessions_id_seq" OWNED BY "public"."workout_sessions"."id";



ALTER TABLE ONLY "public"."exercise_sessions" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."exercise_sessions_new_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."exercises" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."exercises_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."lift_sessions" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."exercise_sessions_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."lift_sets" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."set_entries_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."runs" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."runs_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."set_components" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."set_components_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."set_entries" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."set_entries_id_seq1"'::"regclass");



ALTER TABLE ONLY "public"."set_groups" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."set_groups_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."users" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."users_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."wods" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."wods_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."workout_sessions" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."workout_sessions_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."exercise_sessions"
    ADD CONSTRAINT "exercise_sessions_new_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."lift_sessions"
    ADD CONSTRAINT "exercise_sessions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."exercises"
    ADD CONSTRAINT "exercises_canonical_key_key" UNIQUE ("canonical_key");



ALTER TABLE ONLY "public"."exercises"
    ADD CONSTRAINT "exercises_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."exercises"
    ADD CONSTRAINT "exercises_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."runs"
    ADD CONSTRAINT "runs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."set_components"
    ADD CONSTRAINT "set_components_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."lift_sets"
    ADD CONSTRAINT "set_entries_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."set_entries"
    ADD CONSTRAINT "set_entries_pkey1" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."lift_sets"
    ADD CONSTRAINT "set_entries_session_id_order_index_key" UNIQUE ("lift_session_id", "order_index");



ALTER TABLE ONLY "public"."set_groups"
    ADD CONSTRAINT "set_groups_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_pkey" PRIMARY KEY ("user_id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_username_key" UNIQUE ("username");



ALTER TABLE ONLY "public"."wods"
    ADD CONSTRAINT "wods_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."workout_sessions"
    ADD CONSTRAINT "workout_sessions_pkey" PRIMARY KEY ("id");



CREATE UNIQUE INDEX "idx_exercises_canonical_key" ON "public"."exercises" USING "btree" ("canonical_key");



CREATE UNIQUE INDEX "idx_session_order" ON "public"."lift_sets" USING "btree" ("lift_session_id", "order_index");



CREATE INDEX "idx_sessions_user_id" ON "public"."lift_sessions" USING "btree" ("user_id");



CREATE INDEX "idx_set_entries_session_id" ON "public"."lift_sets" USING "btree" ("lift_session_id");



ALTER TABLE ONLY "public"."lift_sessions"
    ADD CONSTRAINT "exercise_sessions_exercise_id_fkey" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id");



ALTER TABLE ONLY "public"."exercise_sessions"
    ADD CONSTRAINT "exercise_sessions_new_exercise_id_fkey" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id");



ALTER TABLE ONLY "public"."exercise_sessions"
    ADD CONSTRAINT "exercise_sessions_new_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."lift_sessions"
    ADD CONSTRAINT "exercise_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."lift_sessions"
    ADD CONSTRAINT "exercise_sessions_workout_session_id_fkey" FOREIGN KEY ("workout_session_id") REFERENCES "public"."workout_sessions"("id");



ALTER TABLE ONLY "public"."runs"
    ADD CONSTRAINT "runs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."set_components"
    ADD CONSTRAINT "set_components_exercise_id_fkey" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id");



ALTER TABLE ONLY "public"."set_components"
    ADD CONSTRAINT "set_components_set_group_id_fkey" FOREIGN KEY ("set_group_id") REFERENCES "public"."set_groups"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."lift_sets"
    ADD CONSTRAINT "set_entries_session_id_fkey" FOREIGN KEY ("lift_session_id") REFERENCES "public"."lift_sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."set_groups"
    ADD CONSTRAINT "set_groups_workout_session_id_fkey" FOREIGN KEY ("workout_session_id") REFERENCES "public"."workout_sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."wods"
    ADD CONSTRAINT "wods_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."workout_sessions"
    ADD CONSTRAINT "workout_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE "public"."exercises" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."lift_sessions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."lift_sets" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."runs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."set_components" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."set_groups" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_profiles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."wods" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."workout_sessions" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON TABLE "public"."exercise_sessions" TO "anon";
GRANT ALL ON TABLE "public"."exercise_sessions" TO "authenticated";
GRANT ALL ON TABLE "public"."exercise_sessions" TO "service_role";



GRANT ALL ON TABLE "public"."lift_sessions" TO "anon";
GRANT ALL ON TABLE "public"."lift_sessions" TO "authenticated";
GRANT ALL ON TABLE "public"."lift_sessions" TO "service_role";



GRANT ALL ON SEQUENCE "public"."exercise_sessions_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."exercise_sessions_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."exercise_sessions_id_seq" TO "service_role";



GRANT ALL ON SEQUENCE "public"."exercise_sessions_new_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."exercise_sessions_new_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."exercise_sessions_new_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."exercises" TO "anon";
GRANT ALL ON TABLE "public"."exercises" TO "authenticated";
GRANT ALL ON TABLE "public"."exercises" TO "service_role";



GRANT ALL ON SEQUENCE "public"."exercises_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."exercises_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."exercises_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."lift_sets" TO "anon";
GRANT ALL ON TABLE "public"."lift_sets" TO "authenticated";
GRANT ALL ON TABLE "public"."lift_sets" TO "service_role";



GRANT ALL ON TABLE "public"."runs" TO "anon";
GRANT ALL ON TABLE "public"."runs" TO "authenticated";
GRANT ALL ON TABLE "public"."runs" TO "service_role";



GRANT ALL ON SEQUENCE "public"."runs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."runs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."runs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."set_components" TO "anon";
GRANT ALL ON TABLE "public"."set_components" TO "authenticated";
GRANT ALL ON TABLE "public"."set_components" TO "service_role";



GRANT ALL ON SEQUENCE "public"."set_components_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."set_components_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."set_components_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."set_entries" TO "anon";
GRANT ALL ON TABLE "public"."set_entries" TO "authenticated";
GRANT ALL ON TABLE "public"."set_entries" TO "service_role";



GRANT ALL ON SEQUENCE "public"."set_entries_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."set_entries_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."set_entries_id_seq" TO "service_role";



GRANT ALL ON SEQUENCE "public"."set_entries_id_seq1" TO "anon";
GRANT ALL ON SEQUENCE "public"."set_entries_id_seq1" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."set_entries_id_seq1" TO "service_role";



GRANT ALL ON TABLE "public"."set_groups" TO "anon";
GRANT ALL ON TABLE "public"."set_groups" TO "authenticated";
GRANT ALL ON TABLE "public"."set_groups" TO "service_role";



GRANT ALL ON SEQUENCE "public"."set_groups_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."set_groups_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."set_groups_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."user_profiles" TO "anon";
GRANT ALL ON TABLE "public"."user_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."user_profiles" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";



GRANT ALL ON SEQUENCE "public"."users_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."users_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."users_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."wods" TO "anon";
GRANT ALL ON TABLE "public"."wods" TO "authenticated";
GRANT ALL ON TABLE "public"."wods" TO "service_role";



GRANT ALL ON SEQUENCE "public"."wods_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."wods_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."wods_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."workout_sessions" TO "anon";
GRANT ALL ON TABLE "public"."workout_sessions" TO "authenticated";
GRANT ALL ON TABLE "public"."workout_sessions" TO "service_role";



GRANT ALL ON SEQUENCE "public"."workout_sessions_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."workout_sessions_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."workout_sessions_id_seq" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";







