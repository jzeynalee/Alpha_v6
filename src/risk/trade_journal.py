# src/risk/trade_journal.py
"""
Trade Journal  —  Alpha Factory V3
====================================
Immutable, append-only trade log with structured analytics.

Records
-------
  TradeEntry   — written when a trade is opened
  TradeExit    — written when a trade is closed (links back to TradeEntry)
  BarSnapshot  — written every bar: signal state, risk snapshot, market data
  AlertRecord  — written for any risk / precision / alignment alert

Storage
-------
  Primary  : CSV files (one per month, one per record type) — human-readable,
             compatible with pandas, Excel, and any BI tool.
  Index    : SQLite journal.db — fast lookups by strategy_id, symbol, date.
  Exports  : JSON (for dashboard APIs), Parquet (for offline analysis).

"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Record schemas
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TradeEntry:
    trade_id:       str
    timestamp:      float
    datetime_utc:   str
    symbol:         str
    direction:      int          # +1 / -1
    entry_price:    float
    units:          float
    notional:       float
    stop_loss:      float
    take_profit:    float
    strategy_id:    str
    regime:         str
    proba_alpha:    float
    deter_alpha:    bool
    c_met_ratio:    float
    precision_ewma: float
    kelly_fraction: float
    risk_pct:       float
    atr:            float
    css:            float
    regime_entropy: float
    bar_index:      int   = 0
    notes:          str   = ""    
    top_features:   str   = ""   # JSON: [[feat, shap_value], ...]


@dataclass
class TradeExit:
    trade_id:       str
    timestamp:      float
    datetime_utc:   str
    symbol:         str
    exit_price:     float
    exit_reason:    str    # "stop_loss" | "take_profit" | "time_exit" | "signal_reversal" | "manual"
    units:          float
    pnl:            float  # absolute (in quote currency)
    pnl_pct:        float  # fraction of notional
    pnl_r:          float  # multiples of initial risk (R)
    hold_bars:      int
    strategy_id:    str
    mae:            float = 0.0  # max adverse excursion (negative = loss)
    mfe:            float = 0.0  # max favourable excursion


@dataclass
class BarSnapshot:
    timestamp:       float
    datetime_utc:    str
    symbol:          str
    timeframe:       str
    open:            float
    high:            float
    low:             float
    close:           float
    volume:          float
    regime:          str
    css:             float
    alpha_final:     float
    deter_alpha:     bool
    proba_alpha:     float
    final_decision:  int
    portfolio_heat:  float
    kill_switch:     bool
    ws_healthy:      bool


@dataclass
class AlertRecord:
    timestamp:    float
    datetime_utc: str
    alert_type:   str       # "kill_switch" | "css_drift" | "precision_decay" | ...
    strategy_id:  str
    message:      str
    value:        float
    threshold:    float


# ═══════════════════════════════════════════════════════════════════════════════
#  TradeJournal
# ═══════════════════════════════════════════════════════════════════════════════

class TradeJournal:
    """
    Append-only trade log with structured analytics.

    Constructor signature is unchanged; all M8 plumbing is internal.
    """

    def __init__(self, base_dir: Path = Path("data/journal")) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # In-memory caches for fast analytics
        self._entries: Dict[str, TradeEntry] = {}     # trade_id -> entry
        self._exits:   Dict[str, TradeExit]  = {}     # trade_id -> exit
        self._bar_snapshots: List[BarSnapshot] = []   # bounded deque in production
        self._alerts: List[AlertRecord] = []

        # SQLite for indexed lookups
        self._db_path = self.base_dir / "journal.db"
        self._init_db()

        # Load existing entries from DB on startup
        self._load_open_trades()
        self._load_closed_trades()


    # ─── DB init ─────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """
        M8: enable WAL journal mode and a 5 s busy_timeout. Three coroutines
        (live execution, reconciliation monitor, position monitor) can each
        write to this DB on the same tick; without WAL the second and third
        get OperationalError: database is locked. WAL also lets readers
        proceed concurrently with the writer.

        journal_mode = WAL is persistent (survives DB closes); busy_timeout
        and synchronous are per-connection and re-applied in _connect().
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")  # ms
            conn.execute("PRAGMA synchronous = NORMAL")  # WAL-safe, faster than FULL
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trade_entries (
                    trade_id TEXT PRIMARY KEY,
                    timestamp REAL, datetime_utc TEXT, symbol TEXT,
                    direction INTEGER, entry_price REAL, units REAL,
                    notional REAL, stop_loss REAL, take_profit REAL,
                    strategy_id TEXT, regime TEXT, proba_alpha REAL,
                    deter_alpha INTEGER, c_met_ratio REAL, precision_ewma REAL,
                    kelly_fraction REAL, risk_pct REAL, atr REAL, css REAL,
                    regime_entropy REAL, bar_index INTEGER, notes TEXT, top_features  TEXT DEFAULT '',
                    closed INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS trade_exits (
                    trade_id TEXT PRIMARY KEY,
                    timestamp REAL, datetime_utc TEXT, symbol TEXT,
                    exit_price REAL, exit_reason TEXT, units REAL,
                    pnl REAL, pnl_pct REAL, pnl_r REAL, hold_bars INTEGER,
                    strategy_id TEXT, mae REAL, mfe REAL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL, datetime_utc TEXT, alert_type TEXT,
                    strategy_id TEXT, message TEXT, value REAL, threshold REAL
                );
                CREATE INDEX IF NOT EXISTS idx_entries_symbol
                    ON trade_entries(symbol);
                CREATE INDEX IF NOT EXISTS idx_entries_strategy
                    ON trade_entries(strategy_id);
                CREATE INDEX IF NOT EXISTS idx_exits_symbol
                    ON trade_exits(symbol);
            """)

    def _connect(self) -> sqlite3.Connection:
        """
        Return a SQLite connection with the M8 pragmas applied.

        Use this everywhere instead of sqlite3.connect(self._db_path) so the
        per-connection busy_timeout is set on every open. journal_mode = WAL
        is persistent and was set once in _init_db.
        """
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA busy_timeout = 5000")

        try:
            conn.execute("ALTER TABLE trade_entries ADD COLUMN "
                        "top_features TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass    # column already exists

        return conn

    def _load_open_trades(self) -> None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trade_entries WHERE closed = 0"
            ).fetchall()
        for row in rows:
            d = dict(row)
            d["deter_alpha"] = bool(d["deter_alpha"])
            self._entries[d["trade_id"]] = TradeEntry(**{
                k: v for k, v in d.items() if k != "closed"
            })
        logger.info("TradeJournal loaded %d open trades from DB.", len(self._entries))

    # ─── Logging API ──────────────────────────────────────────────────────────

    def log_entry(
        self,
        symbol:         str,
        direction:      int,
        entry_price:    float,
        units:          float,
        stop_loss:      float,
        take_profit:    float,
        strategy_id:    str,
        regime:         str,
        proba_alpha:    float,
        deter_alpha:    bool,
        c_met_ratio:    float = 0.0,
        precision_ewma: float = 0.0,
        kelly_fraction: float = 0.0,
        risk_pct:       float = 0.0,
        atr:            float = 0.0,
        css:            float = 0.0,
        regime_entropy: float = 0.0,
        bar_index:      int   = 0,
        notes:          str   = "",
    ) -> str:
        """Record a trade opening. Returns the unique trade_id."""
        trade_id = str(uuid.uuid4())[:12]
        now      = time.time()
        dt_utc   = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

        entry = TradeEntry(
            trade_id=trade_id, timestamp=now, datetime_utc=dt_utc,
            symbol=symbol, direction=direction, entry_price=entry_price,
            units=units, notional=units * entry_price,
            stop_loss=stop_loss, take_profit=take_profit,
            strategy_id=strategy_id, regime=regime,
            proba_alpha=proba_alpha, deter_alpha=deter_alpha,
            c_met_ratio=c_met_ratio, precision_ewma=precision_ewma,
            kelly_fraction=kelly_fraction, risk_pct=risk_pct,
            atr=atr, css=css, regime_entropy=regime_entropy,
            bar_index=bar_index, notes=notes,
        )
        self._entries[trade_id] = entry

        # DB insert
        row = asdict(entry)
        row["deter_alpha"] = int(entry.deter_alpha)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trade_entries VALUES "
                "(:trade_id,:timestamp,:datetime_utc,:symbol,:direction,"
                ":entry_price,:units,:notional,:stop_loss,:take_profit,"
                ":strategy_id,:regime,:proba_alpha,:deter_alpha,:c_met_ratio,"
                ":precision_ewma,:kelly_fraction,:risk_pct,:atr,:css,"
                ":regime_entropy,:bar_index,:notes,:top_features, 0)",
                row,
            )

        # CSV
        self._append_csv("entries", asdict(entry))
        logger.info(
            "TRADE OPEN  id=%s %s dir=%+d price=%.2f units=%.4f",
            trade_id, symbol, direction, entry_price, units,
        )
        return trade_id

    def _load_closed_trades(self, max_rows: int = 10_000) -> None:
        """
        Load recently-closed trades into _exits (and their entries into
        _entries) so analytics_report() is complete immediately after a
        restart. Capped at max_rows so a huge history does not bloat memory.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            exit_rows = conn.execute(
                "SELECT * FROM trade_exits ORDER BY timestamp DESC LIMIT ?",
                (max_rows,),
            ).fetchall()
            if not exit_rows:
                logger.info("TradeJournal: no closed trades to load.")
                return
            trade_ids = [r["trade_id"] for r in exit_rows]
            placeholders = ",".join("?" * len(trade_ids))
            entry_rows = conn.execute(
                f"SELECT * FROM trade_entries WHERE trade_id IN ({placeholders})",
                trade_ids,
            ).fetchall()

        for row in entry_rows:
            d = dict(row)
            d["deter_alpha"] = bool(d["deter_alpha"])
            self._entries[d["trade_id"]] = TradeEntry(
                **{k: v for k, v in d.items() if k != "closed"}
            )
        for row in exit_rows:
            d = dict(row)
            self._exits[d["trade_id"]] = TradeExit(**d)
        logger.info(
            "TradeJournal: loaded %d closed trade(s) into analytics cache.",
            len(exit_rows),
        )

    def log_exit(
        self,
        trade_id:    str,
        exit_price:  float,
        exit_reason: str,
        hold_bars:   int,
        mae:         float = 0.0,
        mfe:         float = 0.0,
    ) -> Optional[TradeExit]:
        """Record a trade closing. Returns the TradeExit, or None if trade_id unknown."""
        entry = self._entries.get(trade_id)
        if entry is None:
            logger.warning("log_exit: unknown trade_id %s", trade_id)
            return None

        pnl      = entry.direction * (exit_price - entry.entry_price) * entry.units
        pnl_pct  = pnl / max(entry.notional, 1e-9)
        risk_amt = entry.risk_pct * entry.notional
        pnl_r    = pnl / max(risk_amt, 1e-9)
        now      = time.time()
        dt_utc   = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

        exit_ = TradeExit(
            trade_id=trade_id, timestamp=now, datetime_utc=dt_utc,
            symbol=entry.symbol, exit_price=exit_price,
            exit_reason=exit_reason, units=entry.units,
            pnl=pnl, pnl_pct=pnl_pct, pnl_r=pnl_r,
            hold_bars=hold_bars, strategy_id=entry.strategy_id,
            mae=mae, mfe=mfe,
        )
        self._exits[trade_id] = exit_

        # DB
        row = asdict(exit_)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trade_exits VALUES "
                "(:trade_id,:timestamp,:datetime_utc,:symbol,:exit_price,"
                ":exit_reason,:units,:pnl,:pnl_pct,:pnl_r,:hold_bars,"
                ":strategy_id,:mae,:mfe)",
                row,
            )
            conn.execute(
                "UPDATE trade_entries SET closed=1 WHERE trade_id=?", (trade_id,)
            )

        self._append_csv("exits", asdict(exit_))
        logger.info(
            "TRADE CLOSE id=%s %s reason=%s pnl=%.4f (%.2fR) hold=%d bars",
            trade_id, entry.symbol, exit_reason, pnl, pnl_r, hold_bars,
        )
        return exit_

    def update_attribution(self, trade_id: str, top_features_json: str) -> None:
        '''Update the top_features SHAP attribution for an existing trade.
        No-op if trade_id is unknown.'''
        if trade_id not in self._entries:
            logger.warning("update_attribution: unknown trade_id %s", trade_id)
            return
        self._entries[trade_id].top_features = top_features_json
        with self._connect() as conn:
            conn.execute(
                "UPDATE trade_entries SET top_features = ? WHERE trade_id = ?",
                (top_features_json, trade_id),
            )
        logger.debug("Attribution updated for trade %s", trade_id)

    def log_bar_snapshot(
        self,
        symbol:         str,
        timeframe:      str,
        ohlcv:          dict,
        regime:         str,
        css:            float,
        alpha_final:    float,
        deter_alpha:    bool,
        proba_alpha:    float,
        final_decision: int,
        portfolio_heat: float,
        kill_switch:    bool,
        ws_healthy:     bool,
    ) -> None:
        now    = time.time()
        dt_utc = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
        snap = BarSnapshot(
            timestamp=now, datetime_utc=dt_utc,
            symbol=symbol, timeframe=timeframe,
            open=ohlcv.get("open", 0.0), high=ohlcv.get("high", 0.0),
            low=ohlcv.get("low", 0.0),   close=ohlcv.get("close", 0.0),
            volume=ohlcv.get("volume", 0.0),
            regime=regime, css=css, alpha_final=alpha_final,
            deter_alpha=deter_alpha, proba_alpha=proba_alpha,
            final_decision=final_decision, portfolio_heat=portfolio_heat,
            kill_switch=kill_switch, ws_healthy=ws_healthy,
        )
        self._bar_snapshots.append(snap)
        # Keep last 10 000 in memory
        if len(self._bar_snapshots) > 10_000:
            self._bar_snapshots = self._bar_snapshots[-10_000:]
        # CSV append every bar (buffered by OS)
        self._append_csv(f"bars_{symbol}_{timeframe}", asdict(snap))

    def log_alert(
        self,
        alert_type:  str,
        strategy_id: str,
        message:     str,
        value:       float,
        threshold:   float,
    ) -> None:
        now    = time.time()
        dt_utc = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
        alert  = AlertRecord(
            timestamp=now, datetime_utc=dt_utc,
            alert_type=alert_type, strategy_id=strategy_id,
            message=message, value=value, threshold=threshold,
        )
        self._alerts.append(alert)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO alerts(timestamp,datetime_utc,alert_type,"
                "strategy_id,message,value,threshold) VALUES (?,?,?,?,?,?,?)",
                (now, dt_utc, alert_type, strategy_id, message, value, threshold),
            )
        self._append_csv("alerts", asdict(alert))
        logger.warning(
            "ALERT [%s] %s: %s (value=%.4f, threshold=%.4f)",
            alert_type, strategy_id, message, value, threshold,
        )

    # ─── CSV helpers ─────────────────────────────────────────────────────────

    def _append_csv(self, name: str, row: dict) -> None:
        """Append one row to the monthly CSV file for `name`."""
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        path  = self.base_dir / f"{name}_{month}.csv"
        write_header = not path.exists()
        try:
            with open(path, "a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=row.keys())
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
        except Exception as exc:
            logger.warning("CSV append failed for %s: %s", name, exc)

    # ─── Analytics ────────────────────────────────────────────────────────────

    def closed_trades_df(self) -> pd.DataFrame:
        """Return a merged DataFrame of all closed trades (entry + exit columns)."""
        if not self._exits:
            return pd.DataFrame()
        entries = [asdict(self._entries[tid]) for tid in self._exits if tid in self._entries]
        exits   = [asdict(e) for e in self._exits.values()]
        df_e    = pd.DataFrame(entries).add_prefix("entry_").rename(
                      columns={"entry_trade_id": "trade_id"})
        df_x    = pd.DataFrame(exits).add_prefix("exit_").rename(
                      columns={"exit_trade_id": "trade_id"})
        return df_e.merge(df_x, on="trade_id", how="inner")

    def win_rate(self, strategy_id: str = "") -> float:
        exits = list(self._exits.values())
        if strategy_id:
            exits = [e for e in exits if e.strategy_id == strategy_id]
        if not exits:
            return float("nan")
        wins = sum(1 for e in exits if e.pnl > 0)
        return wins / len(exits)

    def profit_factor(self, strategy_id: str = "") -> float:
        exits = list(self._exits.values())
        if strategy_id:
            exits = [e for e in exits if e.strategy_id == strategy_id]
        gross_profit = sum(e.pnl for e in exits if e.pnl > 0)
        gross_loss   = sum(abs(e.pnl) for e in exits if e.pnl < 0)
        return gross_profit / max(gross_loss, 1e-9)

    def sharpe(self, strategy_id: str = "", annualise_factor: float = 252.0) -> float:
        exits = list(self._exits.values())
        if strategy_id:
            exits = [e for e in exits if e.strategy_id == strategy_id]
        if len(exits) < 4:
            return float("nan")
        returns = np.array([e.pnl_pct for e in exits])
        std     = np.std(returns)
        if std < 1e-9:
            return 0.0
        return float(np.mean(returns) / std * np.sqrt(annualise_factor))

    def max_drawdown(self, strategy_id: str = "") -> float:
        exits = list(self._exits.values())
        if strategy_id:
            exits = [e for e in exits if e.strategy_id == strategy_id]
        if not exits:
            return 0.0
        equity = np.cumprod([1.0 + e.pnl_pct for e in exits])
        peak   = np.maximum.accumulate(equity)
        dd     = (peak - equity) / np.maximum(peak, 1e-9)
        return float(dd.max())

    def expectancy(self, strategy_id: str = "") -> float:
        exits = list(self._exits.values())
        if strategy_id:
            exits = [e for e in exits if e.strategy_id == strategy_id]
        if not exits:
            return float("nan")
        return float(np.mean([e.pnl for e in exits]))

    def avg_mae_mfe(self, strategy_id: str = "") -> dict:
        exits = list(self._exits.values())
        if strategy_id:
            exits = [e for e in exits if e.strategy_id == strategy_id]
        if not exits:
            return {"avg_mae": float("nan"), "avg_mfe": float("nan")}
        return {
            "avg_mae": float(np.mean([e.mae for e in exits])),
            "avg_mfe": float(np.mean([e.mfe for e in exits])),
        }

    def trade_duration_stats(self, strategy_id: str = "") -> dict:
        exits = list(self._exits.values())
        if strategy_id:
            exits = [e for e in exits if e.strategy_id == strategy_id]
        if not exits:
            return {}
        durations = [e.hold_bars for e in exits]
        return {
            "mean_bars":   float(np.mean(durations)),
            "median_bars": float(np.median(durations)),
            "max_bars":    int(np.max(durations)),
        }

    def monthly_pnl(self) -> pd.DataFrame:
        if not self._exits:
            return pd.DataFrame()
        rows = []
        for exit_ in self._exits.values():
            dt = datetime.fromtimestamp(exit_.timestamp, tz=timezone.utc)
            rows.append({
                "month": dt.strftime("%Y-%m"),
                "pnl": exit_.pnl,
                "pnl_pct": exit_.pnl_pct,
                "strategy_id": exit_.strategy_id,
            })
        df = pd.DataFrame(rows)
        return df.groupby(["month", "strategy_id"])[["pnl", "pnl_pct"]].sum().reset_index()

    def strategy_breakdown(self) -> pd.DataFrame:
        exits = list(self._exits.values())
        if not exits:
            return pd.DataFrame()
        strategies = list({e.strategy_id for e in exits})
        rows = []
        for sid in strategies:
            rows.append({
                "strategy_id":    sid,
                "n_trades":       sum(1 for e in exits if e.strategy_id == sid),
                "win_rate":       self.win_rate(sid),
                "profit_factor":  self.profit_factor(sid),
                "sharpe":         self.sharpe(sid),
                "max_drawdown":   self.max_drawdown(sid),
                "expectancy":     self.expectancy(sid),
                "total_pnl":      sum(e.pnl for e in exits if e.strategy_id == sid),
            })
        return pd.DataFrame(rows).sort_values("total_pnl", ascending=False)

    def open_trades_summary(self) -> List[dict]:
        closed_ids = set(self._exits.keys())
        return [
            {"trade_id": tid, "symbol": e.symbol, "direction": e.direction,
             "entry_price": e.entry_price, "units": e.units,
             "strategy_id": e.strategy_id, "regime": e.regime,
             "open_since": e.datetime_utc}
            for tid, e in self._entries.items()
            if tid not in closed_ids
        ]

    def analytics_report(self) -> dict:
        """Return a full analytics snapshot as a structured dict."""
        return {
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "open_trades":       len(self.open_trades_summary()),
            "closed_trades":     len(self._exits),
            "overall": {
                "win_rate":      self.win_rate(),
                "profit_factor": self.profit_factor(),
                "sharpe":        self.sharpe(),
                "max_drawdown":  self.max_drawdown(),
                "expectancy":    self.expectancy(),
                **self.avg_mae_mfe(),
                **self.trade_duration_stats(),
            },
            "monthly_pnl":        self.monthly_pnl().to_dict(orient="records"),
            "strategy_breakdown": self.strategy_breakdown().to_dict(orient="records"),
            "recent_alerts":      [asdict(a) for a in self._alerts[-20:]],
        }

    def export_json(self, path: Optional[Path] = None) -> Path:
        path = path or (self.base_dir / "analytics_report.json")
        with open(path, "w") as fh:
            json.dump(self.analytics_report(), fh, indent=2, default=str)
        logger.info("Analytics report exported → %s", path)
        return path

    def export_parquet(self) -> Optional[Path]:
        df = self.closed_trades_df()
        if df.empty:
            return None
        path = self.base_dir / "closed_trades.parquet"
        df.to_parquet(path, index=False)
        logger.info("Closed trades exported → %s (%d rows)", path, len(df))
        return path