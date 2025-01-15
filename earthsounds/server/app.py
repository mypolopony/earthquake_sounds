import logging

from flask import Flask, render_template
from flask_socketio import SocketIO

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "z!bB3!UL!"  # Replace with a secure key for production

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)


# Define WebSocket events
@socketio.on("connect")
def handle_connect():
    print("Client connected")
    socketio.emit("message", {"data": "Welcome!"})
    print("Emitted 'Welcome!' message")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


@socketio.on("custom_event")
def handle_custom_event(data):
    print(f"Received event: {data}")
    socketio.emit("response", {"data": "Acknowledged"})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/websocket")
def websocket():
    return render_template("websocket.html")


# Start the server
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)
