from __future__ import annotations

from .ai_writer import render_chinese_memo
from .indicators import indicator_snapshot
from .models import AnalysisResult, Candle
from .risk_policy import build_dual_signal_plans, build_signal_plan
from .strategy.breakout_accumulation import analyze_breakout_accumulation
from .strategy.breakdown_short import analyze_breakdown_short_signal
from .strategy.left_side_short import analyze_left_side_short
from .strategy.market_structure import analyze_market_structure
from .strategy.pullback_long import analyze_pullback_long_signal
from .strategy.wash_distribution import analyze_wash_distribution


def _aggregate_score(rules: list) -> float:
    by_name = {rule.name: rule for rule in rules}
    breakout = by_name["breakout_accumulation"]
    wash = by_name["wash_distribution"]
    structure = by_name["market_structure"]

    score = breakout.score * 0.50 + structure.score * 0.25

    if wash.state == "wash_candidate":
        score += min(wash.score, 75) * 0.20
    elif wash.state == "distribution_risk":
        score -= min(wash.score, 80) * 0.25
    else:
        score += 10

    return max(0.0, min(100.0, round(score, 2)))


def analyze_candles(
    candles: list[Candle],
    symbol: str,
    timeframe: str,
    source: str = "demo",
) -> AnalysisResult:
    if len(candles) < 60:
        raise ValueError("At least 60 candles are required for MVP analysis")

    indicators = indicator_snapshot(candles)
    rules = [
        analyze_breakout_accumulation(candles),
        analyze_wash_distribution(candles, indicators),
        analyze_market_structure(candles),
        analyze_left_side_short(candles, indicators),
        analyze_pullback_long_signal(candles, indicators),
        analyze_breakdown_short_signal(candles, indicators),
    ]
    aggregate = _aggregate_score(rules)
    plan = build_signal_plan(candles, indicators, rules, aggregate)
    aggressive_plan, conservative_plan = build_dual_signal_plans(candles, indicators, rules, aggregate)
    result = AnalysisResult(
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        last_price=candles[-1].close,
        aggregate_score=aggregate,
        plan=plan,
        indicators=indicators,
        rules=rules,
        memo_cn="",
        aggressive_plan=aggressive_plan,
        conservative_plan=conservative_plan,
    )
    result.memo_cn = render_chinese_memo(result)
    return result
