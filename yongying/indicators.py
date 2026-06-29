from __future__ import annotations

import math
from statistics import mean, pstdev

from .models import Candle, IndicatorSnapshot


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def _highs(candles: list[Candle]) -> list[float]:
    return [c.high for c in candles]


def _lows(candles: list[Candle]) -> list[float]:
    return [c.low for c in candles]


def _volumes(candles: list[Candle]) -> list[float]:
    return [c.volume for c in candles]


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return mean(values[-period:])


def ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    alpha = 2 / (period + 1)
    out: list[float | None] = [None] * (period - 1)
    current = mean(values[:period])
    out.append(current)
    for value in values[period:]:
        current = value * alpha + current * (1 - alpha)
        out.append(current)
    return out


def bollinger(values: list[float], period: int = 20, width: float = 2.0) -> tuple[float | None, float | None, float | None]:
    if len(values) < period:
        return None, None, None
    window = values[-period:]
    mid = mean(window)
    deviation = pstdev(window)
    return mid, mid + width * deviation, mid - width * deviation


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for prev, current in zip(values[-period - 1 : -1], values[-period:]):
        change = current - prev
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if math.isclose(avg_loss, 0.0):
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    true_ranges = []
    recent = candles[-period:]
    previous = candles[-period - 1]
    for candle in recent:
        tr = max(
            candle.high - candle.low,
            abs(candle.high - previous.close),
            abs(candle.low - previous.close),
        )
        true_ranges.append(tr)
        previous = candle
    return mean(true_ranges)


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float | None, float | None, float | None]:
    if len(values) < slow + signal:
        return None, None, None
    fast_ema = ema_series(values, fast)
    slow_ema = ema_series(values, slow)
    macd_line: list[float] = []
    for f, s in zip(fast_ema, slow_ema):
        if f is not None and s is not None:
            macd_line.append(f - s)
    signal_series = ema_series(macd_line, signal)
    if not macd_line or signal_series[-1] is None:
        return None, None, None
    line = macd_line[-1]
    sig = signal_series[-1]
    return line, sig, line - sig


def indicator_snapshot(candles: list[Candle]) -> IndicatorSnapshot:
    if not candles:
        raise ValueError("At least one candle is required")

    closes = _closes(candles)
    volumes = _volumes(candles)
    boll_mid, boll_upper, boll_lower = bollinger(closes)
    macd_line, macd_signal, macd_hist = macd(closes)
    latest = candles[-1]

    return IndicatorSnapshot(
        close=latest.close,
        ma7=sma(closes, 7),
        ma25=sma(closes, 25),
        boll_mid=boll_mid,
        boll_upper=boll_upper,
        boll_lower=boll_lower,
        rsi14=rsi(closes),
        macd=macd_line,
        macd_signal=macd_signal,
        macd_hist=macd_hist,
        atr14=atr(candles),
        volume=latest.volume,
        volume_ma20=sma(volumes, 20),
    )

