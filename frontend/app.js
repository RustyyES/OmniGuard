// State
const state = {
    myLocation: { lat: 30.0444, lon: 31.2357 },
    radius: 500,
    events: [],
    socket: null,
    currentEvent: null
};

// DOM Elements
const mapElement = document.getElementById('map');
const radiusSlider = document.getElementById('radius-slider');
const radiusVal = document.getElementById('radius-val');
const magSlider = document.getElementById('mag-slider');
const magVal = document.getElementById('mag-val');
const btnSave = document.getElementById('btn-save');
const btnSimulate = document.getElementById('btn-simulate');
const btnClearSim = document.getElementById('btn-clear-sim');
const btnDismiss = document.getElementById('btn-dismiss');
const connectionStatus = document.getElementById('connection-status');
const statusDot = document.querySelector('.dot');
const eventList = document.getElementById('event-list');
const alertOverlay = document.getElementById('alert-overlay');
const chatSection = document.getElementById('chat-section');
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const btnSendChat = document.getElementById('btn-send-chat');

// Map Initialization
// Initialize Map (Dark Theme)
const map = L.map('map').setView([20, 0], 2);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

// Fix map gray areas
setTimeout(() => {
    map.invalidateSize();
}, 100);

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
        console.log("Simulated (HTTP):", data);
        if (data.event) {
            showAlert(data.event);
            // Show Clear Button
            btnClearSim.classList.remove('hidden');
            btnClearSim.dataset.eventId = data.event.id;
        }
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
    // Prevent duplicate alerts for the same event
    if (state.currentEvent && state.currentEvent.id === event.id) {
        console.log("Duplicate event ignored:", event.id);
        return;
    }
    state.currentEvent = event;
    const dist = calculateDistance(state.myLocation.lat, state.myLocation.lon, event.coords[1], event.coords[0]);

    // Only show if within radius
    if (dist > state.radius) return;

    document.getElementById('alert-title').innerText = "EARTHQUAKE WARNING";
    document.getElementById('alert-details').innerText = `Magnitude ${event.magnitude} Earthquake detected ${Math.round(dist)}km away.`;

    // AI Guidance
    const aiSteps = document.getElementById('ai-steps');
    aiSteps.innerHTML = '';

    // Clear Chat History completely for new event
    chatHistory.innerHTML = '';

    // Reset Chat Input
    chatInput.value = '';

    // Typewriter effect for AI Guidance
    if (event.ai_guidance) {
        // Cancel any existing typewriter
        if (window.typewriterTimeout) clearTimeout(window.typewriterTimeout);

        // Parse Markdown
        let htmlContent = event.ai_guidance;
        if (typeof marked !== 'undefined') {
            htmlContent = marked.parse(event.ai_guidance);
        } else {
            console.warn("marked.js not loaded");
        }

        // For HTML typewriter, we need a different approach or just show it
        // Since typewriter with HTML tags is complex, we will fade it in for better UX with Markdown
        aiSteps.innerHTML = htmlContent;
        aiSteps.style.opacity = 0;

        // Simple fade in animation
        let op = 0.1;
        const timer = setInterval(function () {
            if (op >= 1) {
                clearInterval(timer);
            }
            aiSteps.style.opacity = op;
            aiSteps.style.filter = 'alpha(opacity=' + op * 100 + ")";
            op += op * 0.1;
        }, 10);

        // Add to chat history ONLY if it's not already there (though we cleared it)
        // BUT user requested "once under ai safety guidance and once above text box" -> "I want only one"
        // So we do NOT add it to chat history here. User can ask follow-up.
        chatInput.focus();
    } else {
        aiSteps.innerText = "Analyzing situation...";
    }

    alertOverlay.classList.remove('hidden');
}

function typeWriter(text, element, i = 0, callback) {
    if (i < text.length) {
        element.innerHTML += text.charAt(i);
        i++;
        // Auto-scroll if needed
        element.scrollTop = element.scrollHeight;
        window.typewriterTimeout = setTimeout(() => typeWriter(text, element, i, callback), 20); // Faster speed
    } else if (callback) {
        callback();
    }
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
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
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

btnClearSim.addEventListener('click', async () => {
    const eventId = btnClearSim.dataset.eventId;
    if (!eventId) return;

    try {
        // 1. Call Delete API
        await fetch(`/api/events/${eventId}`, { method: 'DELETE' });

        // 2. Clear from State
        state.events = state.events.filter(e => e.id !== eventId && e.external_id !== eventId);
        if (state.currentEvent && state.currentEvent.id === eventId) {
            state.currentEvent = null;
            alertOverlay.classList.add('hidden');
        }

        // 3. Update UI
        updateFeed(state.events);
        updateMap(state.events);

        // 4. Hide Button
        btnClearSim.classList.add('hidden');

    } catch (e) {
        console.error("Failed to clear simulation", e);
    }
});

btnDismiss.addEventListener('click', () => {
    alertOverlay.classList.add('hidden');
});

btnSendChat.addEventListener('click', sendChatMessage);

async function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Add User Message
    addChatMessage(text, 'user');
    chatInput.value = '';

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                context: state.currentEvent
            })
        });
        const data = await res.json();
        const aiResponse = data.response || data.error;
        addChatMessage(marked.parse(aiResponse), 'ai', true); // true for isHTML
    } catch (e) {
        addChatMessage("Error connecting to AI.", 'ai');
    }
}

function addChatMessage(text, sender, isHTML = false) {
    const div = document.createElement('div');
    div.className = `chat-message ${sender}`;
    if (isHTML) {
        div.innerHTML = text;
    } else {
        div.innerText = text;
    }
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// --- INIT ---
fetchLocation();
fetchEvents();
connectWebSocket();
