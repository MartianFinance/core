from uagents import Agent, Context, Model

# --- Message Models for Control ---

class StartMessage(Model):
    """Message to start the agent's trading activity."""
    pass

class StopMessage(Model):
    """Message to stop the agent's trading activity."""
    pass

class StatusRequest(Model):
    """Message to request the agent's current status."""
    pass

class StatusResponse(Model):
    """Message containing the agent's current status."""
    active: bool
    pnl: float
    trades_executed: int

# --- Agent Definition ---

# This will be our core Martian agent
agent = Agent(
    name="martian_arbitrage_agent",
    port=8001,
    seed="martian_arbitrage_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8001/submit"],
)

# --- Agent State ---

# In-memory state for the agent.
# In a real application, this would be persisted using agent.storage
agent_state = {
    "active": False,
    "pnl": 0.0,
    "trades_executed": 0,
}

# --- Message Handlers for CLI and API ---

@agent.on_message(model=StartMessage)
async def start_agent(ctx: Context, sender: str, _msg: StartMessage):
    ctx.logger.info(f"Received start command from {sender}")
    if not agent_state["active"]:
        agent_state["active"] = True
        ctx.logger.info("Agent is now ACTIVE and monitoring for arbitrage opportunities.")
    else:
        ctx.logger.info("Agent is already active.")

@agent.on_message(model=StopMessage)
async def stop_agent(ctx: Context, sender: str, _msg: StopMessage):
    ctx.logger.info(f"Received stop command from {sender}")
    if agent_state["active"]:
        agent_state["active"] = False
        ctx.logger.info("Agent has been STOPPED.")
    else:
        ctx.logger.info("Agent is already stopped.")

@agent.on_message(model=StatusRequest)
async def get_status(ctx: Context, sender: str, _msg: StatusRequest):
    ctx.logger.info(f"Received status request from {sender}")
    await ctx.send(sender, StatusResponse(
        active=agent_state["active"],
        pnl=agent_state["pnl"],
        trades_executed=agent_state["trades_executed"],
    ))

# --- Core Arbitrage Logic ---

@agent.on_interval(period=15.0)
async def monitor_dexs(ctx: Context):
    if not agent_state["active"]:
        # Do nothing if the agent is not active
        return

    ctx.logger.info("Checking for arbitrage opportunities...")
    # In the future, this is where the logic will go:
    # 1. Fetch prices from Raydium, Orca, SegaSwap.
    # 2. Analyze for profitable arbitrage opportunities.
    # 3. If opportunity found:
    #    a. Construct transactions.
    #    b. Use Sanctum Gateway to build and send the transaction bundle.
    #    c. Update P&L and trade count.
    pass

if __name__ == "__main__":
    agent.run()
