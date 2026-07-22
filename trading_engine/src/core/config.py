from dataclasses import dataclass
from enum import Enum

class ExecutionMode(Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"
    REPLAY = "REPLAY"

@dataclass
class EngineConfig:
    mode: ExecutionMode = ExecutionMode.PAPER
    target_vol: float = 0.12
    max_leverage: float = 2.0
