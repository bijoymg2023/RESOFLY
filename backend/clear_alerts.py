import sqlite3
import os

DB_PATH = "./thermo_vision.db"

def clear_alerts():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

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
