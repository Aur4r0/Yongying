from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from .models import Candle


@dataclass(frozen=True)
class PatternResult:
    name: str
    matched: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def candle_geometry(candle: Candle) -> dict[str, float]:
    full_range = max(candle.high - candle.low, 0.0)
    body_top = max(candle.open, candle.close)
    body_bottom = min(candle.open, candle.close)
    body = abs(candle.close - candle.open)
    upper_shadow = max(candle.high - body_top, 0.0)
    lower_shadow = max(body_bottom - candle.low, 0.0)
    return {
        "range": full_range,
        "body": body,
        "upper_shadow": upper_shadow,
        "lower_shadow": lower_shadow,
        "body_ratio": _safe_div(body, full_range),
        "upper_shadow_ratio": _safe_div(upper_shadow, full_range),
        "lower_shadow_ratio": _safe_div(lower_shadow, full_range),
        "close_position": _safe_div(candle.close - candle.low, full_range),
    }


def _average_volume(candles: list[Candle], period: int = 20) -> float | None:
    if len(candles) < period:
        return None
    return mean(c.volume for c in candles[-period:])


def _recent_support(candles: list[Candle]) -> float:
    return min(c.low for c in candles)


def _recent_resistance(candles: list[Candle]) -> float:
    return max(c.high for c in candles)


def detect_long_upper_shadow(candle: Candle) -> PatternResult:
    geometry = candle_geometry(candle)
    matched = geometry["upper_shadow_ratio"] >= 0.45 and geometry["body_ratio"] <= 0.45
    reasons = []
    if matched:
        reasons.append("Upper shadow is large while the body remains limited")
    return PatternResult(
        name="long_upper_shadow",
        matched=matched,
        score=80.0 if matched else 0.0,
        reasons=reasons,
        metrics=geometry,
    )


def detect_bearish_engulfing(candles: list[Candle]) -> PatternResult:
    if len(candles) < 2:
        return PatternResult(name="bearish_engulfing", matched=False, score=0.0)

    previous = candles[-2]
    current = candles[-1]
    previous_bullish = previous.close > previous.open
    current_bearish = current.close < current.open
    body_engulfed = current.open >= previous.close and current.close <= previous.open
    matched = previous_bullish and current_bearish and body_engulfed
    reasons = []
    if matched:
        reasons.append("Bearish candle body engulfs the previous bullish body")
    return PatternResult(
        name="bearish_engulfing",
        matched=matched,
        score=85.0 if matched else 0.0,
        reasons=reasons,
        metrics={
            "previous_open": previous.open,
            "previous_close": previous.close,
            "current_open": current.open,
            "current_close": current.close,
        },
    )


def detect_long_lower_shadow(candle: Candle) -> PatternResult:
    geometry = candle_geometry(candle)
    matched = geometry["lower_shadow_ratio"] >= 0.45 and geometry["body_ratio"] <= 0.45
    reasons = []
    if matched:
        reasons.append("Lower shadow is large while the body remains limited")
    return PatternResult(
        name="long_lower_shadow",
        matched=matched,
        score=80.0 if matched else 0.0,
        reasons=reasons,
        metrics=geometry,
    )


def detect_volume_contraction_stabilization(candles: list[Candle], lookback: int = 20) -> PatternResult:
    if len(candles) < lookback + 1:
        return PatternResult(name="volume_contraction_stabilization", matched=False, score=0.0)

    latest = candles[-1]
    previous = candles[-2]
    base = candles[-lookback - 1 : -1]
    avg_volume = mean(c.volume for c in base)
    support = _recent_support(base)
    geometry = candle_geometry(latest)
    volume_ratio = _safe_div(latest.volume, avg_volume)
    close_holds = latest.close >= previous.close * 0.995
    support_holds = latest.low >= support * 0.995
    stabilizing_shape = latest.close >= latest.open or geometry["lower_shadow_ratio"] >= 0.30
    matched = volume_ratio <= 0.75 and close_holds and support_holds and stabilizing_shape
    reasons = []
    if matched:
        reasons.append("Volume contracted while price held support and stabilized")
    return PatternResult(
        name="volume_contraction_stabilization",
        matched=matched,
        score=75.0 if matched else 0.0,
        reasons=reasons,
        metrics={
            "volume_ratio": round(volume_ratio, 4),
            "support": support,
            "close_holds": close_holds,
            "support_holds": support_holds,
            "stabilizing_shape": stabilizing_shape,
        },
    )


def detect_volume_breakdown(candles: list[Candle], lookback: int = 20) -> PatternResult:
    if len(candles) < lookback + 1:
        return PatternResult(name="volume_breakdown", matched=False, score=0.0)

    latest = candles[-1]
    base = candles[-lookback - 1 : -1]
    avg_volume = mean(c.volume for c in base)
    support = _recent_support(base)
    volume_ratio = _safe_div(latest.volume, avg_volume)
    matched = latest.close < support and volume_ratio >= 1.30
    reasons = []
    if matched:
        reasons.append("Price closed below recent support with expanded volume")
    return PatternResult(
        name="volume_breakdown",
        matched=matched,
        score=85.0 if matched else 0.0,
        reasons=reasons,
        metrics={
            "volume_ratio": round(volume_ratio, 4),
            "support": support,
            "latest_close": latest.close,
        },
    )


def detect_stalling_small_body(candles: list[Candle], lookback: int = 20) -> PatternResult:
    if len(candles) < lookback + 1:
        return PatternResult(name="stalling_small_body", matched=False, score=0.0)

    latest = candles[-1]
    base = candles[-lookback - 1 : -1]
    avg_volume = mean(c.volume for c in base)
    context_low = _recent_support(base)
    context_high = _recent_resistance(base)
    high_position = _safe_div(latest.close - context_low, context_high - context_low)
    volume_ratio = _safe_div(latest.volume, avg_volume)
    geometry = candle_geometry(latest)
    matched = (
        high_position >= 0.75
        and volume_ratio >= 1.0
        and geometry["body_ratio"] <= 0.30
        and geometry["upper_shadow_ratio"] >= 0.25
    )
    reasons = []
    if matched:
        reasons.append("Small body and upper shadow appeared in a high-price area")
    return PatternResult(
        name="stalling_small_body",
        matched=matched,
        score=70.0 if matched else 0.0,
        reasons=reasons,
        metrics={
            "high_position": round(high_position, 4),
            "volume_ratio": round(volume_ratio, 4),
            **geometry,
        },
    )


def detect_false_breakout_reversal(candles: list[Candle], lookback: int = 20) -> PatternResult:
    if len(candles) < lookback + 1:
        return PatternResult(name="false_breakout_reversal", matched=False, score=0.0)

    latest = candles[-1]
    base = candles[-lookback - 1 : -1]
    resistance = _recent_resistance(base)
    geometry = candle_geometry(latest)
    broke_intrabar = latest.high > resistance
    closed_back_below = latest.close < resistance
    weak_close = geometry["close_position"] <= 0.50
    matched = broke_intrabar and closed_back_below and weak_close
    reasons = []
    if matched:
        reasons.append("Price broke resistance intrabar but closed back below it")
    return PatternResult(
        name="false_breakout_reversal",
        matched=matched,
        score=80.0 if matched else 0.0,
        reasons=reasons,
        metrics={
            "resistance": resistance,
            "latest_high": latest.high,
            "latest_close": latest.close,
            "close_position": round(geometry["close_position"], 4),
        },
    )


def detect_pullback_near_ma25(
    candles: list[Candle],
    ma25: float | None,
    atr: float | None = None,
    lookback: int = 20,
    max_distance_ratio: float = 0.018,
) -> PatternResult:
    if not candles:
        return PatternResult(name="pullback_near_ma25", matched=False, score=0.0)
    if ma25 is None or ma25 <= 0:
        return PatternResult(
            name="pullback_near_ma25",
            matched=False,
            score=0.0,
            reasons=[],
            metrics={"ma25": ma25, "available": False},
        )
    if len(candles) < lookback + 1:
        return PatternResult(
            name="pullback_near_ma25",
            matched=False,
            score=0.0,
            metrics={"ma25": ma25, "available": True, "insufficient_data": True},
        )

    latest = candles[-1]
    base = candles[-lookback - 1 : -1]
    avg_volume = mean(c.volume for c in base)
    volume_ratio = _safe_div(latest.volume, avg_volume)
    geometry = candle_geometry(latest)
    distance_ratio = abs(latest.close - ma25) / ma25
    touch_buffer = (atr or max(latest.high - latest.low, ma25 * 0.01)) * 0.25
    touched_ma25 = latest.low <= ma25 + touch_buffer and latest.high >= ma25 - touch_buffer
    close_near_ma25 = distance_ratio <= max_distance_ratio
    volume_contracts = volume_ratio <= 0.85
    stabilizes = latest.close >= latest.open or geometry["lower_shadow_ratio"] >= 0.30
    matched = (touched_ma25 or close_near_ma25) and volume_contracts and stabilizes
    reasons = []
    if matched:
        reasons.append("Price pulled back near MA25 with contracted volume and stabilization")
    return PatternResult(
        name="pullback_near_ma25",
        matched=matched,
        score=80.0 if matched else 0.0,
        reasons=reasons,
        metrics={
            "ma25": ma25,
            "atr": atr,
            "distance_ratio": round(distance_ratio, 4),
            "touched_ma25": touched_ma25,
            "close_near_ma25": close_near_ma25,
            "volume_ratio": round(volume_ratio, 4),
            "volume_contracts": volume_contracts,
            "stabilizes": stabilizes,
        },
    )


def detect_break_below_ma7(
    candles: list[Candle],
    ma7: float | None,
    lookback: int = 20,
    min_volume_ratio: float = 1.25,
) -> PatternResult:
    if not candles:
        return PatternResult(name="break_below_ma7", matched=False, score=0.0)
    if ma7 is None or ma7 <= 0:
        return PatternResult(
            name="break_below_ma7",
            matched=False,
            score=0.0,
            reasons=[],
            metrics={"ma7": ma7, "available": False},
        )
    if len(candles) < lookback + 1:
        return PatternResult(
            name="break_below_ma7",
            matched=False,
            score=0.0,
            metrics={"ma7": ma7, "available": True, "insufficient_data": True},
        )

    latest = candles[-1]
    base = candles[-lookback - 1 : -1]
    avg_volume = mean(c.volume for c in base)
    volume_ratio = _safe_div(latest.volume, avg_volume)
    geometry = candle_geometry(latest)
    close_below_ma7 = latest.close < ma7
    bearish_shape = latest.close < latest.open or geometry["close_position"] <= 0.35
    broke_recent_low = latest.close < _recent_support(base)
    volume_expands = volume_ratio >= min_volume_ratio
    matched = close_below_ma7 and volume_expands and bearish_shape
    reasons = []
    if matched:
        reasons.append("Price closed below MA7 with expanded volume and bearish candle behavior")
    return PatternResult(
        name="break_below_ma7",
        matched=matched,
        score=80.0 if matched else 0.0,
        reasons=reasons,
        metrics={
            "ma7": ma7,
            "close_below_ma7": close_below_ma7,
            "volume_ratio": round(volume_ratio, 4),
            "volume_expands": volume_expands,
            "bearish_shape": bearish_shape,
            "broke_recent_low": broke_recent_low,
        },
    )


def analyze_patterns(
    candles: list[Candle],
    lookback: int = 20,
    ma7: float | None = None,
    ma25: float | None = None,
    atr: float | None = None,
) -> dict[str, PatternResult]:
    if not candles:
        return {}

    latest = candles[-1]
    results = [
        detect_long_upper_shadow(latest),
        detect_bearish_engulfing(candles),
        detect_long_lower_shadow(latest),
        detect_volume_contraction_stabilization(candles, lookback=lookback),
        detect_volume_breakdown(candles, lookback=lookback),
        detect_stalling_small_body(candles, lookback=lookback),
        detect_false_breakout_reversal(candles, lookback=lookback),
        detect_pullback_near_ma25(candles, ma25=ma25, atr=atr, lookback=lookback),
        detect_break_below_ma7(candles, ma7=ma7, lookback=lookback),
    ]
    return {result.name: result for result in results}
