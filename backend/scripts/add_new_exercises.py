import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def add_exercises():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not found.")
        return
        
    exercises = [
        ("dumbbell box step over", "CrossFit"),
        ("tall snatch", "CrossFit"),
        ("snatch balance", "CrossFit")
    ]
    
    print(f"🚀 Adding exercises to: {url.split('@')[-1]}")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        
        # Fix sequence out of sync issue
        print("  - Fixing ID sequence...")
        cur.execute("SELECT setval('exercises_id_seq', (SELECT MAX(id) FROM exercises))")
        
        for name, category in exercises:
            # We'll generate a basic canonical key (lowercase name)
            key = name.lower().strip()
            
            cur.execute("""
                INSERT INTO exercises (name, category, canonical_key)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO NOTHING;
            """, (name, category, key))
            
            if cur.rowcount > 0:
                print(f"  [✓] Added: {name}")
            else:
                print(f"  [!] Skipped (already exists): {name}")
                
        conn.commit()
        cur.close()
        conn.close()
        print("\n✅ Done!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_exercises()
