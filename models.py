from uagents import Model

class StrategyRequest(Model):
    user_query: str
    session_id: str

class StrategyResponse(Model):
    strategy_description: str
    session_id: str
