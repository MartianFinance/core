from uagents import Agent, Context, Protocol
from models import ScoutRequest, ScoutResponse
from address_book import save_address
import json
import time
import httpx

# The Scout Agent
scout_agent = Agent(
    name="martian_scout_agent",
    port=8004, # Use a different port
    seed="martian_scout_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8004/submit"],
)

ONCHAIN_SERVICE_URL = "http://localhost:3001"

# Define a protocol for communication with the Scout Agent
scout_proto = Protocol("Scout", version="1.0")

@scout_proto.on_message(model=ScoutRequest)
async def handle_scout_request(ctx: Context, sender: str, msg: ScoutRequest):
    ctx.logger.info(f"Received scout request from {sender}: {msg.query}")

    simulated_data = {
        "timestamp": int(time.time()),
        "opportunities": {
            "kaminos_usdc_apy": "12.5%",
            "drift_stablecoin_apy": "11.2%",
            "sonic_usdc_sol_apy": "16.8%",
        },
        "network_health": {
            "solana_congestion": "moderate",
            "solana_tps": 2500,
            "sonic_congestion": "low",
        },
        "prices": {
            "SOL": 150.00,
            "USDC": 1.00,
            "USDT": 1.00,
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ONCHAIN_SERVICE_URL}/market-data")
            response.raise_for_status()
            market_data = response.json()
            # Merge the real-time data with the simulated data
            simulated_data["opportunities"].update(market_data)
    except httpx.RequestError as e:
        ctx.logger.error(f"Error fetching market data from onchain-service: {e}")

    await ctx.send(sender, ScoutResponse(data=simulated_data))

# Include the scout protocol
scout_agent.include(scout_proto)

if __name__ == "__main__":
    save_address("scout_agent", scout_agent.address)
    print(f"Scout Agent running with address: {scout_agent.address}")
    scout_agent.run()
