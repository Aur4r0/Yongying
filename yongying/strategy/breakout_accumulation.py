from __future__ import annotations

from statistics import mean

from ..models import Candle, RuleResult


def _confidence(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _consecutive_bullish(candles: list[Candle]) -> int:
    count = 0
    for index in range(len(candles) - 1, 0, -1):
        current = candles[index]
        previous = candles[index - 1]
        if current.close > current.open and current.close > previous.close:
            count += 1
        else:
            break
    return count


def analyze_breakout_accumulation(candles: list[Candle], lookback: int = 20) -> RuleResult:
    if len(candles) < lookback + 2:
        return RuleResult(
            name="breakout_accumulation",
            score=0,
            confidence="low",
            state="insufficient_data",
            warnings=[f"Need at least {lookback + 2} candles"],
        )

    current = candles[-1]
    previous = candles[-2]
    base_window = candles[-lookback - 1 : -1]
    highs = [c.high for c in base_window]
    lows = [c.low for c in base_window]
    volumes = [c.volume for c in base_window]
    range_high = max(highs)
    range_low = min(lows)
    range_mid = (range_high + range_low) / 2
    range_pct = (range_high - range_low) / range_mid if range_mid else 0
    avg_volume = mean(volumes)
    volume_ratio = current.volume / avg_volume if avg_volume else 0
    bull_count = _consecutive_bullish(candles)
    has_fvg_up = current.low > previous.high
    broke_range = current.close > range_high

    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    if 0 < range_pct <= 0.15:
        score += 25
        reasons.append(f"{lookback} candle range is compressed ({range_pct:.2%})")
    elif range_pct <= 0.20:
        score += 15
        reasons.append(f"Range is moderately compressed ({range_pct:.2%})")
    else:
        warnings.append(f"Range is too wide for clean accumulation ({range_pct:.2%})")

    if volume_ratio >= 2.0:
        score += 25
        reasons.append(f"Latest volume is {volume_ratio:.2f}x the base average")
    elif volume_ratio >= 1.5:
        score += 15
        reasons.append(f"Latest volume expanded to {volume_ratio:.2f}x")
    else:
        warnings.append(f"Volume expansion is weak ({volume_ratio:.2f}x)")

    if bull_count >= 3:
        score += 20
        reasons.append(f"{bull_count} consecutive bullish closes")
    elif bull_count >= 2:
        score += 12
        reasons.append(f"{bull_count} consecutive bullish closes")
    else:
        warnings.append("Consecutive bullish candle evidence is weak")

    if has_fvg_up:
        score += 20
        reasons.append("Upward FVG/imbalance detected: latest low is above previous high")
    else:
        warnings.append("No upward FVG/imbalance on the latest candle")

    if broke_range:
        score += 10
        reasons.append("Latest close broke above the accumulation range high")
    else:
        warnings.append("Price has not closed above the range high")

    state = "breakout_candidate" if score >= 65 else "watch"
    return RuleResult(
        name="breakout_accumulation",
        score=round(min(score, 100), 2),
        confidence=_confidence(score),  # type: ignore[arg-type]
        state=state,
        reasons=reasons,
        warnings=warnings,
        metrics={
            "lookback": lookback,
            "range_high": round(range_high, 6),
            "range_low": round(range_low, 6),
            "range_pct": round(range_pct, 6),
            "volume_ratio": round(volume_ratio, 4),
            "consecutive_bullish": bull_count,
            "has_fvg_up": has_fvg_up,
            "broke_range": broke_range,
        },
    )

