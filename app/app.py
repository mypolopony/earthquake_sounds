import logging
from datetime import datetime

import eventlet
from flask import Flask, render_template
from flask_socketio import SocketIO

from api import InvalidAPIResponse, USGSEarthquakeAPI

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
    # API client
    api_client = USGSEarthquakeAPI()
    params = {
        "limit": 20,
        "minmagnitude": 2,
    }

    while True:
        # Check if any clients are connected
        rooms = socketio.server.manager.rooms  # Get all active rooms
        active_clients = len(rooms.get("/", {}))

        # No active clients, skip API request
        if active_clients <= 1:
            eventlet.sleep(5)
            continue

        try:
            # Fetch
            data = api_client.fetch_earthquakes(params)

            # Parse
            earthquakes = api_client.parse_earthquake_data(data)

            # Display
            if earthquakes:
                quakelist = []
                for quake in earthquakes:
                    timestamp = datetime.fromtimestamp(
                        int(quake["time"] / 1000)
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    quakelist.append(
                        f"{quake['place']} (Mag: {quake['magnitude']}) at {timestamp}"
                    )
                socketio.emit("api_data", quakelist)

        except InvalidAPIResponse as e:
            socketio.emit("message", f"Error parsing API response: {e}")
        except Exception as e:
            socketio.emit("message", f"An unexpected error occurred: {e}")

        eventlet.sleep(10)  # Wait before the next poll


# Start the server
if __name__ == "__main__":
    # Run API polling in a separate thread
    eventlet.spawn(poll_api_and_emit)

    # Start Flask-SocketIO server
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, use_reloader=False)
