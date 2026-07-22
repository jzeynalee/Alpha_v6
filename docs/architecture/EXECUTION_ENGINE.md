# Execution Engine Architecture

The `ExecutionEngine` is the sole executable trading component, mediating between validated `MechanismRecord` objects and live/simulated market data.

## Core Design Philosophy
- **Deterministic:** All execution paths are reproducible via `REPLAY` mode.
- **Separation of Concerns:** Strategies do not know about exchanges; Gateways do not know about strategies.
- **Scientific Gating:** L6 is split into Infrastructure Certification (L6A) and Market Validation (L6B).

## Architectural Components

| Component | Responsibility |
| :--- | :--- |
| **StrategyManager** | Mechanism lifecycle, weight allocation. |
| **SignalRouter** | Mechanism output → Position Intent. |
| **PortfolioManager** | Kelly sizing, risk parity, exposure limits. |
| **RiskEngine** | Circuit breakers, VaR, emergency shutdown. |
| **ExecutionPolicy** | Latency/Slippage modeling, retry logic. |
| **ExchangeGateway** | Abstract interface for PAPER/LIVE execution. |
| **OrderManager** | Lifecycle management, state transitions. |
| **StateStore** | Restart recovery, persistent position state. |
| **HealthMonitor** | Infrastructure health, drift, heartbeat. |
| **AuditLogger** | Reproducible trail of every decision/fill. |

## Execution Modes
- `PAPER`: Real-time execution via simulated fill logic.
- `LIVE`: Real-time execution via exchange APIs.
- `REPLAY`: Deterministic simulation using historical market events through the production execution pipeline.

## L6 Advancement Gates
- **L6A (Infrastructure Certification):** Focuses on system uptime, error recovery, and auditability.
- **L6B (Market Validation):** Focuses on empirical performance, regime coverage, and trade statistics.
