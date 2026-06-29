from __future__ import annotations

from ..models import Candle, IndicatorSnapshot, RuleResult
from ..patterns import analyze_patterns, candle_geometry


def _confidence(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _volume_ratio(candles: list[Candle], lookback: int) -> float | None:
    if len(candles) < lookback + 1:
        return None
    base = candles[-lookback - 1 : -1]
    avg_volume = sum(c.volume for c in base) / len(base)
    if avg_volume == 0:
        return None
    return candles[-1].volume / avg_volume


def analyze_breakdown_short_signal(
    candles: list[Candle],
    indicators: IndicatorSnapshot,
    lookback: int = 20,
) -> RuleResult:
    if len(candles) < lookback + 1:
        return RuleResult(
            name="breakdown_short_signal",
            score=0,
            confidence="low",
            state="insufficient_data",
            warnings=[f"Need at least {lookback + 1} candles"],
        )
    if indicators.ma7 is None:
        return RuleResult(
            name="breakdown_short_signal",
            score=0,
            confidence="low",
            state="unavailable",
            warnings=["MA7 is unavailable"],
        )

    latest = candles[-1]
    patterns = analyze_patterns(candles, lookback=lookback, ma7=indicators.ma7)
    ma7_break_pattern = patterns["break_below_ma7"]
    volume_ratio = _volume_ratio(candles, lookback)
    geometry = candle_geometry(latest)
    close_below_ma7 = latest.close < indicators.ma7
    broke_previous_low = latest.close < min(c.low for c in candles[-lookback - 1 : -1])
    volume_expands = volume_ratio is not None and volume_ratio >= 1.25
    bearish_shape = latest.close < latest.open or geometry["close_position"] <= 0.35
    breakdown_pattern = patterns["volume_breakdown"].matched

    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    if close_below_ma7:
        score += 30
        reasons.append("Price closed below MA7")
    else:
        warnings.append("Price has not closed below MA7")

    if volume_expands:
        score += 25
        reasons.append(f"Volume expanded on the breakdown ({volume_ratio:.2f}x)")
    else:
        warnings.append("Breakdown volume is not strong enough")

    if bearish_shape:
        score += 15
        reasons.append("Latest candle has bearish closing behavior")

    if broke_previous_low or breakdown_pattern:
        score += 25
        reasons.append("Price broke recent support")

    if ma7_break_pattern.matched:
        reasons.append("Structured break_below_ma7 pattern matched")

    hard_conditions = close_below_ma7 and volume_expands and bearish_shape
    state = "breakdown_short_candidate" if score >= 70 and hard_conditions else "watch_breakdown" if score >= 50 else "no_short"
    return RuleResult(
        name="breakdown_short_signal",
        score=round(min(score, 100), 2),
        confidence=_confidence(score),  # type: ignore[arg-type]
        state=state,
        reasons=reasons,
        warnings=warnings,
        metrics={
            "ma7": indicators.ma7,
            "close_below_ma7": close_below_ma7,
            "volume_ratio": round(volume_ratio, 4) if volume_ratio is not None else None,
            "bearish_shape": bearish_shape,
            "broke_previous_low": broke_previous_low,
            "volume_breakdown_pattern": breakdown_pattern,
            "break_below_ma7_pattern": ma7_break_pattern.matched,
            "hard_conditions": hard_conditions,
        },
    )
