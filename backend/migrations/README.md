# DB Migration Strategy

## Overview

This project uses a **versioned SQL migration** system. Every schema or structural data change is captured in a numbered `.sql` file under `migrations/`. A Python runner (`migrate.py`) tracks which migrations have been applied on each database using a `schema_migrations` table.

**No new dependencies** — uses `psycopg2` and `python-dotenv` already in your venv.

---

## ⚡ Quick Start (The Normal Loop)

```bash
# 1. Scaffold a new migration
python migrate.py new "add pace column to runs"

# 2. Edit the generated SQL file, then test locally
python migrate.py --target local --dry-run   # preview — no changes
python migrate.py --target local             # apply it

# 3. Verify
python migrate.py status

# 4. Push to Supabase (will auto-backup first, then prompt for confirmation)
python migrate.py --target remote
```

---

## 🔒 Safety First: Three Rules, All Automatic

### A. Backups (Safety Pins)

> Before running any migration on production, trigger a snapshot. Think of it as the safety pins on a squat rack.

**What `migrate.py` does:**
- `--target remote` **always** runs `pg_dump` first and saves it to `backups/` before touching anything
- `--target local` does it on request with `--backup`

```bash
python migrate.py --target local --backup    # optional backup before local migration
python migrate.py --target remote            # backup is AUTOMATIC, cannot be skipped
```

Backups are saved to `backend/backups/backup_<label>_<timestamp>.sql`. To restore:
```bash
psql $DATABASE_URL < backups/backup_remote_20260428-183000.sql
```

> **Requires `pg_dump`** — install Postgres CLI tools (`brew install libpq`) if you don't have it.

---

### B. Transactions (The Undo Button)

> Wrap your migration logic in a transaction. If the script fails halfway through, a transaction ensures none of the changes are saved.

**What `migrate.py` does:**
- Each `.sql` file runs inside a single `BEGIN` / `COMMIT` block managed by psycopg2
- If **any statement in the file fails**, the entire file is rolled back — your DB is left exactly as it was before
- The migration is only recorded in `schema_migrations` after a successful `COMMIT`

```
File runs → [BEGIN implicit]
  ├── statement 1 ✅
  ├── statement 2 ✅
  ├── statement 3 ❌ ERROR
  └── [ROLLBACK] ← DB unchanged, script stops
```

You don't need to add `BEGIN`/`COMMIT` to your `.sql` files — the runner strips them if you do.

---

### C. Staging Gate (Local First, Always)

> Never run a migration on your "real" app first. Run it on a local copy. If local breaks, just reset the container.

**What `migrate.py` does:**
- `--target remote` is **hard-blocked** if your local DB has any pending migrations
- Forces the order: **local → verify → remote**, every time

```
$ python migrate.py --target remote

🚫 Safety C — Staging Gate: BLOCKED
   Your local DB still has pending migrations:
     [0002] add pace column to runs

   Fix: run   python migrate.py --target local   first.
```

---

## Commands Reference

| Command | What it does |
|---|---|
| `python migrate.py status` | Show applied / pending on both DBs |
| `python migrate.py new "desc"` | Scaffold the next migration file |
| `python migrate.py --target local` | Apply pending → local |
| `python migrate.py --target local --backup` | Backup local first, then migrate |
| `python migrate.py --target local --dry-run` | Preview only, zero changes |
| `python migrate.py --target remote` | Backup + apply pending → Supabase |
| `python migrate.py --target both` | Local first, then remote (full safe path) |

---

## File Naming Convention

```
migrations/
  001_baseline_schema.sql       ← starting point (marks current schema)
  002_add_pace_to_runs.sql
  003_drop_legacy_tables.sql
  ...
```

- Must match pattern: `NNN_description.sql`
- Numbers determine execution order — never change them
- Use `python migrate.py new "..."` to auto-number

---

## .env Setup

```bash
# Local Postgres (Docker)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fitness_app

# Remote Supabase
RENDER_DATABASE_URL=postgresql://postgres.xxx:password@aws-...supabase.com:6543/postgres
```

---

## Writing Good Migration SQL

```sql
-- ✅ Good: idempotent guards
ALTER TABLE runs ADD COLUMN IF NOT EXISTS pace_per_km REAL;
CREATE INDEX IF NOT EXISTS idx_runs_date ON runs (date);
DROP TABLE IF EXISTS old_table;

-- ❌ Bad: will fail if column already exists (or doesn't)
ALTER TABLE runs ADD COLUMN pace_per_km REAL;
DROP TABLE old_table;
```

**Never edit an already-applied migration.** If you made a mistake, create a new one to fix it.
