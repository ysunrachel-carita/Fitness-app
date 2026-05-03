import psycopg2
from db import get_db

def clean_up_duplicate_exercises():
    """Collapse rows that share a canonical_key into a single row."""
    conn = get_db()
    try:
        # Check if duplicates exist
        dupes = conn.execute('''
            SELECT canonical_key, COUNT(*) as cnt 
            FROM exercises 
            WHERE canonical_key IS NOT NULL AND canonical_key != ''
            GROUP BY canonical_key 
            HAVING COUNT(*) > 1
            LIMIT 1
        ''').fetchone()
        
        if not dupes:
            return

        exercises = conn.execute(
            "SELECT id, name, canonical_key FROM exercises ORDER BY id"
        ).fetchall()
        
        # We need the canonical_exercise_key helper here too, or we import it
        from exercises import canonical_exercise_key

        grouped = {}
        for row in exercises:
            key = row['canonical_key'] or canonical_exercise_key(row['name'])
            if not key:
                continue
            grouped.setdefault(key, []).append(row)

        for key, rows in grouped.items():
            keep_id = rows[0]['id']
            if not rows[0]['canonical_key']:
                conn.execute(
                    "UPDATE exercises SET canonical_key = %s WHERE id = %s",
                    (key, keep_id),
                )
            if len(rows) < 2:
                continue

            duplicate_ids = [row['id'] for row in rows[1:]]
            placeholders = ','.join(['%s'] * len(duplicate_ids))
            conn.execute(
                f"UPDATE lift_sessions SET exercise_id = %s "
                f"WHERE exercise_id IN ({placeholders})",
                [keep_id, *duplicate_ids],
            )
            conn.execute(
                f"DELETE FROM exercises WHERE id IN ({placeholders})",
                duplicate_ids,
            )
        conn.commit()
    finally:
        conn.close()

def _migrate_exercise_canonical_key():
    """Backfill canonical_key column if missing."""
    conn = get_db()
    try:
        # Check column existence using Postgres information_schema
        check_col = conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'exercises' AND column_name = 'canonical_key'
        """).fetchone()
        
        if not check_col:
            conn.execute("ALTER TABLE exercises ADD COLUMN canonical_key TEXT")

        rows = conn.execute(
            "SELECT id, name FROM exercises "
            "WHERE canonical_key IS NULL OR canonical_key = ''"
        ).fetchall()
        
        from exercises import canonical_exercise_key
        for row in rows:
            key = canonical_exercise_key(row['name'])
            if key:
                conn.execute(
                    "UPDATE exercises SET canonical_key = %s WHERE id = %s",
                    (key, row['id']),
                )
        conn.commit()
    finally:
        conn.close()

def _ensure_canonical_key_unique_index():
    conn = get_db()
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_exercises_canonical_key "
            "ON exercises(canonical_key)"
        )
        conn.commit()
    finally:
        conn.close()

def migrate_legacy_lifts_to_sessions():
    # This was a SQLite-to-Postgres bridge. 
    # In the modern Postgres app, this is likely no longer needed, 
    # but we'll keep it here as a legacy script just in case.
    print("Skipping legacy SQLite migration - already on PostgreSQL.")
    pass
