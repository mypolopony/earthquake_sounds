import logging

import eventlet
import requests
from flask import Flask, render_template
from flask_socketio import SocketIO

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = ".Tmg^T+I5y#x"  # Replace with a secure key for production

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)


# Define WebSocket events
@socketio.on("connect")
def handle_connect():
    print("Client connected")
    socketio.emit("message", {"data": "Welcome!"})
    print(f"Active clients: {socketio.server.manager.get_participants('/', '/')}")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")
    print(f"Remaining clients: {socketio.server.manager.get_participants('/', '/')}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/websocket")
def websocket():
    return render_template("websocket.html")


def poll_api_and_emit():
    """
    Make sure the API is only polled when there are active WebSocket clients.
    """
    while True:
        # Check if any clients are connected
        rooms = socketio.server.manager.rooms  # Get all active rooms
        active_clients = len(
            rooms.get("/", {})
        )  # Default to empty if "/" doesn't exist

        if active_clients <= 1:  # 1 means only the server itself is in the room
            print("🚫 No active clients, skipping API request.")
            eventlet.sleep(5)
            continue

        try:
            response = requests.get("https://jsonplaceholder.typicode.com/todos/1")
            if response.status_code == 200:
                data = response.json()
                print("Fetched data from API:", data)
                socketio.emit("api_data", data)  # Emit data to connected clients
            else:
                print(f"API responded with status code {response.status_code}")
        except Exception as e:
            print(f"Error polling API: {e}")
        eventlet.sleep(5)  # Poll every 5 seconds


# Start the server
if __name__ == "__main__":
    # Run API polling in a separate thread
    eventlet.spawn(poll_api_and_emit)

    # Start Flask-SocketIO server
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, use_reloader=False)
