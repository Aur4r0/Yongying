from __future__ import annotations

from .models import Candle, IndicatorSnapshot, RuleResult, SignalPlan


def _round_price(value: float) -> float:
    if value >= 100:
        return round(value, 2)
    if value >= 1:
        return round(value, 4)
    return round(value, 6)


def _take_profits(entry: float, atr: float, direction: str) -> list[float]:
    multiples = [0.8, 1.2, 1.8, 2.5, 3.2]
    if direction == "LONG":
        return [_round_price(entry + atr * m) for m in multiples]
    return [_round_price(entry - atr * m) for m in multiples]


def build_signal_plan(
    candles: list[Candle],
    indicators: IndicatorSnapshot,
    rules: list[RuleResult],
    aggregate_score: float,
) -> SignalPlan:
    latest = candles[-1]
    atr = indicators.atr14 or max(latest.high - latest.low, latest.close * 0.01)
    rule_by_name = {rule.name: rule for rule in rules}
    breakout = rule_by_name["breakout_accumulation"]
    wash = rule_by_name["wash_distribution"]
    structure = rule_by_name["market_structure"]
    recent_support = min(c.low for c in candles[-20:])
    recent_resistance = max(c.high for c in candles[-20:])

    distribution_risk = wash.state == "distribution_risk"
    bullish_structure = structure.state in {"bullish_sms", "bullish_bms", "upside_pressure"}
    bearish_structure = structure.state in {"bearish_sms", "bearish_bms", "downside_pressure"}

    if breakout.score >= 65 and not distribution_risk and (bullish_structure or aggregate_score >= 70):
        entry_low = latest.close * 0.998
        entry_high = latest.close * 1.003
        stop = min(recent_support, latest.close - 1.35 * atr)
        return SignalPlan(
            direction="LONG",
            risk_level="medium" if aggregate_score >= 75 else "high",
            entry_range=(_round_price(entry_low), _round_price(entry_high)),
            take_profits=_take_profits(latest.close, atr, "LONG"),
            stop_loss=_round_price(stop),
            confirmation=[
                "Breakout accumulation score >= 65",
                "No active distribution-risk state",
                "Price holds above recent breakout area",
            ],
            invalidation=[
                "Close falls back into the 20-candle accumulation range",
                "Latest candle breaks MA25 with expanding volume",
                "Bearish SMS/BMS appears after entry",
            ],
            position_note="Research signal only. Use small test size or paper trading until backtested.",
        )

    if distribution_risk and bearish_structure:
        entry_low = latest.close * 0.997
        entry_high = latest.close * 1.002
        stop = max(recent_resistance, latest.close + 1.25 * atr)
        return SignalPlan(
            direction="SHORT",
            risk_level="high",
            entry_range=(_round_price(entry_low), _round_price(entry_high)),
            take_profits=_take_profits(latest.close, atr, "SHORT"),
            stop_loss=_round_price(stop),
            confirmation=[
                "Distribution-risk state is active",
                "Bearish SMS/BMS or downside pressure is active",
                "Rebound fails below recent resistance",
            ],
            invalidation=[
                "Price reclaims recent resistance",
                "Volume contracts and price recovers above MA25",
                "Bullish SMS/BMS appears",
            ],
            position_note="Research signal only. Short-side signals require stricter risk limits.",
        )

    return SignalPlan(
        direction="WAIT",
        risk_level="medium",
        entry_range=None,
        take_profits=[],
        stop_loss=None,
        confirmation=[
            "Wait for either a clean breakout confirmation or a confirmed distribution breakdown",
        ],
        invalidation=[
            "Current evidence is mixed or incomplete",
        ],
        position_note="No active trade plan. Continue monitoring.",
    )

