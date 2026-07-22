from abc import ABC, abstractmethod
from typing import Dict, Any

class ExchangeGateway(ABC):
    """Abstract interface for exchange connectivity."""
    
    @abstractmethod
    def connect(self):
        pass
        
    @abstractmethod
    def submit_order(self, order: Dict[str, Any]) -> str:
        """Submit order, return order ID."""
        pass
        
    @abstractmethod
    def get_balance(self) -> Dict[str, float]:
        pass
