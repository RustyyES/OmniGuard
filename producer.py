import time
import json
import os
import requests
import random
from kafka import KafkaProducer

# --- CONFIGURATION ---
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
USGS_API_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
SIMULATE_EARTHQUAKE = os.environ.get("SIMULATE_EARTHQUAKE", "false").lower() == "true"
MY_LAT = float(os.environ.get("MY_LAT", "30.0444")) # Default: Cairo
MY_LON = float(os.environ.get("MY_LON", "31.2357"))

# Deduplication Cache
SEEN_EVENTS = set()

def json_serializer(data):
    return json.dumps(data).encode("utf-8")

def generate_fake_quake():
    """Generates a fake earthquake ~50km from user"""
    # Add small random offset (approx 0.5 degrees is ~55km)
    lat_offset = random.uniform(-0.5, 0.5)
    lon_offset = random.uniform(-0.5, 0.5)
    
    return {
        "source": "SIMULATION",
        "type": "Earthquake",
        "magnitude": round(random.uniform(4.5, 7.0), 1),
        "location": "SIMULATED QUAKE NEAR YOU",
        "time": int(time.time() * 1000),
        "coords": [MY_LON + lon_offset, MY_LAT + lat_offset, 10.0],
        "alert": "red",
        "url": "http://localhost/simulation"
    }

if __name__ == "__main__":
    # Connect to Kafka
    # Retry connection to Kafka
    producer = None
    for i in range(10):
        try:
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BROKER],
                value_serializer=json_serializer
            )
            print("Connected to Kafka!")
            break
        except Exception as e:
            print(f"Waiting for Kafka... ({e})")
            time.sleep(5)
            
    if not producer:
        print("Failed to connect to Kafka after retries.")
        exit(1)

    print("OmniGuard Ingestion Module Started...")
    print(f"Simulation Mode: {SIMULATE_EARTHQUAKE}")
    print("-------------------------------------")

    while True:
        try:
            # 1. FETCH REAL DATA
            response = requests.get(USGS_API_URL)
            data = response.json()
            features = data.get('features', [])
            
            new_count = 0
            for quake in features:
                quake_id = quake['id']
                
                if quake_id not in SEEN_EVENTS:
                    SEEN_EVENTS.add(quake_id)
                    props = quake['properties']
                    
                    event = {
                        "source": "USGS",
                        "type": "Earthquake",
                        "id": quake_id,
                        "magnitude": props.get('mag'),
                        "location": props.get('place'),
                        "time": props.get('time'),
                        "coords": quake['geometry']['coordinates'], # [long, lat, depth]
                        "alert": props.get('alert'),
                        "url": props.get('url')
                    }
                    
                    producer.send("disaster_events", event)
                    print(f"[SENT] USGS Event: {event['location']} (Mag: {event['magnitude']})")
                    new_count += 1
            
            if new_count == 0:
                print("[INFO] No new real earthquakes found.")

            # 2. SIMULATION INJECTION
            if SIMULATE_EARTHQUAKE:
                fake_event = generate_fake_quake()
                producer.send("disaster_events", fake_event)
                print(f"[SIMULATION] Sent fake quake at {fake_event['location']} Mag:{fake_event['magnitude']}")

            time.sleep(60) # Poll every minute
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
