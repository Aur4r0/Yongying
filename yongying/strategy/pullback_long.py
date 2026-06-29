from __future__ import annotations

from ..models import Candle, IndicatorSnapshot, RuleResult
from ..patterns import analyze_patterns


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
    patterns = analyze_patterns(candles, lookback=lookback, ma25=indicators.ma25, atr=indicators.atr14)
    pullback_pattern = patterns["pullback_near_ma25"]
    atr = indicators.atr14 or max(latest.high - latest.low, latest.close * 0.01)
    ma25_distance = abs(latest.close - indicators.ma25) / indicators.ma25 if indicators.ma25 else 1.0
    touched_ma25 = latest.low <= indicators.ma25 + atr * 0.25
    near_ma25 = ma25_distance <= 0.018 or touched_ma25
    volume_ratio = _volume_ratio(candles, lookback)
    volume_contracts = volume_ratio is not None and volume_ratio <= 0.85
    stabilizes = (
        patterns["volume_contraction_stabilization"].matched
        or patterns["long_lower_shadow"].matched
        or pullback_pattern.metrics.get("stabilizes") is True
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

    if pullback_pattern.matched:
        reasons.append("Structured pullback_near_ma25 pattern matched")

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
            "pullback_near_ma25_pattern": pullback_pattern.matched,
            "hard_conditions": hard_conditions,
        },
    )
