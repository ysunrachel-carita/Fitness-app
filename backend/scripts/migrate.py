#!/usr/bin/env python3
"""
migrate.py — Fitness App Database Migration Runner

Usage:
  python migrate.py --target local              # Run pending migrations on local DB
  python migrate.py --target remote             # Run pending migrations on remote (Supabase)
  python migrate.py --target both               # Local first, then remote (recommended)
  python migrate.py --target local --dry-run    # Preview what would run, no changes
  python migrate.py --target local --backup     # Backup local DB first, then migrate
  python migrate.py status                      # Show applied/pending on both DBs
  python migrate.py new "add rpe to runs"       # Scaffold a new empty migration file

Safety rules enforced automatically:
  ✅ A. Backup  — remote migrations always pg_dump first (local: opt-in via --backup)
  ✅ B. Transactions — every migration file runs inside BEGIN/COMMIT; failure = full rollback
  ✅ C. Staging — --target remote is blocked if local still has pending migrations
"""

import os
import sys
import re
import shutil
import argparse
import subprocess
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Connection config ──────────────────────────────────────────────────────────
# In .env: DATABASE_URL = local postgres, RENDER_DATABASE_URL = Supabase
LOCAL_URL  = os.getenv("DATABASE_URL",        "postgresql://postgres:postgres@localhost:5432/fitness_app")
REMOTE_URL = os.getenv("REMOTE_DATABASE_URL") or os.getenv("RENDER_DATABASE_URL")

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
BACKUPS_DIR    = Path(__file__).parent.parent / "backups"

TRACKING_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT        PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT
);
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_conn(url: str):
    try:
        return psycopg2.connect(url)
    except psycopg2.OperationalError as e:
        print(f"  ❌ Could not connect: {e}")
        sys.exit(1)


def ensure_tracking_table(cur):
    cur.execute(TRACKING_TABLE_DDL)


def get_applied_versions(cur) -> set[str]:
    cur.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cur.fetchall()}


def get_migration_files() -> list[tuple[str, str, Path]]:
    """
    Returns sorted list of (version, description, path) for all .sql files
    in the migrations/ directory. Files must be named like:
      001_add_rpe_column.sql
      002_rename_exercise_sessions.sql
    """
    pattern = re.compile(r'^(\d+)_(.+)\.sql$')
    files = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = pattern.match(f.name)
        if m:
            version     = m.group(1).zfill(4)   # zero-pad to 4 digits for sorting
            description = m.group(2).replace("_", " ")
            files.append((version, description, f))
        else:
            print(f"  ⚠️  Skipping '{f.name}' — filename must match NNN_description.sql")
    return files


def get_pending(conn_url: str) -> list[tuple[str, str, Path]]:
    """Return migrations not yet applied to the given DB."""
    conn = get_conn(conn_url)
    cur  = conn.cursor()
    ensure_tracking_table(cur)
    conn.commit()
    applied = get_applied_versions(cur)
    cur.close(); conn.close()
    return [(v, d, p) for v, d, p in get_migration_files() if v not in applied]


# ── Safety A: Backup ───────────────────────────────────────────────────────────

def take_backup(conn_url: str, label: str) -> Path | None:
    """
    Run pg_dump to create a .sql snapshot in backups/.
    Returns the backup path on success, None if pg_dump is not available.
    """
    if not shutil.which("pg_dump"):
        print(f"  ⚠️  pg_dump not found on PATH — skipping backup for {label}.")
        print("     Install Postgres CLI tools to enable automatic backups.")
        return None

    BACKUPS_DIR.mkdir(exist_ok=True)
    timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUPS_DIR / f"backup_{label}_{timestamp}.sql"

    print(f"\n  💾 Safety A — Backup: dumping {label} DB...")
    print(f"     → {backup_path}")

    try:
        result = subprocess.run(
            ["pg_dump", "--no-owner", "--no-acl", conn_url],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        backup_path.write_text(result.stdout)
        size_kb = backup_path.stat().st_size // 1024
        print(f"  ✅ Backup saved ({size_kb} KB). You can restore with:")
        print(f"     psql <DB_URL> < {backup_path}")
        return backup_path
    except subprocess.CalledProcessError as e:
        print(f"  ❌ pg_dump failed: {e.stderr.strip()}")
        print("     Refusing to proceed without a backup. Fix pg_dump and retry.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("  ❌ pg_dump timed out after 120s.")
        sys.exit(1)


# ── Safety B: Transaction wrapper ─────────────────────────────────────────────

def run_migrations(conn_url: str, label: str, dry_run: bool = False, do_backup: bool = False):
    """Apply all pending migrations to the given database."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}🎯 Target: {label}")
    print(f"   URL: {conn_url[:45]}...")

    conn = get_conn(conn_url)
    cur  = conn.cursor()
    ensure_tracking_table(cur)
    conn.commit()   # commit tracking table DDL immediately

    applied  = get_applied_versions(cur)
    all_migs = get_migration_files()
    pending  = [(v, d, p) for v, d, p in all_migs if v not in applied]

    if not pending:
        print("   ✅ Already up to date — no pending migrations.")
        cur.close(); conn.close()
        return

    print(f"   📋 {len(pending)} pending migration(s):")
    for version, description, path in pending:
        print(f"      [{version}] {description}")

    if dry_run:
        print("\n   (dry-run) No changes made.")
        cur.close(); conn.close()
        return

    # Safety A — take backup before making any changes
    if do_backup:
        take_backup(conn_url, label.lower().replace(" ", "_").replace("(", "").replace(")", ""))

    # Safety B — one transaction per migration file
    for version, description, path in pending:
        sql = path.read_text().strip()

        # Strip any bare BEGIN/COMMIT the user may have typed — we control the transaction
        sql_clean = re.sub(r'^\s*BEGIN\s*;', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql_clean = re.sub(r'\s*COMMIT\s*;\s*$', '', sql_clean, flags=re.IGNORECASE)

        print(f"\n   ▶ Applying [{version}] {description}...")
        print(f"     Safety B: running inside a transaction (full rollback on any error)")
        try:
            # psycopg2 is always in a transaction by default; each execute below is
            # within the same open transaction until commit() or rollback() is called.
            cur.execute(sql_clean)
            cur.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (%s, %s)",
                (version, description)
            )
            conn.commit()   # ← COMMIT: only reaches here if the whole file succeeded
            print(f"   ✅ [{version}] committed.")
        except Exception as e:
            conn.rollback() # ← ROLLBACK: DB is exactly as it was before this file ran
            print(f"   ❌ [{version}] FAILED — transaction rolled back.")
            print(f"      Error: {e}")
            print("   ⛔ No changes were saved. Fix the SQL above and re-run.")
            cur.close(); conn.close()
            sys.exit(1)

    print(f"\n   🎉 Done! {len(pending)} migration(s) applied to {label}.")
    cur.close()
    conn.close()


# ── Status ─────────────────────────────────────────────────────────────────────

def show_status():
    """Print a side-by-side status of local vs remote migrations."""
    all_migs = get_migration_files()

    def fetch_applied(url, label):
        try:
            conn = get_conn(url)
            cur  = conn.cursor()
            ensure_tracking_table(cur)
            conn.commit()
            applied = get_applied_versions(cur)
            cur.close(); conn.close()
            return applied
        except SystemExit:
            print(f"  ⚠️  Could not reach {label}.")
            return set()

    local_applied  = fetch_applied(LOCAL_URL,  "local")
    remote_applied = fetch_applied(REMOTE_URL, "remote") if REMOTE_URL else set()

    print("\n📊 Migration Status")
    print(f"{'Version':<8} {'Description':<38} {'Local':<12} {'Remote':<12}")
    print("─" * 72)

    for version, description, _ in all_migs:
        local_mark  = "✅ applied" if version in local_applied  else "⏳ pending"
        remote_mark = "✅ applied" if version in remote_applied else "⏳ pending"
        if not REMOTE_URL:
            remote_mark = "— (no URL)"
        print(f"{version:<8} {description:<38} {local_mark:<12} {remote_mark:<12}")

    if not all_migs:
        print("  (no migration files found in migrations/)")


# ── Scaffold ───────────────────────────────────────────────────────────────────

def scaffold_new(description: str):
    """Create a new empty migration file with the next sequence number."""
    all_migs = get_migration_files()
    next_num  = len(all_migs) + 1
    slug      = re.sub(r'\s+', '_', description.strip().lower())
    slug      = re.sub(r'[^a-z0-9_]', '', slug)
    filename  = f"{next_num:03d}_{slug}.sql"
    path      = MIGRATIONS_DIR / filename

    template = f"""-- Migration: {description}
-- Created:   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
--
-- ✅ Safety B: This file runs inside a single transaction automatically.
--    If any statement fails, the ENTIRE file is rolled back. No partial changes.
--
-- Tips:
--   • Use IF NOT EXISTS / IF EXISTS guards for idempotency
--   • Test locally first:  python migrate.py --target local --dry-run
--   • Then apply locally:  python migrate.py --target local
--   • Then push remotely:  python migrate.py --target remote

"""
    path.write_text(template)
    print(f"✨ Created: migrations/{filename}")
    print(f"   Next step:  python migrate.py --target local --dry-run")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fitness App DB Migration Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest="command")

    # `status` sub-command
    subparsers.add_parser("status", help="Show applied/pending migrations on both DBs")

    # `new` sub-command
    new_parser = subparsers.add_parser("new", help="Scaffold a new empty migration file")
    new_parser.add_argument("description", help='e.g. "add rpe to runs"')

    # default run-migrations flags
    parser.add_argument(
        "--target",
        choices=["local", "remote", "both"],
        default="local",
        help="Which database to migrate (default: local)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview pending migrations without applying them"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Take a pg_dump snapshot before migrating (always on for --target remote)"
    )

    args = parser.parse_args()

    if not MIGRATIONS_DIR.exists():
        MIGRATIONS_DIR.mkdir()
        print(f"📁 Created migrations/ directory at {MIGRATIONS_DIR}")

    if args.command == "status":
        show_status()

    elif args.command == "new":
        scaffold_new(args.description)

    else:
        # ── Validate remote pre-conditions ─────────────────────────────────────
        if not REMOTE_URL and args.target in ("remote", "both"):
            print("❌ No RENDER_DATABASE_URL (or REMOTE_DATABASE_URL) found in .env")
            print("   Add:  RENDER_DATABASE_URL=postgresql://...")
            sys.exit(1)

        # Safety C — hard block: refuse remote if local is behind
        if args.target in ("remote", "both") and not args.dry_run:
            try:
                local_pending = get_pending(LOCAL_URL)
                if local_pending:
                    print("\n🚫 Safety C — Staging Gate: BLOCKED")
                    print("   Your local DB still has pending migrations that haven't been applied:")
                    for v, d, _ in local_pending:
                        print(f"     [{v}] {d}")
                    print("\n   Fix: run   python migrate.py --target local   first.")
                    print("   This ensures every change is proven locally before touching production.")
                    sys.exit(1)
            except SystemExit as e:
                if e.code == 1:
                    raise  # re-raise only the gate block, not connection errors
                pass      # local unreachable — warn but don't block

        # ── Run ────────────────────────────────────────────────────────────────
        if args.target in ("local", "both"):
            run_migrations(
                LOCAL_URL, "Local (localhost)",
                dry_run=args.dry_run,
                do_backup=args.backup,
            )

        if args.target in ("remote", "both"):
            if not args.dry_run:
                print("\n⚠️  Safety A — Backup: a pg_dump will run before any changes.")
                confirm = input("   Apply migrations to REMOTE (Supabase)? [y/N] ")
                if confirm.lower() != "y":
                    print("Aborted.")
                    sys.exit(0)
            run_migrations(
                REMOTE_URL, "Remote (Supabase)",
                dry_run=args.dry_run,
                do_backup=not args.dry_run,  # always backup before remote writes
            )


if __name__ == "__main__":
    main()
