from __future__ import annotations

from statistics import mean

from ..models import Candle, IndicatorSnapshot, RuleResult


def _shadow_ratios(candle: Candle) -> tuple[float, float, float]:
    full_range = max(candle.high - candle.low, 1e-12)
    body_top = max(candle.open, candle.close)
    body_bottom = min(candle.open, candle.close)
    upper = max(candle.high - body_top, 0.0) / full_range
    lower = max(body_bottom - candle.low, 0.0) / full_range
    body = abs(candle.close - candle.open) / full_range
    return upper, lower, body


def analyze_wash_distribution(candles: list[Candle], indicators: IndicatorSnapshot, lookback: int = 20) -> RuleResult:
    if len(candles) < max(lookback + 1, 60):
        return RuleResult(
            name="wash_distribution",
            score=0,
            confidence="low",
            state="insufficient_data",
            warnings=["Need at least 60 candles for context"],
        )

    current = candles[-1]
    base_window = candles[-lookback - 1 : -1]
    context_window = candles[-60:]
    avg_volume = mean([c.volume for c in base_window])
    volume_ratio = current.volume / avg_volume if avg_volume else 0
    support = min(c.low for c in base_window)
    context_low = min(c.low for c in context_window)
    context_high = max(c.high for c in context_window)
    high_position = (current.close - context_low) / (context_high - context_low) if context_high > context_low else 0.5
    drawdown_from_20_high = (max(c.high for c in base_window) - current.close) / max(c.high for c in base_window)
    upper_shadow, lower_shadow, body_ratio = _shadow_ratios(current)
    broke_support = current.close < support
    below_ma25 = indicators.ma25 is not None and current.close < indicators.ma25

    wash_score = 0.0
    distribution_score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    if volume_ratio <= 0.70:
        wash_score += 30
        reasons.append(f"Volume contraction fits wash behavior ({volume_ratio:.2f}x)")
    elif volume_ratio >= 1.20:
        distribution_score += 30
        warnings.append(f"Volume expansion raises distribution risk ({volume_ratio:.2f}x)")

    if not broke_support and drawdown_from_20_high <= 0.10:
        wash_score += 25
        reasons.append("Price remains above recent support with limited drawdown")
    if broke_support:
        distribution_score += 25
        warnings.append("Latest close broke recent support")

    if lower_shadow >= 0.35 and body_ratio <= 0.45:
        wash_score += 20
        reasons.append("Long lower shadow suggests intrabar recovery")
    if upper_shadow >= 0.35 and current.close < current.open:
        distribution_score += 20
        warnings.append("Bearish candle with long upper shadow suggests selling pressure")

    if high_position >= 0.70 and volume_ratio >= 1.0:
        distribution_score += 15
        warnings.append("High-zone volume activity increases distribution probability")
    if below_ma25:
        distribution_score += 10
        warnings.append("Price is below MA25")
    elif indicators.ma25 is not None:
        wash_score += 10
        reasons.append("Price remains above MA25")

    net_score = max(wash_score, distribution_score)
    if distribution_score >= 55 and distribution_score > wash_score:
        state = "distribution_risk"
        confidence = "high" if distribution_score >= 75 else "medium"
    elif wash_score >= 55 and wash_score > distribution_score:
        state = "wash_candidate"
        confidence = "high" if wash_score >= 75 else "medium"
    else:
        state = "neutral"
        confidence = "low"

    return RuleResult(
        name="wash_distribution",
        score=round(min(net_score, 100), 2),
        confidence=confidence,  # type: ignore[arg-type]
        state=state,
        reasons=reasons,
        warnings=warnings,
        metrics={
            "volume_ratio": round(volume_ratio, 4),
            "support": round(support, 6),
            "high_position": round(high_position, 4),
            "drawdown_from_20_high": round(drawdown_from_20_high, 4),
            "upper_shadow_ratio": round(upper_shadow, 4),
            "lower_shadow_ratio": round(lower_shadow, 4),
            "body_ratio": round(body_ratio, 4),
            "broke_support": broke_support,
            "below_ma25": bool(below_ma25),
            "wash_score": round(wash_score, 2),
            "distribution_score": round(distribution_score, 2),
        },
    )
