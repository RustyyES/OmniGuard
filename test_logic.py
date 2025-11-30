import os
import sys
from unittest.mock import MagicMock

# Mock dependencies
sys.modules["psycopg2"] = MagicMock()
sys.modules["kafka"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()

# Set env vars for testing
os.environ["MY_LAT"] = "30.0444"
os.environ["MY_LON"] = "31.2357"
os.environ["SIMULATE_EARTHQUAKE"] = "true"

# Import modules
try:
    from producer import generate_fake_quake
    from consumer import calculate_distance, ALERT_RADIUS_KM
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_simulation_logic():
    print("Testing Simulation Logic...")
    
    # 1. Generate Fake Quake
    fake_event = generate_fake_quake()
    print(f"Generated Event: {fake_event['location']} at {fake_event['coords']}")
    
    # 2. Calculate Distance
    my_lat = float(os.environ["MY_LAT"])
    my_lon = float(os.environ["MY_LON"])
    quake_lon, quake_lat, depth = fake_event['coords']
    
    dist = calculate_distance(my_lat, my_lon, quake_lat, quake_lon)
    print(f"Calculated Distance: {dist:.2f} km")
    
    # 3. Verify Logic
    if dist < ALERT_RADIUS_KM:
        print("SUCCESS: Event is within alert radius!")
    else:
        print(f"FAILURE: Event is too far ({dist}km)!")
        sys.exit(1)

    # 4. Verify Alert Color
    if fake_event.get('alert') == 'red':
        print("SUCCESS: Alert color is red!")
    else:
        print("FAILURE: Alert color missing or wrong!")

if __name__ == "__main__":
    test_simulation_logic()
