// Connect to the server
const socket = io("http://127.0.0.1:5001");
socket.on("connect", () => {
    console.log("Connected to WebSocket server");
});

// Generic "message" event
socket.on("message", (data) => {
    console.log("Message from server:", data);
});

// Listen for "api_data" event and display it on the page
socket.on("api_data", (data) => {
    const list = document.getElementById("usgs_earthquakes");
    list.innerHTML = "";  // Clear old data

    // Check for proper type
    if (!Array.isArray(data)) {
        list.textContent = "Error: Expected an array, but received " + typeof data;
        return;
    }

    // Enumerate
    data.forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        list.appendChild(li);
    });
});

// Error
socket.on("connect_error", (error) => {
    console.error("WebSocket connection error:", error);
});

// Disconnect
socket.on("disconnect", () => {
    console.log("Disconnected from WebSocket server");
});