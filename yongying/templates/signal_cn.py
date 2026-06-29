from __future__ import annotations

from ..models import AnalysisResult, SignalPlan


def _pair(symbol: str) -> str:
    return symbol if symbol.startswith("$") else f"${symbol}"


def _entry(plan: SignalPlan) -> str:
    if plan.entry_range is None:
        return "等待确认"
    return f"{plan.entry_range[0]} ~ {plan.entry_range[1]}"


def _take_profits(plan: SignalPlan) -> list[str]:
    labels = ["1", "2", "3", "4", "5"]
    return [f"{labels[index]}. {price}" for index, price in enumerate(plan.take_profits[:5])]


def _stop_loss(plan: SignalPlan) -> str:
    if plan.stop_loss is None:
        return "等待确认"
    return str(plan.stop_loss)


def _aggressive_title(plan: SignalPlan) -> str:
    if plan.direction == "SHORT":
        return "⚠️ 激进者：左侧轻仓试空（极轻仓）"
    if plan.direction == "LONG":
        return "⚠️ 激进者：轻仓试多（小仓确认）"
    return "⚠️ 激进者：观望"


def _direction_line(plan: SignalPlan) -> str:
    if plan.direction == "SHORT":
        return "💎 SHORT（左侧摸顶，极轻仓）"
    if plan.direction == "LONG":
        return "💎 LONG（回踩/突破确认，轻仓）"
    return "💎 WAIT（等待确认）"


def _conservative_title(plan: SignalPlan) -> str:
    if plan.direction == "WAIT":
        return "✅ 稳健者：观望，等待确认"
    if plan.direction == "LONG":
        return "✅ 稳健者：回踩确认做多（轻仓）"
    return "✅ 稳健者：右侧跌破做空（轻仓）"


def _compact_take_profits(plan: SignalPlan) -> str:
    if not plan.take_profits:
        return "等待确认"
    return " / ".join(str(price) for price in plan.take_profits[:5])


def render_signal_cn(result: AnalysisResult) -> str:
    aggressive = result.aggressive_plan or result.plan
    conservative = result.conservative_plan or result.plan
    lines: list[str] = []

    lines.append(_aggressive_title(aggressive))
    lines.append("")
    lines.append(f"PAIR {_pair(result.symbol)}")
    lines.append(_direction_line(aggressive))
    if aggressive.leverage:
        lines.append(aggressive.leverage)
    lines.append("")
    lines.append("✔️ Entry Target（开仓范围）：")
    lines.append(_entry(aggressive))
    if aggressive.confirmation:
        lines.append(f"（{aggressive.confirmation[0]}）")
    lines.append("")
    lines.append("☑️ Take Profits：")
    take_profits = _take_profits(aggressive)
    if take_profits:
        lines.extend(take_profits)
    else:
        lines.append("等待确认")
    lines.append("")
    lines.append(f"❌ STOP LOSS：{_stop_loss(aggressive)}")
    if aggressive.invalidation:
        lines.append(f"（{aggressive.invalidation[0]}）")
    lines.append("")
    lines.append(_conservative_title(conservative))
    lines.append("")
    if conservative.confirmation:
        for item in conservative.confirmation:
            lines.append(f"· {item}")
    else:
        lines.append("· 等待新的结构化信号")
    if conservative.direction != "WAIT":
        lines.append(f"· 稳健入场：{_entry(conservative)}")
        lines.append(f"· 稳健止盈：{_compact_take_profits(conservative)}")
        lines.append(f"· 稳健止损：{_stop_loss(conservative)}")
    lines.append("")
    lines.append("免责声明：这是项目研发输出，不构成投资建议或自动下单指令。")
    return "\n".join(lines)
