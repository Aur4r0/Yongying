from __future__ import annotations

from .models import AnalysisResult


def render_chinese_memo(result: AnalysisResult) -> str:
    plan = result.plan
    lines: list[str] = []
    lines.append(f"PAIR {result.symbol}")
    lines.append(f"TIMEFRAME {result.timeframe}")
    lines.append(f"SIGNAL {plan.direction}")
    lines.append(f"AGGREGATE SCORE {result.aggregate_score:.1f}/100")
    lines.append("")
    lines.append("核心判断：")

    if plan.direction == "LONG":
        entry = f"{plan.entry_range[0]} ~ {plan.entry_range[1]}" if plan.entry_range else "等待回踩确认"
        lines.append(f"激进方案：突破蓄势信号成立，允许研究性轻仓观察。入场区间：{entry}。")
    elif plan.direction == "SHORT":
        entry = f"{plan.entry_range[0]} ~ {plan.entry_range[1]}" if plan.entry_range else "等待反弹确认"
        lines.append(f"风险方案：出货/破位信号偏强，仅适合研究性观察。入场区间：{entry}。")
    else:
        lines.append("当前证据不足，不生成方向性交易计划，继续等待确认信号。")

    if plan.take_profits:
        lines.append("止盈参考：" + " / ".join(str(tp) for tp in plan.take_profits))
    if plan.stop_loss is not None:
        lines.append(f"失效/止损参考：{plan.stop_loss}")

    lines.append("")
    lines.append("确认条件：")
    for item in plan.confirmation:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("失效条件：")
    for item in plan.invalidation:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("规则证据：")
    for rule in result.rules:
        lines.append(f"- {rule.name}: {rule.state}, score={rule.score}, confidence={rule.confidence}")
        for reason in rule.reasons[:3]:
            lines.append(f"  - {reason}")
        for warning in rule.warnings[:2]:
            lines.append(f"  - 风险：{warning}")

    lines.append("")
    lines.append(f"仓位备注：{plan.position_note}")
    lines.append("免责声明：这是项目研发输出，不构成投资建议或自动下单指令。")
    return "\n".join(lines)

