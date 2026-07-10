"""Generate synthetic BTCUSDT OHLCV data for pipeline validation."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def generate_ohlcv(start_price, n_bars, bar_minutes, start_date):
    """Generate realistic OHLCV data with GBM + mean reversion + volatility clustering."""
    np.random.seed(42)

    dt = bar_minutes / (60 * 24)  # fraction of a day
    mu = 0.00005  # slight upward drift
    base_sigma = 0.015  # base daily vol

    # Mean re