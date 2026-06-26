



# src/config/settings.py
"""
V3 Settings — loads YAML config and exposes a typed settings object.
Also provides setup_system_monitoring() for structured log configuration.

Bugs fixed
-----------
1. self.symbols commented out → subscribed_channels crashed at import.
2. load_from_yaml() discarded YAML overrides (setattr missing).
3. root logger level was string literal "log-level" → ValueError at runtime.
4. json formatter referenced non-existent src.utils.logging_formatters module.
5. Unused imports (json, Any, Optional) removed.
6. (NEW) load_yaml_config() crashed with FileNotFoundError when the caller
   passed "alpha_factory_config.yaml" but the file on disk is
   "alpha_factory_config.yml" (or vice-versa).
   Fix: resolve_config_path() tries the given path first, then swaps the
   extension between .yaml and .yml before raising.
"""

from __future__ import annotations

import logging
import logging.config
import os
from pathlib import Path
from typing import Dict, List

import yaml


# ─── YAML loader with .yaml / .yml fallback ───────────────────────────────────

def resolve_config_path(path: str) -> Path:
    """
    Return a Path that actually exists on disk.

    Tries the given path first; if not found, swaps the extension between
    .yaml and .yml and tries again.  Raises FileNotFoundError only if
    neither variant exists.

    This resolves the common mismatch between callers who write
    "alpha_factory_config.yaml" and files stored as "alpha_factory_config.yml"
    (or the reverse).
    """
    p = Path(path)
    if p.exists():
        return p

    # Swap extension and try again
    if p.suffix == ".yaml":
        alt = p.with_suffix(".yml")
    elif p.suffix == ".yml":
        alt = p.with_suffix(".yaml")
    else:
        alt = None

    if alt is not None and alt.exists():
        return alt

    # Neither exists — provide a helpful message listing both candidates
    candidates = [str(p)]
    if alt:
        candidates.append(str(alt))
    raise FileNotFoundError(
        f"Config file not found. Tried: {candidates}. "
        f"Check the path and ensure the file exists in the project root."
    )


def load_yaml_config(path: str) -> dict:
    """Load and return a YAML config file as a dict, tolerating .yaml/.yml mismatch."""
    resolved = resolve_config_path(path)
    with open(resolved, "r") as fh:
        return yaml.safe_load(fh)


# ─── Settings class ───────────────────────────────────────────────────────────

class _Settings:
    """
    Singleton-style settings object.
    Defaults are set here; call load_from_yaml() to override from a YAML file.
    """

    def __init__(self) -> None:
        self.env: str = os.getenv("ENV", "dev")

        # ── Symbols — MUST be defined first; referenced by subscribed_channels ─
        self.symbols: List[str] = ["BTCUSDT", "ETHUSDT"]
        self.symbol_map: Dict[str, str] = {s: s for s in self.symbols}

        # ── Data acquisition ──────────────────────────────────────────────────
        self.resampling_intervals: List[str] = ["5", "15", "60"]
        self.data_storage_path: str = "data/raw"
        # Min rows per resolution — must exceed FeatureEngineerOptimized.MAX_LOOKBACK
        # (typically 1050) so warm_features() can compute all rolling indicators.
        # 15m target = 1500 (43% above MAX_LOOKBACK=1050): absorbs API gaps and
        # the 48-bar large-gap threshold so intermediate TF warm-up never falls back.
        # 5m / 60m targets are unchanged (already well above MAX_LOOKBACK).
        self.min_training_rows_by_resolution: Dict[str, int] = {
            "5": 3200, "15": 1500, "60": 50000
        }
        self.min_training_rows: int = int(os.getenv("MIN_TRAINING_ROWS", "50000"))

        # ── API rate limiting ─────────────────────────────────────────────────
        self.api_rate_limit_calls: int = 30
        self.api_rate_limit_period: int = 60  # seconds

        # ── Nobitex API ───────────────────────────────────────────────────────
        self.nobitex_base_url: str    = "https://apiv2.nobitex.ir"
        self.nobitex_api_token: str   = os.getenv("NOBITEX_API_TOKEN", "")
        self.nobitex_username: str    = os.getenv("NOBITEX_USERNAME", "")
        self.nobitex_password: str    = os.getenv("NOBITEX_PASSWORD", "")
        self.nobitex_totp_secret: str = os.getenv("NOBITEX_TOTP_SECRET", "")
        self.nobitex_api_key: str     = os.getenv("NOBITEX_API_KEY", "")
        self.nobitex_api_secret: str  = os.getenv("NOBITEX_API_SECRET", "")

        # ── API endpoints ─────────────────────────────────────────────────────
        self.nobitex_endpoints: Dict[str, str] = {
            "ohlcv":        "/market/udf/history",
            "trades":       "/v2/trades/",
            "market_stats": "/market/stats",
            "orderbook":    "/v3/orderbook/",
            "market_depth": "/v2/depth/",
        }

        # ── Per-endpoint rate limits (requests / minute) ──────────────────────
        self.rate_limits: Dict[str, int] = {
            "ohlcv":        60,
            "trades":       60,
            "market_stats": 20,
            "orderbook":    300,
            "market_depth": 300,
        }

        # ── WebSocket ─────────────────────────────────────────────────────────
        self.websocket_url: str   = "wss://ws.nobitex.ir/connection/websocket"

        # Sanity check: never allow REST base URL here
        if "api.nobitex.ir" in self.websocket_url:
            raise ValueError(f"WebSocket URL contains REST domain: {self.websocket_url}")


        self.max_connections: int = 100
        self.auth_token_url: str  = "https://apiv2.nobitex.ir/auth/ws/token/"
        # self.symbols is defined above — safe to reference here
        self.subscribed_channels: List[str] = [
            f"public:orderbook-{s}" for s in self.symbols
        ]

        # ── Trading parameters ────────────────────────────────────────────────
        self.daily_risk_cap: float      = float(os.getenv("DAILY_RISK_CAP", "0.02"))
        self.position_size_pct: float   = float(os.getenv("POSITION_SIZE_PCT", "0.01"))
        self.max_concurrent_trades: int = int(os.getenv("MAX_CONCURRENT_TRADES", "5"))
        self.sl_atr_mult: float         = float(os.getenv("SL_ATR_MULT", "1.5"))
        self.tp_atr_mult: float         = float(os.getenv("TP_ATR_MULT", "3.0"))
        self.trade_threshold: float     = float(os.getenv("TRADE_THRESHOLD", "0.8"))

    def load_from_yaml(self, path: str) -> None:
        """
        Override defaults from a YAML file.
        Uses resolve_config_path() so .yaml / .yml mismatches are handled.
        setattr() is called after validation so overrides are actually applied.
        """
        cfg = load_yaml_config(path)  # already tolerates .yaml/.yml mismatch
        for key, val in cfg.items():
            if not hasattr(self, key):
                continue
            current = getattr(self, key)
            expected_type = type(current)
            # Tolerate int/float coercion (YAML parses "1" as int, "1.0" as float)
            if isinstance(current, float) and isinstance(val, int):
                val = float(val)
            elif (isinstance(current, int)
                  and isinstance(val, float)
                  and val == int(val)):
                val = int(val)
            elif not isinstance(val, expected_type):
                raise TypeError(
                    f"settings.{key}: expected {expected_type.__name__}, "
                    f"got {type(val).__name__} (value={val!r})"
                )
            setattr(self, key, val)


# Module-level singleton — instantiated once at import time
settings = _Settings()


# ─── Logging setup ────────────────────────────────────────────────────────────

class _FallbackJsonFormatter(logging.Formatter):
    """
    Stdlib-only JSON formatter.
    Used when python-json-logger is not installed.
    Produces one JSON object per line suitable for log aggregation pipelines.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        payload: dict = {
            "ts":     self.formatTime(record, self.datefmt),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _make_json_formatter() -> logging.Formatter:
    """Return the best available JSON formatter."""
    try:
        from pythonjsonlogger import jsonlogger  # type: ignore
        return jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    except ImportError:
        return _FallbackJsonFormatter()


def setup_system_monitoring(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the Alpha Factory.
    Call once at startup before any logger is used.
    """
    Path("logs").mkdir(parents=True, exist_ok=True)

    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    normalised = log_level.upper()
    if normalised not in valid_levels:
        normalised = "INFO"

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format":  "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class":     "logging.StreamHandler",
                "formatter": "standard",
                "level":     normalised,
            },
            "file": {
                "class":       "logging.handlers.RotatingFileHandler",
                "filename":    "logs/alpha_factory.log",
                "maxBytes":    50 * 1024 * 1024,  # 50 MB
                "backupCount": 5,
                "formatter":   "standard",
                "level":       "DEBUG",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level":    normalised,  # variable, not string literal "log-level"
        },
        "loggers": {
            "src.core":          {"level": normalised, "propagate": True},
            "src.data":          {"level": normalised, "propagate": True},
            "src.orchestration": {"level": normalised, "propagate": True},
        },
    })

    # Attach JSON handler programmatically (dictConfig cannot call factory fns)
    json_handler = logging.FileHandler("logs/alpha_factory_json.log")
    json_handler.setLevel(logging.DEBUG)
    json_handler.setFormatter(_make_json_formatter())
    logging.getLogger().addHandler(json_handler)