from __future__ import annotations

from ..models import Candle, IndicatorSnapshot, RuleResult
from ..patterns import analyze_patterns


def _confidence(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _safe_ratio(value: float, base: float | None) -> float | None:
    if base is None or base == 0:
        return None
    return value / base


def _momentum_fading(candles: list[Candle]) -> bool:
    if len(candles) < 4:
        return False
    gains = [candles[index].close - candles[index - 1].close for index in range(len(candles) - 3, len(candles))]
    return gains[-1] <= gains[-2] <= gains[-3] or candles[-1].close <= candles[-2].close


def analyze_left_side_short(
    candles: list[Candle],
    indicators: IndicatorSnapshot,
    lookback: int = 20,
) -> RuleResult:
    if len(candles) < lookback + 1:
        return RuleResult(
            name="left_side_short",
            score=0,
            confidence="low",
            state="insufficient_data",
            warnings=[f"Need at least {lookback + 1} candles"],
        )

    latest = candles[-1]
    patterns = analyze_patterns(candles, lookback=lookback)
    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = ["Left-side short is countertrend; use research-only sizing until backtested"]

    boll_close_ratio = _safe_ratio(latest.close, indicators.boll_upper)
    boll_high_ratio = _safe_ratio(latest.high, indicators.boll_upper)
    if boll_close_ratio is not None and boll_high_ratio is not None:
        if boll_high_ratio >= 1.0:
            score += 18
            reasons.append("Price tested or pierced BOLL upper band intrabar")
        elif boll_close_ratio >= 1.0:
            score += 18
            reasons.append("Price closed at or above BOLL upper band")
        elif boll_close_ratio >= 0.985:
            score += 12
            reasons.append("Price is near BOLL upper band")
    else:
        warnings.append("BOLL upper band is unavailable")

    if indicators.rsi14 is not None:
        if indicators.rsi14 >= 75:
            score += 15
            reasons.append(f"RSI is overheated ({indicators.rsi14:.1f})")
        elif indicators.rsi14 >= 68:
            score += 9
            reasons.append(f"RSI is elevated ({indicators.rsi14:.1f})")
    else:
        warnings.append("RSI is unavailable")

    long_upper = patterns["long_upper_shadow"]
    if long_upper.matched:
        score += 18
        reasons.append("Long upper shadow shows intrabar rejection")

    bearish_engulfing = patterns["bearish_engulfing"]
    if bearish_engulfing.matched:
        score += 18
        reasons.append("Bearish engulfing pattern confirms top pressure")

    stalling = patterns["stalling_small_body"]
    if stalling.matched:
        score += 12
        reasons.append("Small-body stalling appeared in a high-price area")

    false_breakout = patterns["false_breakout_reversal"]
    if false_breakout.matched:
        score += 12
        reasons.append("False breakout reversal detected near resistance")

    volume_ratio = None
    if indicators.volume_ma20:
        volume_ratio = latest.volume / indicators.volume_ma20
        if volume_ratio >= 1.20 and (long_upper.matched or stalling.matched or latest.close <= latest.open):
            score += 10
            reasons.append(f"Volume expanded into rejection/stalling ({volume_ratio:.2f}x)")
    else:
        warnings.append("Volume MA20 is unavailable")

    ma25_ratio = _safe_ratio(latest.close, indicators.ma25)
    if ma25_ratio is not None:
        extension = ma25_ratio - 1
        if extension >= 0.08:
            score += 10
            reasons.append(f"Price is extended above MA25 ({extension:.2%})")
        elif extension >= 0.05:
            score += 6
            reasons.append(f"Price is moderately extended above MA25 ({extension:.2%})")
    else:
        warnings.append("MA25 is unavailable")

    fading = _momentum_fading(candles)
    if fading:
        score += 7
        reasons.append("Recent close-to-close momentum is fading")

    capped_score = round(min(score, 100), 2)
    if capped_score >= 70:
        state = "left_side_short_candidate"
    elif capped_score >= 50:
        state = "watch_top"
    else:
        state = "no_short"

    if state == "no_short":
        warnings.append("Top-reversal evidence is not strong enough")

    return RuleResult(
        name="left_side_short",
        score=capped_score,
        confidence=_confidence(capped_score),  # type: ignore[arg-type]
        state=state,
        reasons=reasons,
        warnings=warnings,
        metrics={
            "boll_close_ratio": round(boll_close_ratio, 4) if boll_close_ratio is not None else None,
            "boll_high_ratio": round(boll_high_ratio, 4) if boll_high_ratio is not None else None,
            "rsi14": indicators.rsi14,
            "volume_ratio": round(volume_ratio, 4) if volume_ratio is not None else None,
            "ma25_extension": round(ma25_ratio - 1, 4) if ma25_ratio is not None else None,
            "long_upper_shadow": long_upper.matched,
            "bearish_engulfing": bearish_engulfing.matched,
            "stalling_small_body": stalling.matched,
            "false_breakout_reversal": false_breakout.matched,
            "momentum_fading": fading,
        },
    )
