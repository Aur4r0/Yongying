import unittest

from yongying.indicators import indicator_snapshot
from yongying.market_data import generate_demo_candles
from yongying.models import RuleResult
from yongying.risk_policy import build_dual_signal_plans
from yongying.signal_engine import analyze_candles
from yongying.strategy.breakout_accumulation import analyze_breakout_accumulation
from yongying.strategy.market_structure import analyze_market_structure
from yongying.strategy.wash_distribution import analyze_wash_distribution


class DualPlanTests(unittest.TestCase):
    def test_analysis_result_keeps_primary_and_adds_dual_plans(self):
        result = analyze_candles(generate_demo_candles(bars=140), symbol="ORDI/USDT", timeframe="15m")
        payload = result.to_dict()
        self.assertIn("plan", payload)
        self.assertIn("aggressive_plan", payload)
        self.assertIn("conservative_plan", payload)
        self.assertIsNotNone(payload["aggressive_plan"])
        self.assertIsNotNone(payload["conservative_plan"])

    def test_left_side_short_can_drive_aggressive_plan(self):
        candles = generate_demo_candles(bars=140)
        indicators = indicator_snapshot(candles)
        rules = [
            analyze_breakout_accumulation(candles),
            analyze_wash_distribution(candles, indicators),
            analyze_market_structure(candles),
            RuleResult(
                name="left_side_short",
                score=82,
                confidence="high",
                state="left_side_short_candidate",
                reasons=["test left-side short evidence"],
            ),
        ]
        aggressive, conservative = build_dual_signal_plans(candles, indicators, rules, aggregate_score=40)
        self.assertEqual(aggressive.direction, "SHORT")
        self.assertEqual(aggressive.risk_level, "high")
        self.assertEqual(conservative.direction, "WAIT")
        self.assertTrue(aggressive.confirmation)


if __name__ == "__main__":
    unittest.main()
