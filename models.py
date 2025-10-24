from uagents import Model
from datetime import datetime, timezone

class StrategyRequest(Model):
    user_query: str
    session_id: str

class StrategyResponse(Model):
    strategy_description: str
    session_id: str

class ExecuteStrategy(Model):
    strategy: str
    strategy_id: str
    feePayer: str | None = None

class ExecutionResult(Model):
    success: bool
    transaction_hash: str | None = None
    error: str | None = None
    unsigned_tx_b64: str | None = None # New field for unsigned transaction

class StrategyProposal(Model):
    type: str = "strategy_proposal"
    title: str
    description: str
    details: dict[str, str] | None = None
    strategy_id: str

class CommandMessage(Model):
    command: str
    payload: dict | None = None
    session_id: str

class SubmitSignedTransaction(Model):
    signed_tx_b64: str
    strategy_id: str

class UnsignedTransactionProposal(Model):
    type: str = "unsigned_transaction_proposal"
    unsigned_tx_b64: str
    strategy_id: str

class ScoutRequest(Model):
    query: str # e.g., "Kamino USDC APY", "SOL price"

class ScoutResponse(Model):
    data: dict # e.g., {"kaminos_usdc_apy": "12%", "timestamp": "..."}
    error: str | None = None

class RiskRequest(Model):
    protocol_name: str
    strategy_details: dict # Details about the strategy to assess

class RiskResponse(Model):
    risk_score: float # e.g., 0.1 (low) to 1.0 (high)
    assessment: str # e.g., "Low risk due to audited protocol and high TVL"
    error: str | None = None

class StatusMessage(Model):
    type: str = "status_update"
    message: str
    agent_name: str | None = None
    progress: float | None = None # 0.0 to 1.0
    timestamp: str # Now a required string field