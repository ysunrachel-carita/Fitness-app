import psycopg2

url = "postgresql://postgres:postgres@localhost:5432/fitness_app"

def check_local_postgres():
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM exercises ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
        print("ID | Name")
        print("-" * 20)
        for row in rows:
            print(f"{row[0]} | {row[1]}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_local_postgres()
