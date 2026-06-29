import unittest

from yongying.indicators import indicator_snapshot
from yongying.market_data import generate_demo_candles
from yongying.models import AnalysisResult, SignalPlan
from yongying.signal_engine import analyze_candles
from yongying.templates.signal_cn import render_signal_cn


class SignalTemplateCnTests(unittest.TestCase):
    def test_template_contains_core_sections(self):
        result = analyze_candles(generate_demo_candles(bars=140), symbol="ORDI/USDT", timeframe="15m")
        text = render_signal_cn(result)
        self.assertIn("PAIR $ORDI/USDT", text)
        self.assertIn("Entry Target", text)
        self.assertIn("Take Profits", text)
        self.assertIn("STOP LOSS", text)
        self.assertIn("稳健者", text)
        self.assertIn("免责声明", text)

    def test_template_uses_aggressive_short_plan(self):
        candles = generate_demo_candles(bars=140)
        indicators = indicator_snapshot(candles)
        base = analyze_candles(candles, symbol="ORDI/USDT", timeframe="15m")
        short_plan = SignalPlan(
            direction="SHORT",
            risk_level="high",
            entry_range=(3.38, 3.40),
            take_profits=[3.34, 3.30, 3.25, 3.20, 3.15],
            stop_loss=3.45,
            confirmation=["15m long upper shadow or bearish engulfing appears"],
            invalidation=["Breaks and holds above BOLL upper band"],
            position_note="test",
            leverage="Cross (3x)",
        )
        conservative = SignalPlan(
            direction="WAIT",
            risk_level="medium",
            entry_range=None,
            take_profits=[],
            stop_loss=None,
            confirmation=[
                "做多信号：价格回踩 MA25 附近，缩量企稳后再多",
                "做空信号：放量跌破 MA7 下方，右侧追空",
            ],
            invalidation=["Current evidence is incomplete"],
            position_note="test",
        )
        result = AnalysisResult(
            symbol=base.symbol,
            timeframe=base.timeframe,
            source=base.source,
            last_price=base.last_price,
            aggregate_score=base.aggregate_score,
            plan=base.plan,
            indicators=indicators,
            rules=base.rules,
            memo_cn=base.memo_cn,
            aggressive_plan=short_plan,
            conservative_plan=conservative,
        )
        text = render_signal_cn(result)
        self.assertIn("SHORT", text)
        self.assertIn("Cross (3x)", text)
        self.assertIn("3.38 ~ 3.4", text)
        self.assertIn("1. 3.34", text)
        self.assertIn("STOP LOSS：3.45", text)
        self.assertIn("做空信号", text)


if __name__ == "__main__":
    unittest.main()
