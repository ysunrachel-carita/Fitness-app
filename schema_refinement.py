import sqlite3

def refine_schema(db_path="fitness.db"):
    conn = sqlite3.connect(db_path)
    
    # set_groups changes
    try:
        conn.execute("ALTER TABLE set_groups ADD COLUMN pattern_index INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE set_groups ADD COLUMN completed BOOLEAN DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE set_groups ADD COLUMN shared_weight_kg REAL")
    except sqlite3.OperationalError:
        pass

    # set_components changes
    try:
        conn.execute("ALTER TABLE set_components ADD COLUMN load_type TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE set_components ADD COLUMN load_value REAL")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("Schema refined successfully.")

if __name__ == "__main__":
    refine_schema()
