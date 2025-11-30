import json
import math
import os
import psycopg2
import google.generativeai as genai
from kafka import KafkaConsumer

# --- CONFIGURATION ---
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "disaster_db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")

# My Location (Default: Cairo)
MY_LAT = float(os.environ.get("MY_LAT", "30.0444"))
MY_LON = float(os.environ.get("MY_LON", "31.2357"))
ALERT_RADIUS_KM = 500.0

# Configure Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-pro')

# Mock Users Database (Simulating what would be in your Users table)
# We put one user in Japan (High Risk) and one in Egypt (Safe)
USERS = [
    {"id": 0, "name": "ME (My Location)", "lat": MY_LAT, "lon": MY_LON},
    {"id": 1, "name": "Eyad (Egypt)", "lat": 28.236, "lon": 33.625}, 
    {"id": 2, "name": "Tanaka (Japan)", "lat": 35.676, "lon": 139.650},
    {"id": 3, "name": "Alice (California)", "lat": 34.052, "lon": -118.243}
]

# --- DATABASE SETUP ---
def init_db():
    # ADD port=DB_PORT here
    conn = psycopg2.connect(host=DB_HOST, port=int(DB_PORT), database=DB_NAME, user=DB_USER, password=DB_PASS)
    cur = conn.cursor()
    # Create Earthquakes Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS earthquakes (
            id SERIAL PRIMARY KEY,
            external_id VARCHAR(50),
            place VARCHAR(255),
            magnitude FLOAT,
            time BIGINT,
            lat FLOAT,
            lon FLOAT,
            alert_level VARCHAR(20),
            ai_guidance TEXT
        );
    """)
    conn.commit()
    return conn, cur

# --- HELPER FUNCTIONS ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_ai_advice(user_name, location, magnitude, distance):
    prompt = f"""
    You are an emergency response AI. 
    A Magnitude {magnitude} earthquake occurred in {location}.
    
    1. Assess the danger level (Critical, Moderate, or Low).
    2. Give 3 specific, actionable steps for someone {int(distance)}km away.
    Keep it short (max 50 words).
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "AI Service Unavailable. Stay safe."

if __name__ == "__main__":
    conn, cur = init_db()
    print("OmniGuard Smart Core: Active")
    print(f"Monitoring for location: {MY_LAT}, {MY_LON}")
    print("Listening for Global Events...")

    consumer = None
    for i in range(10):
        try:
            consumer = KafkaConsumer(
                "disaster_events",
                bootstrap_servers=[KAFKA_BROKER],
                auto_offset_reset='latest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print("Connected to Kafka!")
            break
        except Exception as e:
            print(f"Waiting for Kafka... ({e})")
            time.sleep(5)
            
    if not consumer:
        print("Failed to connect to Kafka after retries.")
        exit(1)

    for message in consumer:
        event = message.value
        
        # Calculate distance to ME for AI context
        dist_to_me = calculate_distance(MY_LAT, MY_LON, event['coords'][1], event['coords'][0])
        
        # Generate AI Guidance if it's a significant event or near me
        ai_guidance = None
        if event['magnitude'] >= 5.0 or dist_to_me < ALERT_RADIUS_KM:
             ai_guidance = get_ai_advice("User", event['location'], event['magnitude'], dist_to_me)

        # 1. SAVE TO DATABASE
        try:
            cur.execute("""
                INSERT INTO earthquakes (place, magnitude, time, lat, lon, alert_level, ai_guidance)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                event['location'], 
                event['magnitude'], 
                event['time'], 
                event['coords'][1], 
                event['coords'][0],
                event.get('alert', 'green'),
                ai_guidance
            ))
            conn.commit()
            print(f"[DB SAVED] {event['location']} - Mag {event['magnitude']}")
        except Exception as e:
            print(f"DB Error: {e}")
            conn.rollback()

        # 2. CHECK USERS (The "Danger Range" requirement)
        # We check against the static list which now includes "ME"
        for user in USERS:
            dist = calculate_distance(user['lat'], user['lon'], event['coords'][1], event['coords'][0])
            
            # Danger Threshold
            if dist < ALERT_RADIUS_KM: 
                print(f"\n!!! ALERT TRIGGERED FOR {user['name']} !!!")
                print(f"Distance: {int(dist)}km")
                
                # 3. GEMINI AI ADVICE
                print("Requesting AI Guidance...")
                advice = get_ai_advice(user['name'], event['location'], event['magnitude'], dist)
                print(f"\n--- GEMINI ADVICE ---\n{advice}\n---------------------\n")