import json
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.types import DeliveryStatus

from address_book import get_address, save_address
from models import (
    StrategyRequest, StrategyResponse, ExecuteStrategy, ExecutionResult, 
    StrategyProposal, CommandMessage, SubmitSignedTransaction, 
    UnsignedTransactionProposal, StatusMessage
)

API_URL = "http://127.0.0.1:5001/api/agent-response"

agent = Agent(
    name="martian_user_agent",
    port=8001,
    seed="martian_user_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8001/submit"],
)

chat_proto = Protocol(spec=chat_protocol_spec)
command_proto = Protocol("CommandProtocol", version="1.0")

async def send_response_to_api(session_id: str, content: str):
    """Sends a response back to the API for a specific session."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(API_URL, json={"session_id": session_id, "content": content}, timeout=30)
    except httpx.RequestError as e:
        print(f"Error sending response to API: {e}")

def create_text_chat(text: str) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )

STRATEGY_AGENT_ADDRESS = get_address("strategy_agent")
EXECUTION_AGENT_ADDRESS = get_address("execution_agent")

@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Received chat message from {sender}")
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
    session_id = None
    user_query = None

    for item in msg.content:
        if isinstance(item, TextContent):
            try:
                data = json.loads(item.text)
                user_query = data.get('text')
                session_id = data.get('session_id')
                break
            except (json.JSONDecodeError, TypeError):
                ctx.logger.error("Could not parse chat message content")
                return

    if not session_id or not user_query:
        ctx.logger.error("Missing session_id or user_query in chat message")
        return

    ctx.logger.info(f"User query for session {session_id}: {user_query}")

    await send_response_to_api(session_id, StatusMessage(message="Formulating strategy...", agent_name="Strategy Agent", progress=0.1, timestamp=datetime.now(timezone.utc).isoformat()).model_dump_json())

    strategy_agent_address = get_address("strategy_agent")
    if not strategy_agent_address:
        error_msg = "Strategy Agent not found. Please ensure it is running."
        await send_response_to_api(session_id, error_msg)
        return

    strategy_response, status = await ctx.send_and_receive(
        strategy_agent_address,
        StrategyRequest(user_query=user_query, session_id=session_id),
        StrategyResponse,
        timeout=240
    )

    if not (status.status == DeliveryStatus.DELIVERED and isinstance(strategy_response, StrategyResponse)):
        error_msg = "Strategy Agent did not provide a valid response."
        await send_response_to_api(session_id, error_msg)
    else:
        await send_response_to_api(session_id, strategy_response.strategy_description)

@command_proto.on_message(CommandMessage)
async def handle_command_message(ctx: Context, sender: str, msg: CommandMessage):
    ctx.logger.info(f"Received command from {sender}: {msg.command} for session {msg.session_id}")
    session_id = msg.session_id

    if msg.command == "execute":
        strategy_id = msg.payload.get("strategy_id")
        strategy_description = msg.payload.get("strategy_description")
        feePayer = msg.payload.get("feePayer")
        ctx.logger.info(f"Executing strategy {strategy_id}: {strategy_description} with fee payer {feePayer}")

        await send_response_to_api(session_id, StatusMessage(message="Preparing transaction...", agent_name="Execution Agent", progress=0.3, timestamp=datetime.now(timezone.utc).isoformat()).model_dump_json())

        execution_agent_address = get_address("execution_agent")
        if not execution_agent_address:
            await send_response_to_api(session_id, "Execution Agent not found.")
            return

        execution_result, exec_status = await ctx.send_and_receive(
            execution_agent_address,
            ExecuteStrategy(strategy=strategy_description, strategy_id=strategy_id, feePayer=feePayer),
            ExecutionResult,
            timeout=60
        )

        if not (exec_status.status == DeliveryStatus.DELIVERED and isinstance(execution_result, ExecutionResult)) or not execution_result.success:
            error_detail = execution_result.error if execution_result else (exec_status.detail if exec_status else 'timeout')
            await send_response_to_api(session_id, f"Strategy execution failed. Error: {error_detail}")
        elif execution_result.unsigned_tx_b64:
            proposal = UnsignedTransactionProposal(
                type="unsigned_transaction_proposal",
                unsigned_tx_b64=execution_result.unsigned_tx_b64,
                strategy_id=strategy_id
            )
            await send_response_to_api(session_id, proposal.model_dump_json())
            await send_response_to_api(session_id, StatusMessage(message="Transaction prepared. Waiting for user to sign...", agent_name="User Wallet", progress=0.5, timestamp=datetime.now(timezone.utc).isoformat()).model_dump_json())
        else:
            await send_response_to_api(session_id, f"Strategy {strategy_id} executed successfully. Hash: {execution_result.transaction_hash}")

    elif msg.command == "submit_signed_tx":
        signed_tx_b64 = msg.payload.get("signed_tx_b64")
        strategy_id = msg.payload.get("strategy_id")
        ctx.logger.info(f"Submitting signed tx for strategy {strategy_id}")

        await send_response_to_api(session_id, StatusMessage(message="Submitting signed transaction...", agent_name="Execution Agent", progress=0.7, timestamp=datetime.now(timezone.utc).isoformat()).model_dump_json())

        execution_agent_address = get_address("execution_agent")
        if not execution_agent_address:
            await send_response_to_api(session_id, "Execution Agent not found.")
            return

        execution_result, exec_status = await ctx.send_and_receive(
            execution_agent_address,
            SubmitSignedTransaction(signed_tx_b64=signed_tx_b64, strategy_id=strategy_id),
            ExecutionResult,
            timeout=60,
        )

        if not (exec_status.status == DeliveryStatus.DELIVERED and isinstance(execution_result, ExecutionResult)) or not execution_result.success:
            error_detail = execution_result.error if execution_result else (exec_status.detail if exec_status else 'timeout')
            await send_response_to_api(session_id, f"Transaction submission failed. Error: {error_detail}")
        else:
            await send_response_to_api(session_id, f"Transaction submitted successfully! Hash: {execution_result.transaction_hash}")

    else:
        await send_response_to_api(session_id, f"Unknown command: {msg.command}")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}")

agent.include(chat_proto, publish_manifest=True)
agent.include(command_proto)

if __name__ == "__main__":
    save_address("user_agent", agent.address)
    print(f"User agent running with address: {agent.address}")
    agent.run()