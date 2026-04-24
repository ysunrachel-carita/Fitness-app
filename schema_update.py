import sqlite3

def update_schema(db_path="fitness.db"):
    conn = sqlite3.connect(db_path)
    
    # 1. Create workout_sessions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            type TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # 2. Create set_groups
    conn.execute("""
        CREATE TABLE IF NOT EXISTS set_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_session_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            type TEXT,
            FOREIGN KEY (workout_session_id) REFERENCES workout_sessions(id) ON DELETE CASCADE
        )
    """)
    
    # 3. Create set_components
    conn.execute("""
        CREATE TABLE IF NOT EXISTS set_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_group_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            reps INTEGER,
            weight_kg REAL,
            rpe REAL,
            notes TEXT,
            duration_seconds INTEGER,
            distance_meters REAL,
            FOREIGN KEY (set_group_id) REFERENCES set_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        )
    """)
    
    # 4. Alter exercise_sessions
    try:
        conn.execute("ALTER TABLE exercise_sessions ADD COLUMN workout_session_id INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    conn.commit()
    conn.close()
    print("Schema updated successfully.")

if __name__ == "__main__":
    update_schema()
