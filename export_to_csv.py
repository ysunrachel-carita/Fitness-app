import sqlite3
import csv
import os

def export_db_to_csv(db_path, export_dir):
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table_name in tables:
            table_name = table_name[0]
            cursor.execute(f"SELECT * FROM {table_name}")
            
            # Get column names
            column_names = [description[0] for description in cursor.description]
            
            csv_file_path = os.path.join(export_dir, f"{table_name}.csv")
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(column_names)
                writer.writerows(cursor.fetchall())
                print(f"Exported table '{table_name}' to {csv_file_path}")

        print("\nAll tables exported successfully.")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Using absolute paths or relying on cwd. 
    # CWD will be /Users/rachelsun/Desktop/fitness app
    db_file = 'fitness.db'
    export_folder = 'exports'
    export_db_to_csv(db_file, export_folder)
