import asyncio
from flask import Flask, jsonify, request
from flask_cors import CORS

from uagents.communication import send_sync_message
from uagents.crypto import Identity
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

# We need to import the utility function from the agent file
from agent import create_text_chat

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# The address of the agent we want to communicate with.
# This should match the address of the running martian_user_agent
AGENT_ADDRESS = "agent1qg6xflefemcfff2t59xedc87cwl630c4ryx3rp7j6v6f3e69umu3yyrd3ph"

# This identity is used to sign messages sent from the API to the agent
api_identity = Identity.generate()

@app.route("/api/chat", methods=["POST"])
def handle_chat():
    data = request.get_json()
    message_text = data.get("message")

    if not message_text:
        return jsonify({"status": "error", "message": "No message provided"}), 400

    # Create the chat message using the utility from our agent file
    chat_message = create_text_chat(message_text)

    # For requests that need a response, we need to await the async response
    # and run it in an event loop.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        response = loop.run_until_complete(
            send_sync_message(
                AGENT_ADDRESS, 
                chat_message, 
                response_type=ChatMessage, # We expect a ChatMessage in response
                sender=api_identity,
                timeout=20.0 # Add a timeout
            )
        )
    finally:
        loop.close()
    
    if isinstance(response, ChatMessage) and response.content:
        # Extract the text from the first TextContent item in the response
        response_text = ""
        for item in response.content:
            if isinstance(item, TextContent):
                response_text = item.text
                break
        
        return jsonify({
            "status": "success",
            "response": response_text
        })
    else:
        return jsonify({"status": "error", "message": "Failed to get a valid response from agent"}), 500

if __name__ == "__main__":
    # NOTE: In a production environment, you would use a production-ready server
    # like Gunicorn or uWSGI instead of app.run()
    app.run(port=5001, debug=True)