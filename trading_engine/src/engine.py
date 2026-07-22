from trading_engine.src.core.config import ExecutionMode, EngineConfig
from trading_engine.src.core.gateway.base import ExchangeGateway

class ExecutionEngine:
    """
    Independent trading engine. Consumes MechanismRecords and executes.
    """
    def __init__(self, config: EngineConfig, gateway: ExchangeGateway):
        self.config = config
        self.gateway = gateway
        
    def start(self):
        print(f"Starting engine in {self.config.mode} mode.")
        self.gateway.connect()
