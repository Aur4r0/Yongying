from __future__ import annotations

from ..models import Candle, RuleResult


def _pivot_highs(candles: list[Candle], left: int = 2, right: int = 2) -> list[tuple[int, float]]:
    pivots: list[tuple[int, float]] = []
    for idx in range(left, len(candles) - right):
        value = candles[idx].high
        before = [c.high for c in candles[idx - left : idx]]
        after = [c.high for c in candles[idx + 1 : idx + right + 1]]
        if value > max(before) and value >= max(after):
            pivots.append((idx, value))
    return pivots


def _pivot_lows(candles: list[Candle], left: int = 2, right: int = 2) -> list[tuple[int, float]]:
    pivots: list[tuple[int, float]] = []
    for idx in range(left, len(candles) - right):
        value = candles[idx].low
        before = [c.low for c in candles[idx - left : idx]]
        after = [c.low for c in candles[idx + 1 : idx + right + 1]]
        if value < min(before) and value <= min(after):
            pivots.append((idx, value))
    return pivots


def analyze_market_structure(candles: list[Candle]) -> RuleResult:
    if len(candles) < 30:
        return RuleResult(
            name="market_structure",
            score=0,
            confidence="low",
            state="insufficient_data",
            warnings=["Need at least 30 candles"],
        )

    highs = _pivot_highs(candles)
    lows = _pivot_lows(candles)
    latest = candles[-1]

    if len(highs) < 2 or len(lows) < 2:
        return RuleResult(
            name="market_structure",
            score=20,
            confidence="low",
            state="unclear",
            warnings=["Not enough confirmed pivot highs/lows"],
            metrics={"pivot_highs": highs[-3:], "pivot_lows": lows[-3:]},
        )

    prev_high, last_high = highs[-2], highs[-1]
    prev_low, last_low = lows[-2], lows[-1]
    lower_high = last_high[1] < prev_high[1]
    higher_low = last_low[1] > prev_low[1]
    broke_last_low = latest.close < last_low[1]
    broke_last_high = latest.close > last_high[1]
    made_recent_low = min(c.low for c in candles[-5:]) < last_low[1]
    made_recent_high = max(c.high for c in candles[-5:]) > last_high[1]

    reasons: list[str] = []
    warnings: list[str] = []
    score = 35.0
    state = "range_or_unclear"

    if lower_high and broke_last_low:
        state = "bearish_sms"
        score = 65
        warnings.append("Lower high plus break below pivot low: bearish SMS")
        if made_recent_low:
            state = "bearish_bms"
            score = 80
            warnings.append("Recent price made a fresh low after SMS: bearish BMS")

    elif higher_low and broke_last_high:
        state = "bullish_sms"
        score = 65
        reasons.append("Higher low plus break above pivot high: bullish SMS")
        if made_recent_high:
            state = "bullish_bms"
            score = 80
            reasons.append("Recent price made a fresh high after SMS: bullish BMS")

    elif latest.close > last_high[1]:
        state = "upside_pressure"
        score = 55
        reasons.append("Latest close is above the latest pivot high")
    elif latest.close < last_low[1]:
        state = "downside_pressure"
        score = 55
        warnings.append("Latest close is below the latest pivot low")
    else:
        reasons.append("No confirmed SMS/BMS yet")

    confidence = "high" if score >= 75 else "medium" if score >= 50 else "low"
    return RuleResult(
        name="market_structure",
        score=round(score, 2),
        confidence=confidence,  # type: ignore[arg-type]
        state=state,
        reasons=reasons,
        warnings=warnings,
        metrics={
            "prev_high": {"index": prev_high[0], "price": round(prev_high[1], 6)},
            "last_high": {"index": last_high[0], "price": round(last_high[1], 6)},
            "prev_low": {"index": prev_low[0], "price": round(prev_low[1], 6)},
            "last_low": {"index": last_low[0], "price": round(last_low[1], 6)},
            "lower_high": lower_high,
            "higher_low": higher_low,
            "broke_last_low": broke_last_low,
            "broke_last_high": broke_last_high,
        },
    )

