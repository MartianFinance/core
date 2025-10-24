import asyncio
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import logging
import threading

from uagents import Model
from uagents.communication import send_sync_message
from uagents.crypto import Identity
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from agent import create_text_chat
from address_book import get_address
from models import CommandMessage

# NOTE: Flask-SocketIO is required. Please install it with: pip install Flask-SocketIO eventlet

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO)

AGENT_ADDRESS = get_address("user_agent")
api_identity = Identity.generate()

user_agent_sessions = {}

@socketio.on('connect')
def handle_connect():
    logging.info(f"Client connected: {request.sid}")
    emit('response', {'status': 'success', 'message': 'Connected to Martian API'})

@socketio.on('disconnect')
def handle_disconnect():
    logging.info(f"Client disconnected: {request.sid}")
    if request.sid in user_agent_sessions:
        del user_agent_sessions[request.sid]

def send_to_agent_thread(message):
    """This function runs in a separate thread to send a message to the agent without blocking."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # We are not expecting a direct response here, so we can use a short timeout.
    # The real responses will come back through the /api/agent-response endpoint.
    loop.run_until_complete(
        send_sync_message(AGENT_ADDRESS, message, sender=api_identity, timeout=10.0)
    )
    loop.close()

@socketio.on('chat_message')
def handle_chat_message(data):
    message_text = data.get('message')
    if not message_text:
        emit('error', {'message': 'No message provided'})
        return

    logging.info(f"Received chat message from {request.sid}: {message_text}")
    session_id = request.sid
    user_agent_sessions[session_id] = True

    is_command = False
    parsed_message = None
    if isinstance(message_text, str):
        try:
            if message_text.strip().startswith(("{", "[")):
                parsed_message = json.loads(message_text)
                if isinstance(parsed_message, dict) and "command" in parsed_message:
                    is_command = True
        except json.JSONDecodeError:
            pass

    message_to_send = None
    if is_command:
        message_to_send = CommandMessage(
            command=parsed_message["command"],
            payload=parsed_message.get("payload", {}),
            session_id=session_id
        )
    else:
        message_payload = json.dumps({"text": message_text, "session_id": session_id})
        message_to_send = create_text_chat(message_payload)

    # Run the blocking send_sync_message in a background thread
    thread = threading.Thread(target=send_to_agent_thread, args=(message_to_send,))
    thread.start()

    logging.info(f"Message forwarded to user agent for session: {session_id}")

@app.route("/api/agent-response", methods=["POST"])
def handle_agent_response():
    data = request.get_json()
    session_id = data.get('session_id')
    content = data.get('content')

    if not session_id or not content:
        return jsonify({"status": "error", "message": "Missing session_id or content"}), 400

    if session_id in user_agent_sessions:
        logging.info(f"Relaying agent response to client {session_id}")
        try:
            parsed_content = json.loads(content)
            socketio.emit('agent_response', {'response': parsed_content}, room=session_id)
        except (json.JSONDecodeError, TypeError):
            socketio.emit('agent_response', {'response': content}, room=session_id)
        return jsonify({"status": "success"})
    else:
        logging.warning(f"Received response for unknown session: {session_id}")
        return jsonify({"status": "error", "message": "Unknown session"}), 404

if __name__ == "__main__":
    logging.info("Starting Martian API with SocketIO support...")
    socketio.run(app, port=5001, debug=True)