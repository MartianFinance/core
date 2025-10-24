from uagents import Agent, Context, Protocol
from models import ExecuteStrategy, ExecutionResult, SubmitSignedTransaction
from address_book import save_address

import os
import httpx
import base64

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# --- Onchain Service Configuration ---
ONCHAIN_SERVICE_URL = os.getenv("ONCHAIN_SERVICE_URL", "http://localhost:3001")
# -------------------------------------

# The Execution Agent
execution_agent = Agent(
    name="execution_agent",
    port=8003,
    seed="execution_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8003/submit"],
)

# Define the protocol for execution
execution_proto = Protocol("Execution", version="1.0")

@execution_proto.on_message(model=ExecuteStrategy)
async def handle_execute_strategy(ctx: Context, sender: str, msg: ExecuteStrategy):
    ctx.logger.info(f"Received strategy execution request from {sender}: {msg.strategy} (ID: {msg.strategy_id})")

    # In the future, this is where the Sanctum Gateway integration will go.
    # For now, we'll simulate a successful execution.
    ctx.logger.info("Executing real Sanctum Gateway integration...")

    try:
        # Call the Node.js Onchain service to build and optimize the transaction
        gateway_service_payload = {
            "strategyId": msg.strategy_id,
            "strategyDescription": msg.strategy,
            "feePayer": msg.feePayer,
        }
        
        async with httpx.AsyncClient() as client:
            service_response = await client.post(
                f"{ONCHAIN_SERVICE_URL}/build-gateway-transaction",
                json=gateway_service_payload,
                timeout=30.0
            )
            service_response.raise_for_status() # Raise an exception for 4xx/5xx responses
            service_data = service_response.json()

        if service_data.error:
            raise Exception(f"Onchain service build error: {service_data.error}")

        optimized_tx_b64 = service_data.optimizedTxB64
        
        # Return the unsigned transaction to the User Agent
        await ctx.send(sender, ExecutionResult(
            success=True,
            unsigned_tx_b64=optimized_tx_b64
        ))

    except httpx.HTTPStatusError as e:
        ctx.logger.error(f"HTTP error during Onchain service build: {e.response.status_code} - {e.response.text}")
        await ctx.send(sender, ExecutionResult(
            success=False,
            error=f"HTTP error during Onchain service build: {e.response.status_code} - {e.response.text}"
        ))
    except httpx.RequestError as e:
        ctx.logger.error(f"Network error during Onchain service build: {e}")
        await ctx.send(sender, ExecutionResult(
            success=False,
            error=f"Network error during Onchain service build: {e}"
        ))
    except Exception as e:
        ctx.logger.error(f"Error during Onchain service build: {e}")
        await ctx.send(sender, ExecutionResult(
            success=False,
            error=f"Error during Onchain service build: {e}"
        ))

@execution_proto.on_message(model=SubmitSignedTransaction)
async def handle_submit_signed_transaction(ctx: Context, sender: str, msg: SubmitSignedTransaction):
    ctx.logger.info(f"Received signed transaction for submission (ID: {msg.strategy_id})")

    try:
        # Call the Node.js Onchain service to send the signed transaction
        gateway_service_payload = {
            "signedTxB64": msg.signed_tx_b64,
            "strategyId": msg.strategy_id,
        }

        async with httpx.AsyncClient() as client:
            service_response = await client.post(
                f"{ONCHAIN_SERVICE_URL}/send-signed-transaction",
                json=gateway_service_payload,
                timeout=30.0
            )
            service_response.raise_for_status() # Raise an exception for 4xx/5xx responses
            service_data = service_response.json()

        if service_data.error:
            raise Exception(f"Onchain service send error: {service_data.error}")

        transaction_hash = service_data.transactionHash

        await ctx.send(sender, ExecutionResult(
            success=True,
            transaction_hash=transaction_hash
        ))

    except httpx.HTTPStatusError as e:
        ctx.logger.error(f"HTTP error during Onchain service send: {e.response.status_code} - {e.response.text}")
        await ctx.send(sender, ExecutionResult(
            success=False,
            error=f"HTTP error during Onchain service send: {e.response.status_code} - {e.response.text}"
        ))
    except httpx.RequestError as e:
        ctx.logger.error(f"Network error during Onchain service send: {e}")
        await ctx.send(sender, ExecutionResult(
            success=False,
            error=f"Network error during Onchain service send: {e}"
        ))
    except Exception as e:
        ctx.logger.error(f"Error during Onchain service send: {e}")
        await ctx.send(sender, ExecutionResult(
            success=False,
            error=f"Error during Onchain service send: {e}"
        ))

# Include the protocol
execution_agent.include(execution_proto)

if __name__ == "__main__":
    save_address("execution_agent", execution_agent.address)
    print(f"Execution Agent running with address: {execution_agent.address}")
    execution_agent.run()