from __future__ import annotations

import math
import os
from typing import Literal

from .models import Candle


Source = Literal["demo", "live"]


def generate_demo_candles(symbol: str = "ORDI/USDT", bars: int = 140) -> list[Candle]:
    """Generate deterministic candles with accumulation then breakout behavior."""
    candles: list[Candle] = []
    base_ts = 1_700_000_000_000
    price = 3.0

    for i in range(bars):
        if i < bars - 28:
            drift = 0.002 * math.sin(i / 5)
            price = max(1.0, price + drift)
            span = 0.025 + 0.006 * math.sin(i / 3)
            volume = 900 + 120 * math.sin(i / 7)
        elif i < bars - 5:
            center = 3.18
            oscillation = 0.07 * math.sin(i / 2.2)
            price = center + oscillation
            span = 0.028
            volume = 760 + 80 * math.sin(i / 3)
        else:
            step = i - (bars - 5)
            price = 3.24 + step * 0.055
            span = 0.035 + step * 0.005
            volume = 1700 + step * 230

        open_ = price - span * 0.25
        close = price + span * 0.35
        if i == bars - 2:
            open_ = candles[-1].close + 0.025
            close = open_ + 0.075
            volume *= 1.8
        if i == bars - 1:
            open_ = candles[-1].close + 0.03
            close = open_ + 0.08
            volume *= 2.2

        high = max(open_, close) + span
        low = min(open_, close) - span
        if i >= bars - 2:
            gap_floor = candles[-1].high + 0.005
            low = max(low, gap_floor)
            if open_ < low:
                open_ = low + span * 0.20
            if close < open_:
                close = open_ + span * 1.20
            high = max(high, close + span)

        candles.append(
            Candle(
                timestamp=base_ts + i * 15 * 60 * 1000,
                open=round(open_, 6),
                high=round(high, 6),
                low=round(low, 6),
                close=round(close, 6),
                volume=round(float(volume), 6),
            )
        )

    return candles


def fetch_live_candles(
    symbol: str,
    timeframe: str = "15m",
    limit: int = 180,
    exchange_id: str | None = None,
) -> list[Candle]:
    """Fetch candles through ccxt if available."""
    exchange_name = exchange_id or os.getenv("YONGYING_DEFAULT_EXCHANGE", "binance")
    try:
        import ccxt  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Live data requires installing the 'live' extra: pip install -e '.[live]'") from exc

    if not hasattr(ccxt, exchange_name):
        raise ValueError(f"Unsupported exchange: {exchange_name}")

    exchange_cls = getattr(ccxt, exchange_name)
    exchange = exchange_cls({"enableRateLimit": True})
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    return [Candle.from_ohlcv(row) for row in rows]


def load_candles(
    symbol: str,
    timeframe: str,
    source: Source = "demo",
    limit: int = 180,
    exchange: str | None = None,
) -> list[Candle]:
    if source == "demo":
        return generate_demo_candles(symbol=symbol, bars=limit)
    if source == "live":
        return fetch_live_candles(symbol=symbol, timeframe=timeframe, limit=limit, exchange_id=exchange)
    raise ValueError(f"Unsupported source: {source}")
