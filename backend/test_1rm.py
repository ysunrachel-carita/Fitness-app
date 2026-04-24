from app import app, get_db, calculate_unified_1rm

with app.app_context():
    conn = get_db()
    print('1RM Exercise 1:', calculate_unified_1rm(conn, 1, 1))
    print('1RM Exercise 2:', calculate_unified_1rm(conn, 2, 1))
    conn.close()
