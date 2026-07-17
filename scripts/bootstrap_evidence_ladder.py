# scripts/bootstrap_evidence_ladder.py
"""
Bootstrap the Evidence Ladder with all priority alpha families from the
2026-06-26 Alpha Research Roadmap v2.

Seeds the ladder with:
  - Priority 1: PositioningAlpha (OI/Funding/Positioning)
  - Priority 2: CrossSectionAlpha (Cross-Sectional Momentum)
  - Priority 3: ExpansionAlpha (Compression → Expansion)
  - Priority 4: LiquidationAlpha
  - Priority 5: MicrostructureAlpha (Order Flow / Market Microstructure)
  - Priority 6: Context Engine (Multi-Timeframe Context)
  - Priority 7: RelativeValueAlpha (Statistical Relative Value)
  - Priority 8: Feature Library (Feature Discovery)
  - Priority 9: ML Alpha (Machine Learning)
  - Priority 10: Execution Research
  - Priority 11: Portfolio Construction
  - Priority 12: Indicator Research (archived — low priority)

Each priority seeds 2-5 initial hypotheses at L0, implementing the
specific research topics listed in the roadmap.

Current validated alpha families are annotated with their current status.

Additionally, the validated mechanisms (M001-M005) and the negative
knowledge entries (NEG001-NEG016) from DISCOVERIES.md are seeded with
their current evidence levels, ensuring the ladder mirrors the full
research state.

Usage
-----
    python scripts/bootstrap_evidence_ladder.py
    python scripts/bootstrap_evidence_ladder.py --output data/experiments/evidence_ladder.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.evidence_ladder import EvidenceLadder, EvidenceLevel, HypothesisRecord


# ----------------------------------------------------------------------
# Helper: register a hypothesis at a specific evidence level
# ----------------------------------------------------------------------
def _register(ladder: EvidenceLadder, **kwargs) -> None:
    """Create and register a HypothesisRecord, optionally archived."""
    record = HypothesisRecord(
        hypothesis_id=kwargs["id"],
        name=kwargs["name"],
        family=kwargs.get("family", ""),
        description=kwargs.get("description", ""),
        economic_rationale=kwargs.get("rationale", ""),
        evidence_level=kwargs.get("evidence_level", EvidenceLevel.L0),
        symbols=kwargs.get("symbols", []),
        timeframes=kwargs.get("timeframes", []),
        tags=kwargs.get("tags", []),
        archived=kwargs.get("archived", False),
    )
    ladder.register(record)


# ----------------------------------------------------------------------
# Priority seeders (unchanged logic)
# ----------------------------------------------------------------------
def seed_priority_1_positioning(ladder: EvidenceLadder) -> None:
    """Priority 1: Open Interest + Funding + Positioning ★★★★★"""
    topics = [
        {
            "id": "pos_001",
            "name": "OI Expansion Breakout",
            "description": "Rising OI + rising price = trend confirmation. "
            "OI expanding faster than 20-day average while price breaks N-bar high.",
            "rationale": "New money entering the market creates sustained directional "
            "moves. OI expansion confirms the move is driven by positioning, not noise.",
        },
        {
            "id": "pos_002",
            "name": "OI Divergence Reversal",
            "description": "Price up + OI down = weakening trend. "
            "Detect divergence between price direction and OI change for reversal signals.",
            "rationale": "When price rises but OI falls, existing positions are being "
            "closed, not new ones opened. The move lacks fresh conviction and is likely to reverse.",
        },
        {
            "id": "pos_003",
            "name": "Funding Rate Acceleration",
            "description": "Funding rate 2nd derivative (acceleration) as a crowding signal. "
            "Rapidly increasing funding cost → crowded trade → mean-reversion opportunity.",
            "rationale": "Funding rate itself is slow; its acceleration reveals when "
            "positioning cost is changing rapidly — a leading indicator of squeeze conditions.",
        },
        {
            "id": "pos_004",
            "name": "Funding Divergence Cross-Asset",
            "description": "Funding rate divergence between BTC and ETH as a "
            "relative value signal. Wide funding spread → pair trade opportunity.",
            "rationale": "When BTC funding is high but ETH funding is low (or vice versa), "
            "capital rotates. The divergence predicts which asset will outperform short-term.",
        },
        {
            "id": "pos_005",
            "name": "Liquidation Cascade Detector",
            "description": "Detect cascade conditions: high OI + extreme funding + "
            "price approaching liquidation clusters. Anticipate forced selling/buying waves.",
            "rationale": "Liquidation cascades are the most predictable forced-order-flow "
            "events in crypto. Positioning extremes + price approach = high-probability cascade setup.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="PositioningAlpha",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["15", "60"],
            tags=["open_interest", "funding", "positioning", "priority_1"],
        )
        ladder.register(record)


def seed_priority_2_cross_section(ladder: EvidenceLadder) -> None:
    """Priority 2: Cross-Sectional Momentum ★★★★★"""
    topics = [
        {
            "id": "cs_001",
            "name": "Cross-Sectional Relative Strength",
            "description": "Rank 30-100 assets by N-day return. Long top quintile, "
            "short bottom quintile. Rebalance weekly.",
            "rationale": "Cross-sectional momentum is one of the most persistent "
            "factors across all asset classes. Crypto's high dispersion amplifies the effect.",
        },
        {
            "id": "cs_002",
            "name": "Sector Rotation Detector",
            "description": "Detect when capital rotates between L1, DeFi, Meme, "
            "and Stable sectors. Lead-lag relationships signal rotation.",
            "rationale": "Crypto sectors exhibit clear lead-lag patterns. When L1s "
            "rally first, DeFi follows 1-2 weeks later. This rotation is predictable.",
        },
        {
            "id": "cs_003",
            "name": "Market Breadth Indicator",
            "description": "Percentage of assets above their N-day moving average. "
            "Breadth thrusts and divergences signal regime changes.",
            "rationale": "Market breadth reveals whether a move is broad-based or "
            "narrow. Narrow rallies are fragile; broad rallies are durable.",
        },
        {
            "id": "cs_004",
            "name": "Cross-Sectional Dispersion",
            "description": "Cross-sectional standard deviation of returns. "
            "High dispersion = good for stock-picking; low dispersion = macro-driven.",
            "rationale": "When dispersion is high, cross-sectional strategies thrive. "
            "When low, macro factors dominate. Adapting strategy weight to dispersion "
            "improves risk-adjusted returns.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="CrossSectionAlpha",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            timeframes=["60", "240"],
            tags=["cross_section", "momentum", "relative_strength", "priority_2"],
        )
        ladder.register(record)


def seed_priority_3_expansion(ladder: EvidenceLadder) -> None:
    """Priority 3: Compression → Expansion ★★★★☆"""
    topics = [
        {
            "id": "exp_001",
            "name": "ATR Compression Breakout",
            "description": "ATR at N-period low → expect expansion. "
            "Enter on breakout of compression range with volume confirmation.",
            "rationale": "Volatility is mean-reverting. Periods of abnormally low "
            "volatility are followed by periods of high volatility. The direction "
            "of the expansion is forecastable from the preceding trend and volume.",
        },
        {
            "id": "exp_002",
            "name": "Bollinger Squeeze with Entropy Filter",
            "description": "Bollinger Band width at percentile low + low entropy → "
            "high-confidence expansion signal. Direction from regime context.",
            "rationale": "The Bollinger squeeze is a classic setup, but many squeezes "
            "fail. Adding an entropy filter removes low-conviction squeezes where "
            "the market lacks directional disagreement.",
        },
        {
            "id": "exp_003",
            "name": "Fractal Dimension Regime Switch",
            "description": "Fractal dimension crossing threshold signals "
            "trending → mean-reverting (or vice versa) regime change.",
            "rationale": "Market efficiency varies over time. Fractal dimension "
            "measures the 'roughness' of price series. A drop below 0.4 signals "
            "a trending regime; above 0.6 signals mean-reversion.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="ExpansionAlpha",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["15", "60"],
            tags=["volatility", "compression", "expansion", "priority_3"],
        )
        ladder.register(record)


def seed_priority_4_liquidation(ladder: EvidenceLadder) -> None:
    """Priority 4: Liquidation Research ★★★★☆"""
    topics = [
        {
            "id": "liq_001",
            "name": "Liquidation Cluster Bounce",
            "description": "Price approaching large liquidation cluster → "
            "high probability of bounce (cascade exhausts) or breakthrough "
            "(cascade accelerates). Trade the reaction.",
            "rationale": "Liquidation clusters represent forced orders. When "
            "price reaches a cluster, either it exhausts (reversal) or cascades "
            "(continuation). The reaction is tradeable with tight stops.",
        },
        {
            "id": "liq_002",
            "name": "Long Squeeze Detector",
            "description": "High long OI + negative funding + price breaking down "
            "= long squeeze in progress. Short entry on breakdown confirmation.",
            "rationale": "Long squeezes occur when over-leveraged longs are forced "
            "to sell. The setup is identifiable before the cascade accelerates.",
        },
        {
            "id": "liq_003",
            "name": "Short Squeeze Detector",
            "description": "High short OI + positive funding + price breaking up "
            "= short squeeze in progress. Long entry on breakout confirmation.",
            "rationale": "Short squeezes are sharper and faster than long squeezes. "
            "The asymmetric nature of forced short covering creates explosive moves.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="LiquidationAlpha",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["15", "60"],
            tags=["liquidation", "squeeze", "cascade", "priority_4"],
        )
        ladder.register(record)


def seed_priority_5_microstructure(ladder: EvidenceLadder) -> None:
    """Priority 5: Order Flow / Market Microstructure ★★★★☆"""
    topics = [
        {
            "id": "micro_001",
            "name": "LOB Imbalance Signal",
            "description": "Limit order book imbalance (bid size / ask size) "
            "predicts short-term price direction. Threshold-based entries.",
            "rationale": "The limit order book reveals resting liquidity. A "
            "persistent imbalance in one direction signals informed order flow "
            "and predicts the next few bars' direction.",
        },
        {
            "id": "micro_002",
            "name": "CVD Divergence",
            "description": "Cumulative Volume Delta diverging from price = "
            "order flow not confirming price. Reversal signal.",
            "rationale": "When price rises but CVD is flat or falling, the "
            "buying is passive (limit orders being hit). True demand shows in "
            "aggressive buying, captured by positive CVD divergence.",
        },
        {
            "id": "micro_003",
            "name": "Aggressive Buying/Selling Imbalance",
            "description": "Ratio of aggressive buy volume to aggressive sell "
            "volume over rolling window. Extreme values predict mean-reversion.",
            "rationale": "Aggressive orders (market orders) consume liquidity "
            "and move price. Extreme imbalances exhaust quickly, creating "
            "short-term reversal opportunities.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="MicrostructureAlpha",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT"],
            timeframes=["5", "15"],
            tags=["order_flow", "microstructure", "LOB", "priority_5"],
        )
        ladder.register(record)


def seed_priority_6_mtf_context(ladder: EvidenceLadder) -> None:
    """Priority 6: Multi-Timeframe Context ★★★☆☆"""
    topics = [
        {
            "id": "mtf_001",
            "name": "HTF Volatility Context Filter",
            "description": "Use higher-timeframe volatility regime to adjust "
            "lower-timeframe signal thresholds. Reduce sensitivity in high HTF vol.",
            "rationale": "Higher-timeframe context determines the 'weather' for "
            "lower-timeframe trading. In stormy weather (high HTF vol), reduce "
            "position size and tighten stops.",
        },
        {
            "id": "mtf_002",
            "name": "HTF Trend Age Filter",
            "description": "Measure how long the current HTF trend has persisted. "
            "Aged trends (>N bars) have higher reversal probability at LTF extremes.",
            "rationale": "Trends have a lifecycle. Young trends tend to continue; "
            "aged trends are vulnerable to reversal. Trend age is a powerful "
            "context variable for counter-trend strategies.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="ContextEngine",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["15", "60", "240"],
            tags=["multi_timeframe", "context", "priority_6"],
        )
        ladder.register(record)


def seed_priority_7_relative_value(ladder: EvidenceLadder) -> None:
    """Priority 7: Statistical Relative Value ★★★☆☆"""
    topics = [
        {
            "id": "rv_001",
            "name": "BTC-ETH Cointegration Pair",
            "description": "Trade the BTC-ETH spread when it deviates from "
            "the cointegration equilibrium. Mean-reversion on the spread.",
            "rationale": "BTC and ETH share a long-run equilibrium relationship. "
            "Deviations from this equilibrium are temporary and mean-revert, "
            "offering a market-neutral alpha source.",
        },
        {
            "id": "rv_002",
            "name": "BTC Dominance Effect",
            "description": "BTC dominance rising → altcoins underperform. "
            "Use dominance trend to adjust cross-sectional weights.",
            "rationale": "BTC dominance is the most important macro variable "
            "for altcoin relative performance. When dominance is rising, "
            "reducing altcoin exposure improves risk-adjusted returns.",
        },
        {
            "id": "rv_003",
            "name": "Sector Spread Z-Score",
            "description": "Z-score of sector index relative to BTC. "
            "Extreme z-scores predict sector mean-reversion vs BTC.",
            "rationale": "Crypto sectors oscillate around their relative value "
            "to BTC. Extreme over/underperformance relative to BTC is temporary.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="RelativeValueAlpha",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["60", "240"],
            tags=["relative_value", "cointegration", "spread", "priority_7"],
        )
        ladder.register(record)


def seed_priority_8_feature_discovery(ladder: EvidenceLadder) -> None:
    """Priority 8: Feature Discovery ★★★☆☆"""
    topics = [
        {
            "id": "feat_001",
            "name": "Automated Feature Importance Ranking",
            "description": "Run SHAP + permutation importance on 220+ features "
            "across multiple regimes. Identify stable predictive features.",
            "rationale": "Not all features are equally useful. Systematic "
            "importance ranking across regimes identifies the small subset "
            "of features that consistently predict returns.",
        },
        {
            "id": "feat_002",
            "name": "Mutual Information Feature Selection",
            "description": "Use mutual information with forward return as "
            "feature selection criterion. Prioritize non-linear relationships.",
            "rationale": "Linear correlation misses non-linear predictive "
            "relationships. Mutual information captures any dependency, "
            "including the complex interactions common in financial data.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="FeatureLibrary",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT"],
            timeframes=["15", "60"],
            tags=["feature_discovery", "SHAP", "mutual_information", "priority_8"],
        )
        ladder.register(record)


def seed_priority_9_ml(ladder: EvidenceLadder) -> None:
    """Priority 9: Machine Learning ★★☆☆☆"""
    topics = [
        {
            "id": "ml_001",
            "name": "LightGBM Expected Return Predictor",
            "description": "Train LightGBM to predict forward N-bar return. "
            "Use probability calibration for position sizing. Never search "
            "directly for BUY/SELL.",
            "rationale": "ML models can capture non-linear interactions that "
            "linear models miss. But they must predict expected return, not "
            "direction — the distinction is critical for realistic backtests.",
        },
        {
            "id": "ml_002",
            "name": "Meta-Labeling for Trade Filtering",
            "description": "Train a binary classifier to predict whether a "
            "trade will be profitable, given the entry signal. Use to filter "
            "existing alpha signals.",
            "rationale": "Meta-labeling separates the 'what to trade' from "
            "'when to trade'. A model trained on trade outcomes can filter "
            "false signals from any alpha source without overfitting.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="MachineLearningAlpha",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT"],
            timeframes=["15", "60"],
            tags=["machine_learning", "lightgbm", "meta_labeling", "priority_9"],
        )
        ladder.register(record)


def seed_priority_10_execution(ladder: EvidenceLadder) -> None:
    """Priority 10: Execution Research ★★☆☆☆"""
    topics = [
        {
            "id": "exec_001",
            "name": "Adaptive Exit: Maker vs Taker",
            "description": "Compare maker (limit order) vs taker (market order) "
            "exit performance. Adapt exit method based on spread and urgency.",
            "rationale": "Using limit orders for exits saves the spread but "
            "risks non-execution. A dynamic choice based on spread width and "
            "signal urgency optimizes the trade-off.",
        },
        {
            "id": "exec_002",
            "name": "Dynamic Holding Time",
            "description": "Adjust holding period based on volatility regime. "
            "Longer holds in low vol, shorter in high vol.",
            "rationale": "The optimal holding period varies with market conditions. "
            "In low vol, edges persist longer; in high vol, they decay faster.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="ExecutionResearch",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT"],
            timeframes=["5", "15"],
            tags=["execution", "maker_taker", "adaptive", "priority_10"],
        )
        ladder.register(record)


def seed_priority_11_portfolio(ladder: EvidenceLadder) -> None:
    """Priority 11: Portfolio Construction ★★☆☆☆"""
    topics = [
        {
            "id": "port_001",
            "name": "Kelly vs Half-Kelly Comparison",
            "description": "Empirically compare full Kelly, half-Kelly, and "
            "volatility-targeted sizing across the alpha stream portfolio.",
            "rationale": "Full Kelly maximizes growth but is volatile. Half-Kelly "
            "provides 75% of the growth with half the volatility. Empirical "
            "comparison guides the production sizing choice.",
        },
        {
            "id": "port_002",
            "name": "Dynamic Strategy Allocation",
            "description": "Rotate capital between alpha streams based on "
            "rolling Sharpe and correlation. Reduce exposure to deteriorating streams.",
            "rationale": "Alpha streams decay at different rates. Dynamic "
            "allocation that reduces exposure to decaying strategies and "
            "increases exposure to improving ones enhances portfolio Sharpe.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="PortfolioConstruction",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["15", "60"],
            tags=["portfolio", "kelly", "allocation", "priority_11"],
        )
        ladder.register(record)


def seed_priority_12_indicators(ladder: EvidenceLadder) -> None:
    """Priority 12: Indicator Research ★☆☆☆☆ (archived — low priority)"""
    topics = [
        {
            "id": "ind_001",
            "name": "Economic RSI: Mean-Reversion in Trending Regimes",
            "description": "RSI-based mean-reversion ONLY in trending regimes "
            "where pullbacks to the mean are economically justified. "
            "No standalone RSI signals.",
            "rationale": "While pure indicator research is deprecated, indicators "
            "are valid when anchored to economic mechanics. RSI oversold in a "
            "bull trend represents a discount buying opportunity backed by the "
            "trend's continuation pressure.",
        },
    ]

    for t in topics:
        record = HypothesisRecord(
            hypothesis_id=t["id"],
            name=t["name"],
            family="IndicatorResearch",
            description=t["description"],
            economic_rationale=t["rationale"],
            symbols=["BTCUSDT"],
            timeframes=["15", "60"],
            tags=["indicator", "RSI", "mean_reversion", "priority_12", "archived"],
        )
        record.archived = True  # Archived per roadmap — low priority
        ladder.register(record)


# ----------------------------------------------------------------------
# Existing alphas (unchanged)
# ----------------------------------------------------------------------
def seed_existing_alphas(ladder: EvidenceLadder) -> None:
    """Seed existing alpha families with current status (renamed per Research Platform v2).

    Hypothesis names no longer embed the conclusion (e.g., 'validated_').
    The evidence ladder itself tells you whether something is validated.
    """
    # ── BTC Mean-Reversion (L2 — survived costs, needs re-discovery) ──────────
    btc_mr = HypothesisRecord(
        hypothesis_id="btc_mr_l2",
        name="BTC Mean-Reversion",
        family="MeanReversionAlpha",
        description="Mean-reversion on BTC during neutral/trending regimes. "
        "Requires re-discovery after OOS failure.",
        economic_rationale="BTC exhibits mean-reverting behavior at specific "
        "timeframes due to market-making activity and range-bound periods.",
        evidence_level=EvidenceLevel.L2,  # Survived transaction costs, but needs re-validation
        symbols=["BTCUSDT"],
        timeframes=["15", "60"],
        tags=["mean_reversion", "btc", "needs_rediscovery"],
    )
    ladder.register(btc_mr)

    eth_mom = HypothesisRecord(
        hypothesis_id="eth_mom_l1",
        name="ETH Momentum Continuation",
        family="MomentumAlpha",
        description="Momentum continuation on ETH. Needs walk-forward validation.",
        economic_rationale="ETH momentum persists due to narrative-driven "
        "capital flows and slow information diffusion in altcoin markets.",
        evidence_level=EvidenceLevel.L1,  # Needs walk-forward
        symbols=["ETHUSDT"],
        timeframes=["60"],
        tags=["momentum", "eth", "needs_walk_forward"],
    )
    ladder.register(eth_mom)

    sol_mom = HypothesisRecord(
        hypothesis_id="sol_mom_l1",
        name="SOL Momentum Continuation",
        family="MomentumAlpha",
        description="Momentum continuation on SOL. Needs walk-forward validation.",
        economic_rationale="SOL exhibits strong momentum characteristics due "
        "to high retail participation and narrative-driven flows.",
        evidence_level=EvidenceLevel.L1,  # Needs walk-forward
        symbols=["SOLUSDT"],
        timeframes=["60"],
        tags=["momentum", "sol", "needs_walk_forward"],
    )
    ladder.register(sol_mom)

    # ── Promising ────────────────────────────────────────────────────────────
    funding_div = HypothesisRecord(
        hypothesis_id="funding_div_l0",
        name="Funding Divergence",
        family="PositioningAlpha",
        description="Funding rate divergence between exchanges as a "
        "sentiment and positioning signal.",
        economic_rationale="When funding rates diverge significantly between "
        "exchanges, it signals fragmented positioning that will converge.",
        evidence_level=EvidenceLevel.L0,
        symbols=["BTCUSDT", "ETHUSDT"],
        timeframes=["60"],
        tags=["promising", "funding", "positioning"],
    )
    ladder.register(funding_div)

    vol_comp = HypothesisRecord(
        hypothesis_id="vol_comp_l0",
        name="Volatility Compression",
        family="ExpansionAlpha",
        description="Low volatility periods predict expansion. "
        "Promising early results, needs systematic validation.",
        economic_rationale="Volatility clustering and mean-reversion in "
        "volatility are well-documented market microstructure phenomena.",
        evidence_level=EvidenceLevel.L0,
        symbols=["BTCUSDT"],
        timeframes=["15", "60"],
        tags=["promising", "volatility", "compression"],
    )
    ladder.register(vol_comp)

    # ── Archived ─────────────────────────────────────────────────────────────
    archived = [
        ("archived_ytc", "YTC Continuation", "ContinuationAlpha",
         "Yield-to-Call continuation strategy — archived after OOS failure."),
        ("archived_alignment", "Alignment Framework", "IndicatorAlpha",
         "Multi-indicator alignment scoring — archived as non-economic."),
        ("archived_fib", "Fibonacci Continuation", "IndicatorAlpha",
         "Fibonacci-based continuation — archived. No economic mechanism."),
        ("archived_vsa", "VSA Capitulation", "IndicatorAlpha",
         "Volume Spread Analysis capitulation patterns — archived."),
    ]

    for aid, name, family, desc in archived:
        record = HypothesisRecord(
            hypothesis_id=aid,
            name=name,
            family=family,
            description=desc,
            economic_rationale="",
            evidence_level=EvidenceLevel.L0,
            symbols=["BTCUSDT"],
            timeframes=["15"],
            tags=["archived"],
        )
        record.archived = True
        ladder.register(record)


# ----------------------------------------------------------------------
# Validated mechanisms (M001-M005)
# ----------------------------------------------------------------------
def seed_validated_mechanisms(ladder: EvidenceLadder) -> None:
    """Seed the five validated/rejected mechanisms with current evidence levels."""
    mechanisms = [
        {
            "id": "M001",
            "name": "Liquidity Exhaustion (Z-score MR)",
            "family": "MeanReversionAlpha",
            "description": "Z-score overbought predicts reversal. "
            "Effect strongest at 4h (+61bp) and 1d (+427bp). Asymmetric: only tops predict reversal.",
            "rationale": "Liquidity exhaustion at extreme Z-scores; overleveraged longs unwind.",
            "evidence_level": EvidenceLevel.L4,
            "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            "timeframes": ["4h", "1d"],
            "tags": ["mechanism", "validated", "M001", "zscore", "mean_reversion"],
        },
        {
            "id": "M002",
            "name": "Trend Continuation (ROC Momentum)",
            "family": "MomentumAlpha",
            "description": "ROC(5)>0.5% predicts continuation at 4h (+55bp). "
            "Commoditized factor — fails null model (naive SMA20 beats it).",
            "rationale": "Momentum persists due to slow information diffusion.",
            "evidence_level": EvidenceLevel.L3,  # robust but needs reconstruction
            "symbols": ["ETHUSDT", "SOLUSDT", "BTCUSDT"],
            "timeframes": ["4h"],
            "tags": ["mechanism", "validated", "M002", "momentum", "needs_reconstruction"],
        },
        {
            "id": "M003",
            "name": "Position Unwind (OI Divergence)",
            "family": "PositioningAlpha",
            "description": "OI divergence reversal. "
            "Rejected — no significant predictive power found in event study.",
            "rationale": "Price rising while OI falling suggests weakening trend.",
            "evidence_level": EvidenceLevel.L0,
            "archived": True,
            "symbols": ["BTCUSDT"],
            "timeframes": ["15m"],
            "tags": ["mechanism", "rejected", "M003", "oi_divergence"],
        },
        {
            "id": "M004",
            "name": "Funding Rotation",
            "family": "PositioningAlpha",
            "description": "Funding rate extremes predict reversal on BTC "
            "(+33bp 4h, +85bp 1d). Not significant on ETH.",
            "rationale": "Deep BTC perpetual market creates arbitrage pressure.",
            "evidence_level": EvidenceLevel.L1,
            "symbols": ["BTCUSDT"],
            "timeframes": ["4h", "1d"],
            "tags": ["mechanism", "observed", "M004", "funding"],
        },
        {
            "id": "M005",
            "name": "Vol Compression",
            "family": "ExpansionAlpha",
            "description": "Low volatility periods predict expansion. "
            "Weak effect on BTC, stronger on SOL. Needs replication.",
            "rationale": "Volatility clustering and mean-reversion.",
            "evidence_level": EvidenceLevel.L1,
            "symbols": ["BTCUSDT", "SOLUSDT"],
            "timeframes": ["15m", "4h"],
            "tags": ["mechanism", "observed", "M005", "volatility", "compression"],
        },
    ]

    for m in mechanisms:
        level = m.pop("evidence_level", EvidenceLevel.L0)
        archived = m.pop("archived", False)
        record = HypothesisRecord(
            hypothesis_id=m["id"],
            name=m["name"],
            family=m["family"],
            description=m["description"],
            economic_rationale=m["rationale"],
            evidence_level=level,
            symbols=m["symbols"],
            timeframes=m["timeframes"],
            tags=m["tags"],
            archived=archived,
        )
        ladder.register(record)


# ----------------------------------------------------------------------
# Negative knowledge entries (NEG001-NEG016)
# ----------------------------------------------------------------------
def seed_negative_knowledge(ladder: EvidenceLadder) -> None:
    """Seed the 16 negative‑knowledge entries from DISCOVERIES.md as archived hypotheses."""
    entries = [
        ("NEG001", "Funding rate alone predicts reversals",
         "PositioningAlpha",
         "Rejected — walk‑forward PF=0.81, timing unreliable.",
         "Do not retry unless combined with OI divergence or price confirmation."),
        ("NEG002", "BTC Mean‑Reversion without regime filter",
         "MeanReversionAlpha",
         "Rejected — walk‑forward PF=0.90‑1.10, edge exists only in range‑bound conditions.",
         "Do not retry unless MTF regime gate added."),
        ("NEG003", "Fixed percentage thresholds for mean‑reversion",
         "IndicatorAlpha",
         "Rejected — PF=1.08 vs z‑score PF=1.35.",
         "Do not retry unless thresholds are regime‑adaptive."),
        ("NEG004", "YTC Continuation on BTC 5m",
         "ContinuationAlpha",
         "Archived — no persistent edge.",
         "Do not retry unless new structural market change."),
        ("NEG005", "Fibonacci‑based continuation patterns",
         "IndicatorAlpha",
         "Archived — no economic mechanism.",
         "Do not retry unless testable economic theory proposed."),
        ("NEG006", "VSA Capitulation patterns",
         "IndicatorAlpha",
         "Archived — not predictive after costs.",
         "Do not retry unless combined with order flow confirmation."),
        ("NEG007", "ETH Momentum without multi‑factor confirmation",
         "MomentumAlpha",
         "Rejected — simple SMA20 produced PF=0.000.",
         "Do not retry unless multi‑factor confirmation used."),
        ("NEG008", "Bollinger Squeeze + entropy filter as standalone signal",
         "ExpansionAlpha",
         "Rejected — PF=0.072, poor directional discrimination.",
         "Do not retry unless combined with HTF context or order flow bias."),
        ("NEG009", "Funding rate z‑score as standalone signal",
         "PositioningAlpha",
         "Rejected — PF=0.30, 8% win rate.",
         "Do not retry unless combined with OI extremes or price confirmation."),
        ("NEG010", "BTC Mean‑Reversion with ADX filter on 15m",
         "MeanReversionAlpha",
         "Rejected — PF=0.428, edge vanished.",
         "Do not retry unless new entry mechanism or tested on 4h+."),
        ("NEG011", "Equal‑weight ensemble without regime awareness",
         "EnsembleAlpha",
         "Rejected — PF=0.57, dilution of strong signals.",
         "Do not retry unless dynamic Sharpe‑weighted or regime‑adaptive allocation used."),
        ("NEG012", "OI divergence as standalone reversal predictor",
         "PositioningAlpha",
         "Rejected — event study found zero significant predictive power.",
         "Do not retry unless combined with second confirmation mechanism."),
        ("NEG013", "Momentum continuation on 1h timeframe",
         "MomentumAlpha",
         "Rejected — no component reached significance; mechanism only works at 4h+.",
         "Do not retry unless tested on 4h+."),
        ("NEG014", "OI divergence on 15m timeframe",
         "PositioningAlpha",
         "Rejected — see NEG012; 4h OI data needed.",
         "Do not retry unless OI resampled to 4h with proper aggregation."),
        ("NEG015", "Short‑term (15m/1h) mechanism testing as definitive rejection",
         "Methodology",
         "Rejected — D019 proves mechanisms invisible at 15m can be significant at 4h/1d.",
         "Do not retry — process change."),
        ("NEG016", "ROC(5) momentum on 4h as unique alpha",
         "MomentumAlpha",
         "Rejected — commoditized factor, fails null model comparison.",
         "Do not retry unless reconstructed with cross‑sectional ranking or regime‑conditional triggers."),
    ]

    for hid, name, family, desc, rationale in entries:
        record = HypothesisRecord(
            hypothesis_id=hid,
            name=name,
            family=family,
            description=desc,
            economic_rationale=rationale,
            evidence_level=EvidenceLevel.L0,
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["15m", "1h"],
            tags=["negative_knowledge", "archived", hid],
            archived=True,
        )
        ladder.register(record)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap the Evidence Ladder with roadmap alpha families."
    )
    parser.add_argument(
        "--output", "-o",
        default="data/experiments/evidence_ladder.json",
        help="Output path for the evidence ladder JSON (default: data/experiments/evidence_ladder.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without saving.",
    )
    args = parser.parse_args()

    ladder = EvidenceLadder(path=args.output)

    # Seed in priority order
    seed_priority_1_positioning(ladder)
    seed_priority_2_cross_section(ladder)
    seed_priority_3_expansion(ladder)
    seed_priority_4_liquidation(ladder)
    seed_priority_5_microstructure(ladder)
    seed_priority_6_mtf_context(ladder)
    seed_priority_7_relative_value(ladder)
    seed_priority_8_feature_discovery(ladder)
    seed_priority_9_ml(ladder)
    seed_priority_10_execution(ladder)
    seed_priority_11_portfolio(ladder)
    seed_priority_12_indicators(ladder)
    seed_existing_alphas(ladder)
    seed_validated_mechanisms(ladder)
    seed_negative_knowledge(ladder)

    print(ladder.render_summary())

    # ── Also seed the Research Knowledge Base ────────────────────────────
    print("\nSeeding Research Knowledge Base...")
    try:
        from src.core.knowledge_base import create_seeded_knowledge_base
        kb = create_seeded_knowledge_base()
        print(kb.render_summary())
    except Exception as exc:
        print(f"  Knowledge Base seeding skipped: {exc}")

    # ── Also seed the Knowledge Graph ────────────────────────────────────
    print("\nSeeding Knowledge Graph...")
    try:
        from src.core.knowledge_graph import create_seeded_graph
        kg = create_seeded_graph()
        print(kg.render_summary())
    except Exception as exc:
        print(f"  Knowledge Graph seeding skipped: {exc}")

    if args.dry_run:
        print("\n[Dry run — not saved]")
    else:
        ladder.save()
        print(f"\nEvidence ladder saved to: {args.output}")

        # ── Show Research Scoreboard ──────────────────────────────────
        try:
            from src.core.research_scoreboard import ResearchScoreboard
            sb = ResearchScoreboard()
            sb.compute()
            print(f"\n{sb.render_compact()}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
