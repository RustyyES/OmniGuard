import os
import psycopg2
import datetime

# Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433")
DB_NAME = os.environ.get("DB_NAME", "disaster_db")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password")

def view_data():
    print("-" * 80)
    print(f"Connecting to Database {DB_NAME} at {DB_HOST}:{DB_PORT}...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cur = conn.cursor()
        
        # Fetch recent events
        cur.execute("SELECT id, place, magnitude, time, alert_level FROM earthquakes ORDER BY time DESC LIMIT 10")
        rows = cur.fetchall()
        
        print(f"Successfully connected! Found {len(rows)} recent events:")
        print("-" * 80)
        print(f"{'ID':<5} | {'MAG':<5} | {'ALERT':<8} | {'TIME':<20} | {'PLACE'}")
        print("-" * 80)
        
        for row in rows:
            id, place, mag, ts, alert = row
            # Handle None values
            place = place or "Unknown"
            mag = mag or 0.0
            alert = alert or "N/A"
            ts = ts or 0
            
            # Convert timestamp to readable date
            if ts:
                dt = datetime.datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
            else:
                dt = "N/A"
                
            print(f"{id:<5} | {mag:<5} | {alert:<8} | {dt:<20} | {place}")
            
        print("-" * 80)
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {e}")
        print("Make sure the Docker containers are running (docker compose up -d).")

if __name__ == "__main__":
    view_data()
