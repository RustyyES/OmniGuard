// State
const state = {
    myLocation: { lat: 30.0444, lon: 31.2357 },
    radius: 500,
    events: [],
    socket: null
};

// DOM Elements
const mapElement = document.getElementById('map');
const radiusSlider = document.getElementById('radius-slider');
const radiusVal = document.getElementById('radius-val');
const magSlider = document.getElementById('mag-slider');
const magVal = document.getElementById('mag-val');
const btnSave = document.getElementById('btn-save');
const btnSimulate = document.getElementById('btn-simulate');
const btnDismiss = document.getElementById('btn-dismiss');
const connectionStatus = document.getElementById('connection-status');
const statusDot = document.querySelector('.dot');
const eventList = document.getElementById('event-list');
const alertOverlay = document.getElementById('alert-overlay');

// Map Initialization
const map = L.map('map').setView([state.myLocation.lat, state.myLocation.lon], 5);

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

// My Location Marker
const myIcon = L.divIcon({
    className: 'my-location-icon',
    html: '<div style="background-color: #3b82f6; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>',
    iconSize: [16, 16]
});
let myMarker = L.marker([state.myLocation.lat, state.myLocation.lon], { icon: myIcon }).addTo(map).bindPopup("My Location");

// Radius Circle
let radiusCircle = L.circle([state.myLocation.lat, state.myLocation.lon], {
    color: '#3b82f6',
    fillColor: '#3b82f6',
    fillOpacity: 0.1,
    radius: state.radius * 1000
}).addTo(map);

// Event Markers Layer Group
const markersLayer = L.layerGroup().addTo(map);

// --- API FUNCTIONS ---

async function fetchLocation() {
    try {
        const res = await fetch('/api/location');
        const data = await res.json();
        state.myLocation = data;
        
        // Update Map
        myMarker.setLatLng([data.lat, data.lon]);
        radiusCircle.setLatLng([data.lat, data.lon]);
        map.setView([data.lat, data.lon], 5);
    } catch (e) {
        console.error("Failed to fetch location", e);
    }
}

async function fetchEvents() {
    try {
        const res = await fetch('/api/events');
        const events = await res.json();
        updateFeed(events);
        updateMap(events);
    } catch (e) {
        console.error("Failed to fetch events", e);
    }
}

async function simulateEvent() {
    const mag = magSlider.value;
    try {
        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ magnitude: mag })
        });
        const data = await res.json();
        console.log("Simulated:", data);
    } catch (e) {
        console.error("Simulation failed", e);
    }
}

// --- UI UPDATES ---

function updateFeed(events) {
    eventList.innerHTML = '';
    if (events.length === 0) {
        eventList.innerHTML = '<div class="empty-state">No recent events.</div>';
        return;
    }

    events.forEach(event => {
        const card = document.createElement('div');
        const alertColor = event.alert || 'green'; // Default to green if missing
        card.className = `event-card ${alertColor}`;
        
        const date = new Date(event.time).toLocaleString();
        
        card.innerHTML = `
            <div class="event-header">
                <span>${event.place || event.location}</span>
                <span>M${event.magnitude}</span>
            </div>
            <div class="event-meta">
                ${date} <br>
                Source: ${event.source || 'Unknown'}
            </div>
        `;
        eventList.appendChild(card);
    });
}

function updateMap(events) {
    markersLayer.clearLayers();
    events.forEach(event => {
        const lat = event.lat || event.coords[1];
        const lon = event.lon || event.coords[0];
        const color = getSeverityColor(event.magnitude);
        
        L.circleMarker([lat, lon], {
            radius: 8,
            fillColor: color,
            color: "#fff",
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(markersLayer).bindPopup(`
            <b>${event.place || event.location}</b><br>
            Magnitude: ${event.magnitude}<br>
            Time: ${new Date(event.time).toLocaleString()}
        `);
    });
}

function getSeverityColor(mag) {
    if (mag >= 7) return '#ef4444'; // Red
    if (mag >= 5) return '#f97316'; // Orange
    return '#eab308'; // Yellow
}

function showAlert(event) {
    const dist = calculateDistance(state.myLocation.lat, state.myLocation.lon, event.coords[1], event.coords[0]);
    
    // Only show if within radius
    if (dist > state.radius) return;

    document.getElementById('alert-title').innerText = "EARTHQUAKE WARNING";
    document.getElementById('alert-details').innerText = `Magnitude ${event.magnitude} Earthquake detected ${Math.round(dist)}km away.`;
    
    // AI Guidance (Mocked for now if not provided by backend, but backend should provide it via consumer logic)
    // Actually, the consumer prints it. The backend just forwards the raw event.
    // Let's generate a simple client-side message or fetch it.
    // For this demo, we'll use a static template if missing.
    
    const steps = `
        <ol>
            <li><strong>DROP, COVER, and HOLD ON.</strong> Get under a sturdy desk or table.</li>
            <li>Stay away from windows and heavy furniture.</li>
            <li>If outdoors, move to a clear area away from buildings and power lines.</li>
        </ol>
    `;
    
    document.getElementById('ai-steps').innerHTML = steps;
    alertOverlay.classList.remove('hidden');
}

// --- WEBSOCKET ---

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/alerts`;
    
    state.socket = new WebSocket(wsUrl);

    state.socket.onopen = () => {
        connectionStatus.innerText = "Connected";
        statusDot.classList.add('connected');
    };

    state.socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("WS Message:", data);
        
        // Add to feed
        const newEvent = {
            ...data,
            place: data.location,
            lat: data.coords[1],
            lon: data.coords[0]
        };
        
        // Prepend to list (simplified)
        fetchEvents(); // Refresh full list for simplicity
        
        // Check for alert
        showAlert(data);
    };

    state.socket.onclose = () => {
        connectionStatus.innerText = "Disconnected";
        statusDot.classList.remove('connected');
        setTimeout(connectWebSocket, 3000); // Reconnect
    };
}

// --- UTILS ---
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// --- EVENTS ---

radiusSlider.addEventListener('input', (e) => {
    state.radius = e.target.value;
    radiusVal.innerText = state.radius;
    radiusCircle.setRadius(state.radius * 1000);
});

magSlider.addEventListener('input', (e) => {
    magVal.innerText = e.target.value;
});

btnSimulate.addEventListener('click', simulateEvent);

btnDismiss.addEventListener('click', () => {
    alertOverlay.classList.add('hidden');
});

// --- INIT ---
fetchLocation();
fetchEvents();
connectWebSocket();
