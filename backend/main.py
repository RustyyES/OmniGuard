import os
import json
import asyncio
import threading
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaConsumer, KafkaProducer
import psycopg2
from psycopg2.extras import RealDictCursor
import google.generativeai as genai

# --- CONFIGURATION ---
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "disaster_db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password")
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
MY_LAT = float(os.environ.get("MY_LAT", "30.0444"))
MY_LON = float(os.environ.get("MY_LON", "31.2357"))
GEMINI_KEY = os.environ.get("GEMINI_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-2.5-pro')
else:
    model = None
    print("WARNING: GEMINI_KEY not set. AI features will be disabled.")

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Frontend
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# --- DATABASE ---
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=int(DB_PORT), database=DB_NAME, user=DB_USER, password=DB_PASS
    )

# --- WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

# --- KAFKA CONSUMER THREAD ---
def kafka_consumer_loop():
    consumer = KafkaConsumer(
        "disaster_events",
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='latest',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for message in consumer:
        event = message.value
        # Broadcast to WebSockets
        # We need to run this in the main event loop or use run_coroutine_threadsafe
        # But since we are in a thread, we can't easily access the main loop directly without passing it.
        # A simpler way for this demo is to just use a global loop reference or similar.
        # However, FastAPI runs on asyncio.
        
        # Let's use a simple approach:
        # We'll just print for now, and rely on the client polling or use a proper async consumer.
        # Actually, let's try to use `manager.broadcast` properly.
        # We can use `asyncio.run_coroutine_threadsafe(manager.broadcast(...), main_loop)`
        pass

# Better approach: Async Kafka Consumer in background task
# --- KAFKA CONSUMER BACKGROUND TASK ---
def kafka_consumer_thread(loop):
    print("Connecting to Kafka in background thread...")
    consumer = None
    # Retry connection
    for i in range(10):
        try:
            consumer = KafkaConsumer(
                "disaster_events",
                bootstrap_servers=[KAFKA_BROKER],
                auto_offset_reset='latest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print("Backend connected to Kafka!")
            break
        except Exception as e:
            print(f"Backend waiting for Kafka... ({e})")
            import time
            time.sleep(5)
            
    if not consumer:
        print("Backend failed to connect to Kafka.")
        return

    try:
        for message in consumer:
            event = message.value
            # Schedule the broadcast on the main event loop
            asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps(event)), loop)
    except Exception as e:
        print(f"Kafka Consumer Error: {e}")

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    # Start Kafka consumer in a separate thread so it doesn't block the async loop
    t = threading.Thread(target=kafka_consumer_thread, args=(loop,), daemon=True)
    t.start()

# --- API ENDPOINTS ---

@app.get("/")
async def read_root():
    from fastapi.responses import FileResponse
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    return FileResponse(index_path)

@app.get("/api/location")
async def get_location():
    return {"lat": MY_LAT, "lon": MY_LON}

@app.get("/api/events")
async def get_events():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM earthquakes ORDER BY time DESC LIMIT 50")
        events = cur.fetchall()
        cur.close()
        conn.close()
        return events
    except Exception as e:
        return {"error": str(e)}

@app.delete("/api/events/{event_id}")
async def delete_event(event_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Delete by external_id (which stores our UUID)
        cur.execute("DELETE FROM earthquakes WHERE external_id = %s", (event_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "deleted", "id": event_id}
    except Exception as e:
        return {"error": str(e)}

from pydantic import BaseModel

class SimulateRequest(BaseModel):
    magnitude: float

@app.post("/api/simulate")
async def simulate_event(request: SimulateRequest):
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Trigger the producer service to simulate? 
        # Actually, the requirement says "triggers the backend's SIMULATE_EARTHQUAKE feature".
        # But the producer service is running separately.
        # We can just send a fake event directly from here to the Kafka topic!
        
        import time
        import random
        
        lat_offset = random.uniform(-0.5, 0.5)
        lon_offset = random.uniform(-0.5, 0.5)
        
        # Generate AI Advice immediately
        ai_advice = "AI Service Unavailable. Please check your GEMINI_KEY in .env. \n\nStandard Safety Protocol:\n1. DROP, COVER, and HOLD ON immediately.\n2. Stay away from glass, windows, and heavy furniture.\n3. If outdoors, move to a clear area away from buildings, trees, and power lines.\n4. Do not use elevators."
        if model:
            try:
                prompt = f"""
                You are an emergency response AI. 
                A Magnitude {request.magnitude} earthquake occurred.
                Give 3 specific, actionable steps for someone nearby.
                Keep it short (max 50 words).
                """
                ai_resp = model.generate_content(prompt)
                ai_advice = ai_resp.text
            except Exception as e:
                print(f"AI Generation Error: {e}")

        import uuid
        fake_event = {
            "id": str(uuid.uuid4()),
            "source": "SIMULATION_WEB",
            "type": "Earthquake",
            "magnitude": request.magnitude,
            "location": "WEB SIMULATED QUAKE",
            "time": int(time.time() * 1000),
            "coords": [MY_LON + lon_offset, MY_LAT + lat_offset, 10.0],
            "alert": "red",
            "url": "#",
            "ai_guidance": ai_advice
        }
        
        producer.send("disaster_events", fake_event)
        return {"status": "simulated", "event": fake_event}
        
    except Exception as e:
        return {"error": str(e)}

class ChatRequest(BaseModel):
    message: str
    context: dict = {}

@app.post("/api/chat")
async def chat_with_ai(request: ChatRequest):
    if not model:
        return {"response": "AI service is not configured."}
    
    try:
        # Construct prompt with context
        event_context = ""
        if request.context:
            event_context = f"Context: User is asking about a {request.context.get('type', 'event')} at {request.context.get('place', 'unknown location')} with magnitude {request.context.get('magnitude', 'unknown')}."
        
        prompt = f"""
        You are OmniGuard AI, an empathetic and helpful emergency assistant.
        {event_context}
        User: {request.message}
        
        Instructions:
        1. Be calm, reassuring, and concise (max 50 words).
        2. Speak naturally like a human helper, not a robot.
        3. Acknowledge the user's specific situation or fear.
        4. Provide immediate, actionable safety advice.
        """
        
        response = model.generate_content(prompt)
        return {"response": response.text}
    except Exception as e:
        return {"error": str(e)}

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection open
    except WebSocketDisconnect:
        manager.disconnect(websocket)
