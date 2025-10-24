from uagents import Agent, Context, Protocol
from models import RiskRequest, RiskResponse
from address_book import save_address

# The Risk Agent
risk_agent = Agent(
    name="martian_risk_agent",
    port=8005, # Use a different port
    seed="martian_risk_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8005/submit"],
)

# Define a protocol for communication with the Risk Agent
risk_proto = Protocol("Risk", version="1.0")

@risk_proto.on_message(model=RiskRequest)
async def handle_risk_request(ctx: Context, sender: str, msg: RiskRequest):
    ctx.logger.info(f"Received risk request from {sender} for protocol {msg.protocol_name} and strategy: {msg.strategy_details}")

    # --- Simulated Risk Assessment (Replace with actual MeTTa/rule-based logic) ---
    risk_score = 0.5 # Default to medium risk
    assessment = "Medium risk: General assessment based on protocol type."

    if "Marinade" in msg.protocol_name or "Kamino" in msg.protocol_name:
        risk_score = 0.2
        assessment = "Low risk: Established protocol with good track record."
    elif "Drift" in msg.protocol_name:
        risk_score = 0.4
        assessment = "Medium-low risk: Well-known derivatives platform."
    elif "Sonic" in msg.protocol_name and "new" in msg.strategy_details.get("description", "").lower():
        risk_score = 0.7
        assessment = "Medium-high risk: Newer ecosystem, potential for higher volatility."
    elif "Degen" in msg.strategy_details.get("title", ""):
        risk_score = 0.9
        assessment = "High risk: Volatile assets and/or new protocols involved."
    # ---------------------------------------------------------------------------

    await ctx.send(sender, RiskResponse(risk_score=risk_score, assessment=assessment))

# Include the risk protocol
risk_agent.include(risk_proto)

if __name__ == "__main__":
    save_address("risk_agent", risk_agent.address)
    print(f"Risk Agent running with address: {risk_agent.address}")
    risk_agent.run()
