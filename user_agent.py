from uagents import Agent, Context, Protocol
from uagents.crypto import Identity
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent, chat_protocol_spec
from datetime import datetime
from uuid import uuid4
import json

from models import StrategyRequest, StrategyResponse, ExecuteStrategy, ExecutionResult, StrategyProposal, CommandMessage, SubmitSignedTransaction, UnsignedTransactionProposal
from address_book import save_address, get_address

# The User Agent (Martian Core)
user_agent = Agent(
    name="martian_user_agent",
    port=8001, # This is the port the API will send messages to
    seed="martian_user_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8001/submit"],
)

# Initialize the chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Utility function to wrap plain text into a ChatMessage
def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )

@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Received chat message from {sender}")
    # Always send back an acknowledgement when a message is received
    await ctx.send(sender, ChatMessage.response_ack(msg))

    response_content = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            user_query = item.text
            ctx.logger.info(f"User query: {user_query}")

            # Forward user query to Strategy Agent
            strategy_agent_address = get_address("strategy_agent")
            if not strategy_agent_address:
                response_content = "Strategy Agent not found. Please ensure it is running."
            else:
                ctx.logger.info(f"Forwarding query to Strategy Agent at {strategy_agent_address}")
                strategy_response: StrategyResponse = await ctx.call(
                    strategy_agent_address,
                    StrategyRequest(user_query=user_query, session_id=str(msg.msg_id)),
                    StrategyResponse
                )

                if strategy_response and strategy_response.strategy_description:
                    try:
                        # Attempt to parse the strategy_description as JSON
                        parsed_strategy = json.loads(strategy_response.strategy_description)
                        if parsed_strategy.get("type") == "strategy_proposal":
                            # If it's a strategy proposal, send it back as a ChatMessage with the JSON content
                            response_content = strategy_response.strategy_description # Send raw JSON string
                        else:
                            response_content = f"Strategy Agent responded: {strategy_response.strategy_description}"
                    except json.JSONDecodeError:
                        response_content = f"Strategy Agent responded: {strategy_response.strategy_description}"
                else:
                    response_content = "Strategy Agent did not provide a valid response."

    # Send response back to the original sender (API)
    await ctx.send(sender, create_text_chat(response_content))

@user_agent.on_message(model=CommandMessage)
async def handle_command_message(ctx: Context, sender: str, msg: CommandMessage):
    ctx.logger.info(f"Received command from {sender}: {msg.command}")
    await ctx.send(sender, ChatMessage.response_ack(msg))

    response_content = ""

    if msg.command == "execute":
        strategy_id = msg.payload.get("strategy_id")
        strategy_description = msg.payload.get("strategy_description")
        ctx.logger.info(f"Executing strategy {strategy_id}: {strategy_description}")

        execution_agent_address = get_address("execution_agent")
        if not execution_agent_address:
            response_content = "Execution Agent not found. Please ensure it is running."
        else:
            ctx.logger.info(f"Sending execution request to Execution Agent at {execution_agent_address}")
            execution_result: ExecutionResult = await ctx.call(
                execution_agent_address,
                ExecuteStrategy(strategy=strategy_description, strategy_id=strategy_id),
                ExecutionResult
            )

            if execution_result and execution_result.success:
                if execution_result.unsigned_tx_b64:
                    # If unsigned transaction is returned, create a proposal for the frontend
                    unsigned_tx_proposal = UnsignedTransactionProposal(
                        type="unsigned_transaction_proposal",
                        unsigned_tx_b64=execution_result.unsigned_tx_b64,
                        strategy_id=strategy_id
                    )
                    response_content = unsigned_tx_proposal.model_dump_json()
                else:
                    response_content = f"Strategy {strategy_id} executed successfully. Transaction Hash: {execution_result.transaction_hash}"
            else:
                response_content = f"Strategy execution failed for {strategy_id}. Error: {execution_result.error}"

    elif msg.command == "submit_signed_tx":
        signed_tx_b64 = msg.payload.get("signed_tx_b64")
        strategy_id = msg.payload.get("strategy_id")
        ctx.logger.info(f"Submitting signed transaction for strategy {strategy_id}")

        execution_agent_address = get_address("execution_agent")
        if not execution_agent_address:
            response_content = "Execution Agent not found. Please ensure it is running."
        else:
            ctx.logger.info(f"Sending signed transaction to Execution Agent at {execution_agent_address}")
            execution_result: ExecutionResult = await ctx.call(
                execution_agent_address,
                SubmitSignedTransaction(signed_tx_b64=signed_tx_b64, strategy_id=strategy_id),
                ExecutionResult
            )

            if execution_result and execution_result.success:
                response_content = f"Transaction submitted successfully. Hash: {execution_result.transaction_hash}"
            else:
                response_content = f"Transaction submission failed. Error: {execution_result.error}"

    else:
        response_content = f"Unknown command: {msg.command}"

    await ctx.send(sender, create_text_chat(response_content))


# Include the chat protocol
user_agent.include(chat_proto)

if __name__ == "__main__":
    save_address("user_agent", user_agent.address)
    print(f"User Agent running with address: {user_agent.address}")
    user_agent.run()
