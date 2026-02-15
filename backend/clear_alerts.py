import sqlite3
import os

POSSIBLE_PATHS = [
    "./thermo_vision.db",
    "./backend/thermo_vision.db",
    "../thermo_vision.db"
]

def clear_alerts():
    db_path = None
    for p in POSSIBLE_PATHS:
        if os.path.exists(p):
            db_path = p
            break
            
    if not db_path:
        print(f"Database not found in: {POSSIBLE_PATHS}")
        return
        
    print(f"Found database at: {db_path}")
    DB_PATH = db_path

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Count before
        cursor.execute("SELECT COUNT(*) FROM alerts")
        count = cursor.fetchone()[0]
        print(f"Found {count} alerts.")
        
        # Delete
        cursor.execute("DELETE FROM alerts")
        conn.commit()
        print("All alerts cleared.")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    clear_alerts()
