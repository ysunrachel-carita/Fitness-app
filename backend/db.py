import os
import psycopg2
from psycopg2.extras import DictCursor

class DBCursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()

    def close(self):
        self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)

class DBConnection:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        cur = self.conn.cursor(cursor_factory=DictCursor)
        try:
            cur.execute(query, list(params) if params else None)
        except Exception as e:
            # We'll keep the print for now since we haven't moved to formal logging yet
            print(f"❌ DATABASE ERROR: {e}")
            print(f"QUERY: {query}")
            self.conn.rollback()
            raise
        
        # Capture lastrowid if it was an INSERT with RETURNING id
        lastrowid = None
        if cur.description and query.strip().upper().startswith("INSERT"):
            cols = [d[0] for d in cur.description]
            if "id" in cols:
                try:
                    if cur.rowcount > 0:
                        row = cur.fetchone()
                        if row:
                            lastrowid = row[cols.index("id")]
                except:
                    pass
        
        self.conn.commit()
        return DBCursor(cur, lastrowid=lastrowid)

    def executemany(self, query, params_list):
        cur = self.conn.cursor(cursor_factory=DictCursor)
        try:
            cur.executemany(query, params_list)
        except Exception as e:
            print(f"❌ DATABASE ERROR (executemany): {e}")
            print(f"QUERY: {query}")
            self.conn.rollback()
            raise
        self.conn.commit()
        return DBCursor(cur)

    def commit(self):   self.conn.commit()
    def rollback(self): self.conn.rollback()

    def close(self):
        self.conn.close()

def get_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    conn = psycopg2.connect(database_url.strip())
    return DBConnection(conn)
def init_db():
    conn = get_db()
    
    # Tables for Users, Exercises, Lift Sessions, Lift Sets, Workout Sessions, Set Groups, Set Components, Runs, Wins
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            category TEXT,
            canonical_key TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lift_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            exercise_id INTEGER REFERENCES exercises(id),
            date DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lift_sets (
            id SERIAL PRIMARY KEY,
            lift_session_id INTEGER REFERENCES lift_sessions(id) ON DELETE CASCADE,
            weight_kg FLOAT NOT NULL,
            reps INTEGER NOT NULL,
            order_index INTEGER,
            rpe FLOAT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            date DATE NOT NULL,
            title TEXT,
            notes TEXT,
            context TEXT,
            time_cap_minutes INTEGER,
            emom_interval INTEGER,
            emom_duration INTEGER,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS set_groups (
            id SERIAL PRIMARY KEY,
            workout_session_id INTEGER REFERENCES workout_sessions(id) ON DELETE CASCADE,
            title TEXT,
            type TEXT,
            shared_weight_kg FLOAT,
            order_index INTEGER,
            completed BOOLEAN DEFAULT TRUE,
            rest_seconds INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS set_components (
            id SERIAL PRIMARY KEY,
            set_group_id INTEGER REFERENCES set_groups(id) ON DELETE CASCADE,
            exercise_id INTEGER REFERENCES exercises(id),
            reps INTEGER,
            weight_kg FLOAT,
            weight_percent FLOAT,
            sets INTEGER,
            calories INTEGER,
            distance_km FLOAT,
            distance_meters FLOAT,
            time_seconds INTEGER,
            shuttle_distance FLOAT,
            target_type TEXT,
            height_inch FLOAT,
            rpe FLOAT,
            notes TEXT,
            order_index INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            distance_km FLOAT NOT NULL,
            time_seconds INTEGER NOT NULL,
            unit TEXT DEFAULT 'km',
            run_type TEXT DEFAULT 'Run',
            date DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS wins (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            content TEXT NOT NULL,
            date DATE NOT NULL,
            category TEXT DEFAULT 'PR',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE REFERENCES users(id),
            display_name TEXT,
            photo_path TEXT,
            weight_display FLOAT,
            weight_unit TEXT DEFAULT 'kg',
            height_display FLOAT,
            height_unit TEXT DEFAULT 'cm',
            preferred_unit TEXT DEFAULT 'kg',
            goal TEXT,
            training_frequency INTEGER DEFAULT 3,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Auto-migration: Ensure all newly added columns exist on the remote database
    # Dictionary of table_name -> { column_name: column_type }
    expected_columns = {
        'set_components': {
            'order_index': 'INTEGER',
            'sets': 'INTEGER',
            'calories': 'INTEGER',
            'distance_km': 'FLOAT',
            'distance_meters': 'FLOAT',
            'time_seconds': 'INTEGER',
            'shuttle_distance': 'FLOAT',
            'target_type': 'TEXT',
            'height_inch': 'FLOAT'
        },
        'lift_sets': {
            'order_index': 'INTEGER'
        },
        'wins': {
            'content': 'TEXT',
            'category': 'TEXT',
            'date': 'DATE'
        }
    }

    # Auto-migration: Handle known column renames first to preserve data
    renames = {
        'wins': {'entry': 'content'}
    }
    for table, col_renames in renames.items():
        existing = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'").fetchall()
        existing_col_names = [row[0] for row in existing]
        for old_name, new_name in col_renames.items():
            if old_name in existing_col_names and new_name not in existing_col_names:
                try:
                    conn.execute(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")
                    print(f"✅ Migrated: Renamed {old_name} to {new_name} in {table}")
                except Exception as e:
                    print(f"⚠️ Could not rename {old_name} to {new_name} in {table}: {e}")

    for table, cols in expected_columns.items():
        # Get existing columns for this table
        existing = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'").fetchall()
        existing_col_names = [row[0] for row in existing]
        
        for col_name, col_type in cols.items():
            if col_name not in existing_col_names:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Migrated: Added {col_name} to {table}")
                except Exception as e:
                    print(f"⚠️ Could not add {col_name} to {table}: {e}")

    conn.close()
