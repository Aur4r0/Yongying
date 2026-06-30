from __future__ import annotations

import math
from typing import Literal

from .exchanges.binance import fetch_binance_klines
from .exchanges.okx import fetch_okx_candles
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
    market: str = "futures",
    start_time: int | None = None,
    end_time: int | None = None,
) -> list[Candle]:
    """Fetch live candles through the configured exchange adapter."""
    exchange_name = (exchange_id or "binance").lower()
    if exchange_name in {"binance", "binance_futures", "binanceusdm"}:
        return fetch_binance_klines(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            market=market,
            start_time=start_time,
            end_time=end_time,
        )
    if exchange_name in {"okx", "okex"}:
        return fetch_okx_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            market=market,
            start_time=start_time,
            end_time=end_time,
        )
    raise ValueError(f"Unsupported live exchange: {exchange_id}. Implemented: binance, okx.")


def load_candles(
    symbol: str,
    timeframe: str,
    source: Source = "demo",
    limit: int = 180,
    exchange: str | None = None,
    market: str = "futures",
) -> list[Candle]:
    if source == "demo":
        return generate_demo_candles(symbol=symbol, bars=limit)
    if source == "live":
        return fetch_live_candles(symbol=symbol, timeframe=timeframe, limit=limit, exchange_id=exchange, market=market)
    raise ValueError(f"Unsupported source: {source}")
