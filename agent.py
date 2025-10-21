from datetime import datetime, timezone
from uuid import uuid4
from uagents import Agent, Context, Model, Protocol
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.types import DeliveryStatus

# Import shared models
from models import StrategyRequest, StrategyResponse

# This will be our core Martian user-facing agent
# It's configured for local testing and to be published to Agentverse
agent = Agent(
    name="martian_user_agent",
    port=8001,
    seed="martian_user_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8001/submit"],
)

# Ensure the agent has funds to register on Agentverse
fund_agent_if_low(agent.wallet.address())

# Initialize the chat protocol with the standard chat spec
chat_proto = Protocol(spec=chat_protocol_spec)

# Utility function to wrap plain text into a ChatMessage
def create_text_chat(text: str) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )

# Hardcoded address for the Strategy Agent
STRATEGY_AGENT_ADDRESS = "agent1qwyge45dyc50m3ka2s9k4ug44jv9cpmchl5htck3jtfe398m9e9fy5svww8"


# Handle incoming chat messages from the API
@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Received message from {sender}")

    for item in msg.content:
        if isinstance(item, TextContent):
            ctx.logger.info(f"Text message from {sender}: {item.text}")

            # Create a strategy request
            strategy_request = StrategyRequest(user_query=item.text, session_id=str(ctx.session))
            ctx.logger.info(f"Forwarding query to Strategy Agent: {item.text}")

            # Use send_and_receive to wait for the strategy agent's response
            # NOTE: This makes the API call synchronous from the user's perspective
            strategy_response, status = await ctx.send_and_receive(
                STRATEGY_AGENT_ADDRESS,
                strategy_request,
                response_type=StrategyResponse,
                timeout=30, # Add a 30-second timeout
            )

            if status.status == DeliveryStatus.DELIVERED and isinstance(strategy_response, StrategyResponse):
                ctx.logger.info(f"Received strategy response: {strategy_response.strategy_description}")
                response_message = create_text_chat(strategy_response.strategy_description)
            else:
                ctx.logger.error(f"Failed to get strategy from agent: {status.detail if status else 'timeout'}")
                response_message = create_text_chat("Error: Could not get a strategy at this time.")

            # Send the final response back to the original sender (the API)
            await ctx.send(sender, response_message)

@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}")

# Include the chat protocol and publish the manifest to Agentverse
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"Agent running with address: {agent.address}")
    agent.run()
