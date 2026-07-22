# Trading Engine (Independent Execution Platform)

This is an independent trading application designed for the reliable execution of validated mechanisms from `Alpha_v6`. It is decoupled from the research platform to maintain scientific purity in research and operational stability in production.

## Core Design Philosophy
- **Deterministic Execution:** Supports `REPLAY` mode for full backtesting of production-ready execution logic.
- **Decoupled Architecture:** Strategies/Mechanisms are consumed as versioned `MechanismRecord` artifacts. The engine is agnostic of research-side code.
- **Operational Safety:** Strictly enforced `PAPER` vs `LIVE` modes, circuit breakers, and state persistence.

## Execution Modes
- `PAPER`: Real-time execution via simulated fill logic.
- `LIVE`: Real-time execution via exchange APIs.
- `REPLAY`: Deterministic simulation using historical market events.

## Directory Structure
- `src/core/gateway/`: Abstract interfaces for exchange connectivity.
- `src/core/execution/`: Core trading logic (order management, risk checks).
- `data/state/`: Persistent position and order state for crash recovery.
- `logs/`: Operational and audit logs.

## Advancement Gates
- **L6A (Infrastructure Certification):** Focuses on system uptime, error recovery, and auditability.
- **L6B (Market Validation):** Focuses on empirical performance, regime coverage, and trade statistics.
