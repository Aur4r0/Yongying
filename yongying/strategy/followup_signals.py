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


def analyze_pullback_long_signal(
    candles: list[Candle],
    indicators: IndicatorSnapshot,
    lookback: int = 20,
) -> RuleResult:
    if len(candles) < lookback + 1:
        return RuleResult(
            name="pullback_long_signal",
            score=0,
            confidence="low",
            state="insufficient_data",
            warnings=[f"Need at least {lookback + 1} candles"],
        )
    if indicators.ma25 is None:
        return RuleResult(
            name="pullback_long_signal",
            score=0,
            confidence="low",
            state="unavailable",
            warnings=["MA25 is unavailable"],
        )

    latest = candles[-1]
    patterns = analyze_patterns(candles, lookback=lookback)
    atr = indicators.atr14 or max(latest.high - latest.low, latest.close * 0.01)
    ma25_distance = abs(latest.close - indicators.ma25) / indicators.ma25 if indicators.ma25 else 1.0
    touched_ma25 = latest.low <= indicators.ma25 + atr * 0.25
    near_ma25 = ma25_distance <= 0.018 or touched_ma25
    volume_ratio = _volume_ratio(candles, lookback)
    volume_contracts = volume_ratio is not None and volume_ratio <= 0.85
    stabilizes = (
        patterns["volume_contraction_stabilization"].matched
        or patterns["long_lower_shadow"].matched
        or latest.close >= latest.open
    )

    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    if near_ma25:
        score += 35
        reasons.append("Price pulled back near MA25")
    else:
        warnings.append("Price is not close enough to MA25")

    if volume_contracts:
        score += 25
        reasons.append(f"Volume contracted on the pullback ({volume_ratio:.2f}x)")
    else:
        warnings.append("Pullback volume did not contract")

    if stabilizes:
        score += 25
        reasons.append("Candle shape shows stabilization")
    else:
        warnings.append("No stabilization candle yet")

    if latest.close >= indicators.ma25:
        score += 10
        reasons.append("Close remains above MA25")

    hard_conditions = near_ma25 and volume_contracts and stabilizes
    state = "pullback_long_candidate" if score >= 70 and hard_conditions else "watch_pullback" if score >= 50 else "no_long"
    return RuleResult(
        name="pullback_long_signal",
        score=round(min(score, 100), 2),
        confidence=_confidence(score),  # type: ignore[arg-type]
        state=state,
        reasons=reasons,
        warnings=warnings,
        metrics={
            "ma25": indicators.ma25,
            "ma25_distance": round(ma25_distance, 4),
            "touched_ma25": touched_ma25,
            "volume_ratio": round(volume_ratio, 4) if volume_ratio is not None else None,
            "stabilizes": stabilizes,
            "hard_conditions": hard_conditions,
        },
    )


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
    patterns = analyze_patterns(candles, lookback=lookback)
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
            "hard_conditions": hard_conditions,
        },
    )
