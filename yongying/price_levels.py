from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from .models import Candle, Direction, IndicatorSnapshot


LevelSource = Literal["indicator", "structure", "atr"]


@dataclass(frozen=True)
class ReferenceLevel:
    name: str
    price: float
    source: LevelSource


@dataclass(frozen=True)
class PriceLevelPlan:
    direction: Direction
    entry_range: tuple[float, float]
    take_profits: list[float]
    stop_loss: float
    references: list[ReferenceLevel] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def round_price(value: float) -> float:
    if value >= 100:
        return round(value, 2)
    if value >= 1:
        return round(value, 4)
    return round(value, 6)


def recent_support(candles: list[Candle], lookback: int = 20) -> float:
    if not candles:
        raise ValueError("At least one candle is required")
    window = candles[-lookback:]
    return min(c.low for c in window)


def recent_resistance(candles: list[Candle], lookback: int = 20) -> float:
    if not candles:
        raise ValueError("At least one candle is required")
    window = candles[-lookback:]
    return max(c.high for c in window)


def _atr(indicators: IndicatorSnapshot, latest: Candle) -> float:
    return indicators.atr14 or max(latest.high - latest.low, latest.close * 0.01)


def _dedupe_sorted(levels: list[float], direction: Direction, current: float, limit: int = 5) -> list[float]:
    if direction == "LONG":
        candidates = sorted(level for level in levels if level > current)
    elif direction == "SHORT":
        candidates = sorted((level for level in levels if level < current), reverse=True)
    else:
        return []

    out: list[float] = []
    seen: set[float] = set()
    for level in candidates:
        rounded = round_price(level)
        if rounded in seen:
            continue
        seen.add(rounded)
        out.append(rounded)
        if len(out) >= limit:
            break
    return out


def _fill_take_profits(levels: list[float], current: float, atr_value: float, direction: Direction, limit: int) -> list[float]:
    if len(levels) >= limit:
        return levels[:limit]

    filled = list(levels)
    step_multiples = [0.8, 1.2, 1.8, 2.5, 3.2, 4.0]
    for multiple in step_multiples:
        if direction == "LONG":
            candidate = round_price(current + atr_value * multiple)
        elif direction == "SHORT":
            candidate = round_price(current - atr_value * multiple)
        else:
            break
        if candidate not in filled:
            filled.append(candidate)
        if len(filled) >= limit:
            break
    if direction == "LONG":
        return sorted(filled)[:limit]
    if direction == "SHORT":
        return sorted(filled, reverse=True)[:limit]
    return []


def reference_levels(candles: list[Candle], indicators: IndicatorSnapshot, lookback: int = 20) -> list[ReferenceLevel]:
    support = recent_support(candles, lookback=lookback)
    resistance = recent_resistance(candles, lookback=lookback)
    refs = [
        ReferenceLevel("recent_support", round_price(support), "structure"),
        ReferenceLevel("recent_resistance", round_price(resistance), "structure"),
    ]

    indicator_map = {
        "ma7": indicators.ma7,
        "ma25": indicators.ma25,
        "boll_upper": indicators.boll_upper,
        "boll_mid": indicators.boll_mid,
        "boll_lower": indicators.boll_lower,
    }
    for name, price in indicator_map.items():
        if price is not None:
            refs.append(ReferenceLevel(name, round_price(price), "indicator"))
    return refs


def generate_price_levels(
    candles: list[Candle],
    indicators: IndicatorSnapshot,
    direction: Direction,
    lookback: int = 20,
    limit: int = 5,
) -> PriceLevelPlan:
    if direction == "WAIT":
        raise ValueError("WAIT direction does not have actionable price levels")
    if not candles:
        raise ValueError("At least one candle is required")

    latest = candles[-1]
    current = latest.close
    atr_value = _atr(indicators, latest)
    support = recent_support(candles, lookback=lookback)
    resistance = recent_resistance(candles, lookback=lookback)
    refs = reference_levels(candles, indicators, lookback=lookback)

    if direction == "LONG":
        entry_low = min(current - atr_value * 0.15, current * 0.998)
        entry_high = max(current + atr_value * 0.10, current * 1.002)
        raw_tps = [
            level
            for level in [
                indicators.ma7,
                indicators.ma25,
                indicators.boll_mid,
                resistance,
                indicators.boll_upper,
                current + atr_value * 1.5,
            ]
            if level is not None
        ]
        take_profits = _fill_take_profits(
            _dedupe_sorted(raw_tps, direction, current, limit=limit),
            current=current,
            atr_value=atr_value,
            direction=direction,
            limit=limit,
        )
        stop_candidates = [
            support - atr_value * 0.05,
            current - atr_value * 1.25,
        ]
        if indicators.boll_lower is not None:
            stop_candidates.append(indicators.boll_lower - atr_value * 0.15)
        stop_loss = min(stop_candidates)
    else:
        entry_low = min(current - atr_value * 0.10, current * 0.998)
        entry_high = max(current + atr_value * 0.15, current * 1.002)
        raw_tps = [
            level
            for level in [
                indicators.ma7,
                indicators.ma25,
                indicators.boll_mid,
                support,
                indicators.boll_lower,
                current - atr_value * 1.5,
            ]
            if level is not None
        ]
        take_profits = _fill_take_profits(
            _dedupe_sorted(raw_tps, direction, current, limit=limit),
            current=current,
            atr_value=atr_value,
            direction=direction,
            limit=limit,
        )
        stop_candidates = [
            resistance + atr_value * 0.05,
            current + atr_value * 1.25,
        ]
        if indicators.boll_upper is not None:
            stop_candidates.append(indicators.boll_upper + atr_value * 0.15)
        stop_loss = max(stop_candidates)

    return PriceLevelPlan(
        direction=direction,
        entry_range=(round_price(entry_low), round_price(entry_high)),
        take_profits=take_profits,
        stop_loss=round_price(stop_loss),
        references=refs,
    )
