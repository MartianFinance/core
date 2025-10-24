import os
import google.generativeai as genai
from dotenv import load_dotenv
from uagents import Agent, Context, Model, Protocol
import json
import re
import asyncio

# Load environment variables from .env file
load_dotenv()

from uagents_core.contrib.protocols.chat import TextContent, ChatMessage
from uagents_core.types import DeliveryStatus
from datetime import datetime, timezone
from uuid import uuid4

from models import StrategyRequest, StrategyResponse, StrategyProposal, ScoutRequest, ScoutResponse, RiskRequest, RiskResponse
from address_book import save_address, get_address

# The Strategy Agent
strategy_agent = Agent(
    name="martian_strategy_agent",
    port=8002,
    seed="martian_strategy_agent_secret_seed_phrase",
    endpoint=["http://127.0.0.1:8002/submit"],
)

# --- Gemini API Configuration ---
try:
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
except AttributeError:
    print("ERROR: Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
    exit(1)

gemini = genai.GenerativeModel('gemini-2.5-flash')
# --------------------------------

# Define a protocol for communication with the Strategy Agent
strategy_comm_proto = Protocol("StrategyComm", version="1.0")

async def query_scout_agent(ctx: Context, user_query: str):
    scout_agent_address = get_address("scout_agent")
    if not scout_agent_address:
        ctx.logger.error("Scout Agent address not found.")
        return None, "Scout Agent address not found."
    
    ctx.logger.info(f"Querying Scout Agent at {scout_agent_address} for opportunities...")
    scout_response, status = await ctx.send_and_receive(
        scout_agent_address,
        ScoutRequest(query=user_query),
        ScoutResponse,
        timeout=30
    )
    
    if not (status.status == DeliveryStatus.DELIVERED and isinstance(scout_response, ScoutResponse)):
        error_detail = status.detail if status else 'timeout'
        ctx.logger.error(f"Failed to get opportunities from Scout Agent: {error_detail}")
        return None, f"Failed to get opportunities from Scout Agent: {error_detail}"
        
    return scout_response.data, None

async def query_risk_agent(ctx: Context, user_query: str):
    risk_agent_address = get_address("risk_agent")
    if not risk_agent_address:
        ctx.logger.error("Risk Agent address not found.")
        return None, "Risk Agent address not found."

    # The risk agent is queried with only the user query for a general assessment.
    # The dependency on scout agent results is removed to allow for concurrent execution.
    strategy_details_for_risk = {"user_query": user_query}
    protocol_name_for_risk = "General"

    ctx.logger.info(f"Querying Risk Agent at {risk_agent_address} for a general assessment...")
    risk_response, status = await ctx.send_and_receive(
        risk_agent_address,
        RiskRequest(protocol_name=protocol_name_for_risk, strategy_details=strategy_details_for_risk),
        RiskResponse,
        timeout=30
    )

    if not (status.status == DeliveryStatus.DELIVERED and isinstance(risk_response, RiskResponse)):
        error_detail = status.detail if status else 'timeout'
        ctx.logger.error(f"Failed to get risk assessment from Risk Agent: {error_detail}")
        return None, f"Failed to get risk assessment from Risk Agent: {error_detail}"
        
    return {"score": risk_response.risk_score, "assessment": risk_response.assessment}, None

@strategy_comm_proto.on_message(model=StrategyRequest)
async def handle_strategy_request(ctx: Context, sender: str, msg: StrategyRequest):
    ctx.logger.info(f"Received strategy request from {sender}: {msg.user_query} (Session: {msg.session_id})")

    # 1. Concurrently query Scout and Risk Agents
    ctx.logger.info("Querying Scout and Risk agents concurrently...")
    scout_task = query_scout_agent(ctx, msg.user_query)
    risk_task = query_risk_agent(ctx, msg.user_query)

    results = await asyncio.gather(scout_task, risk_task, return_exceptions=True)
    
    current_opportunities, scout_error = (None, str(results[0])) if isinstance(results[0], Exception) else results[0]
    risk_assessment, risk_error = (None, str(results[1])) if isinstance(results[1], Exception) else results[1]

    if scout_error:
        ctx.logger.error(f"Scout Agent query failed: {scout_error}")
        await ctx.send(sender, StrategyResponse(strategy_description=f"Error from Scout Agent: {scout_error}", session_id=msg.session_id))
        return
    ctx.logger.info(f"Received opportunities from Scout Agent: {json.dumps(current_opportunities, indent=2)}")

    if risk_error:
        ctx.logger.error(f"Risk Agent query failed: {risk_error}")
        await ctx.send(sender, StrategyResponse(strategy_description=f"Error from Risk Agent: {risk_error}", session_id=msg.session_id))
        return
    ctx.logger.info(f"Received risk assessment from Risk Agent: {json.dumps(risk_assessment, indent=2)}")

    # 3. Generate strategy using Gemini with real-time data and risk assessment
    prompt = f"""You are an expert DeFi strategist for the 'Martian' autonomous yield optimizer.
Your task is to analyze a user's query and recommend one of the following three strategies.
Provide only the single most appropriate strategy description as your response, formatted as a JSON object.

The JSON object should have the following structure:
{{
  "type": "strategy_proposal",
  "title": "<Strategy Title>",
  "description": "<Brief description of the strategy>",
  "details": {{
    "Projected APY": "<APY>%",
    "Risk Level": "<Low/Medium/High>",
    "Protocols": "<Comma separated list of protocols>"
  }},
  "strategy_id": "<Unique ID for the strategy, e.g., a UUID>"
}}

Here are the available strategies:

###
Strategy: Low-Risk Staking
Action: Stake SOL on a well-established platform like Marinade or Jito.
Projected APY: ~7-8%
Reasoning: This is a mature and audited liquid staking solution, offering stable returns with minimal risk.
###

###
Strategy: Medium-Risk Liquidity Provision
Action: Provide liquidity to a stablecoin pair (e.g., USDC-USDT) on a major DEX like Orca or Raydium.
Projected APY: ~10-15%
Reasoning: Offers higher yields than simple staking by earning trading fees, with low impermanent loss risk due to the stable nature of the assets.
###

###
Strategy: High-Risk "Degen" Farming
Action: Provide liquidity to a new, volatile pair (e.g., SOL-WIF, SOL-BONK) on a platform like Raydium.
Projected APY: 50-200%+ (highly variable)
Reasoning: Potential for very high rewards from trading fees and farm incentives, but carries significant risk of impermanent loss and token price volatility.
###

User Query: "{msg.user_query}"

Current Real-time Opportunities from Scout Agent:
{json.dumps(current_opportunities, indent=2)}

Risk Assessment from Risk Agent:
{json.dumps(risk_assessment, indent=2)}

Based on the user's query, the current real-time opportunities, and the risk assessment, which strategy is the most appropriate?"""

    try:
        response = gemini.generate_content(prompt)
        strategy_json_str = response.text
        
        # Extract JSON from markdown code block if present
        match = re.search(r"```json\n(.*?)""```", strategy_json_str, re.DOTALL)
        if match:
            strategy_json_str = match.group(1).strip()

        # Attempt to parse the JSON response
        strategy_data = json.loads(strategy_json_str)
        
        # Validate against the StrategyProposal model
        strategy_data["details"] = strategy_data.get("details") or {}
        strategy_data["title"] = strategy_data.get("title") or "Untitled Strategy Proposal"
        strategy_data["description"] = strategy_data.get("description") or "No description provided."
        strategy_proposal = StrategyProposal(**strategy_data)
        
        ctx.logger.info(f"Sending strategy proposal: {strategy_proposal.model_dump_json()}")

        # Send the strategy proposal back to the sender (User Agent)
        await ctx.send(sender, StrategyResponse(
            strategy_description=strategy_proposal.model_dump_json(), # Send JSON string
            session_id=msg.session_id
        ))

    except json.JSONDecodeError as e:
        ctx.logger.error(f"Error parsing Gemini JSON response: {e}\nResponse: {strategy_json_str}")
        await ctx.send(sender, StrategyResponse(
            strategy_description="I was unable to generate a valid strategy proposal due to a parsing error.",
            session_id=msg.session_id
        ))
    except Exception as e:
        ctx.logger.error(f"Error calling Gemini API or validating strategy: {e}")
        await ctx.send(sender, StrategyResponse(
            strategy_description="I was unable to determine a strategy at this time.",
            session_id=msg.session_id
        ))


# Include the new strategy communication protocol
strategy_agent.include(strategy_comm_proto)

if __name__ == "__main__":
    save_address("strategy_agent", strategy_agent.address)
    print(f"Strategy Agent running with address: {strategy_agent.address}")
    strategy_agent.run()

