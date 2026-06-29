import unittest

from yongying.models import Candle, IndicatorSnapshot, RuleResult
from yongying.risk_policy import build_dual_signal_plans
from yongying.strategy.breakout_accumulation import analyze_breakout_accumulation
from yongying.strategy.market_structure import analyze_market_structure
from yongying.strategy.wash_distribution import analyze_wash_distribution


def candle(index: int, open_: float, high: float, low: float, close: float, volume: float = 1000) -> Candle:
    return Candle(index, open_, high, low, close, volume)


def short_sample_candles() -> list[Candle]:
    candles = []
    for index in range(24):
        base = 3.20 + index * 0.006
        candles.append(candle(index, base, base + 0.035, base - 0.035, base + 0.01, 1000))
    candles.append(candle(99, 3.40, 3.46, 3.36, 3.38, 1800))
    return candles


def short_snapshot() -> IndicatorSnapshot:
    return IndicatorSnapshot(
        close=3.38,
        ma7=3.34,
        ma25=3.27,
        boll_mid=3.30,
        boll_upper=3.45,
        boll_lower=3.15,
        rsi14=76.0,
        macd=0.04,
        macd_signal=0.05,
        macd_hist=-0.01,
        atr14=0.05,
        volume=1800,
        volume_ma20=1000,
    )


class ShortRiskPolicyTests(unittest.TestCase):
    def test_left_side_short_plan_has_short_risk_controls(self):
        candles = short_sample_candles()
        indicators = short_snapshot()
        rules = [
            analyze_breakout_accumulation(candles),
            analyze_wash_distribution(candles, indicators),
            analyze_market_structure(candles),
            RuleResult(
                name="left_side_short",
                score=86,
                confidence="high",
                state="left_side_short_candidate",
            ),
        ]
        aggressive, _ = build_dual_signal_plans(candles, indicators, rules, aggregate_score=45)
        self.assertEqual(aggressive.direction, "SHORT")
        self.assertEqual(aggressive.leverage, "Cross (3x)")
        self.assertIsNotNone(aggressive.entry_range)
        self.assertGreater(aggressive.stop_loss, indicators.close)
        self.assertGreaterEqual(aggressive.stop_loss, indicators.boll_upper)
        self.assertEqual(aggressive.take_profits, sorted(aggressive.take_profits, reverse=True))
        self.assertTrue(all(tp < indicators.close for tp in aggressive.take_profits))
        self.assertIn("very small size", aggressive.position_note)
        self.assertTrue(aggressive.invalidation)


if __name__ == "__main__":
    unittest.main()
