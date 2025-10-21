from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import TextContent, ChatMessage
from datetime import datetime, timezone
from uuid import uuid4

from models import StrategyRequest, StrategyResponse

# The Strategy Agent
strategy_agent = Agent(
    name="martian_strategy_agent",
    port=8002, # Use a different port than the user agent
    seed="martian_strategy_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8002/submit"],
)

# Define a protocol for communication with the Strategy Agent
strategy_comm_proto = Protocol("StrategyComm", version="1.0")

# Utility function to wrap plain text into a ChatMessage
def create_text_chat(text: str) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )

@strategy_comm_proto.on_message(model=StrategyRequest)
async def handle_strategy_request(ctx: Context, sender: str, msg: StrategyRequest):
    ctx.logger.info(f"Received strategy request from {sender}: {msg.user_query} (Session: {msg.session_id})")

    # In the future, this is where the complex strategy generation logic will go.
    # For now, we return a hardcoded response.
    hardcoded_strategy = (
        f"Based on your query \"{msg.user_query}\", I recommend staking SOL on Marinade Finance "
        "for an estimated 7.2% APY. This is a low-risk strategy with good liquidity."
    )

    # Send the strategy response back to the sender (which will be the User Agent)
    await ctx.send(sender, StrategyResponse(
        strategy_description=hardcoded_strategy,
        session_id=msg.session_id # Pass back the session_id
    ))


# Include the new strategy communication protocol
strategy_agent.include(strategy_comm_proto)

if __name__ == "__main__":
    print(f"Strategy Agent running with address: {strategy_agent.address}")
    strategy_agent.run()
