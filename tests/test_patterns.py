import unittest

from yongying.models import Candle
from yongying.patterns import analyze_patterns, candle_geometry


def candle(index: int, open_: float, high: float, low: float, close: float, volume: float = 1000) -> Candle:
    return Candle(
        timestamp=index,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def flat_base(count: int = 22, price: float = 10.0, volume: float = 1000) -> list[Candle]:
    candles = []
    for index in range(count):
        offset = 0.02 if index % 2 == 0 else -0.02
        candles.append(
            candle(
                index=index,
                open_=price + offset,
                high=price + 0.20,
                low=price - 0.20,
                close=price - offset,
                volume=volume,
            )
        )
    return candles


class PatternTests(unittest.TestCase):
    def test_candle_geometry_is_non_negative(self):
        geometry = candle_geometry(candle(1, 10.0, 10.8, 9.8, 10.2))
        self.assertGreaterEqual(geometry["upper_shadow_ratio"], 0)
        self.assertGreaterEqual(geometry["lower_shadow_ratio"], 0)
        self.assertGreaterEqual(geometry["body_ratio"], 0)

    def test_long_upper_shadow_triggers(self):
        candles = flat_base()
        candles.append(candle(99, 10.1, 11.4, 10.0, 10.2, 1200))
        patterns = analyze_patterns(candles)
        self.assertTrue(patterns["long_upper_shadow"].matched)
        self.assertFalse(patterns["long_lower_shadow"].matched)

    def test_bearish_engulfing_triggers(self):
        candles = flat_base()
        candles.append(candle(98, 10.0, 10.7, 9.9, 10.6, 1000))
        candles.append(candle(99, 10.7, 10.8, 9.7, 9.8, 1400))
        patterns = analyze_patterns(candles)
        self.assertTrue(patterns["bearish_engulfing"].matched)

    def test_bearish_engulfing_does_not_trigger_on_small_red_body(self):
        candles = flat_base()
        candles.append(candle(98, 10.0, 10.7, 9.9, 10.6, 1000))
        candles.append(candle(99, 10.5, 10.7, 10.1, 10.2, 1000))
        patterns = analyze_patterns(candles)
        self.assertFalse(patterns["bearish_engulfing"].matched)

    def test_volume_breakdown_triggers(self):
        candles = flat_base()
        candles.append(candle(99, 9.9, 10.0, 9.3, 9.5, 1800))
        patterns = analyze_patterns(candles)
        self.assertTrue(patterns["volume_breakdown"].matched)
        self.assertGreaterEqual(patterns["volume_breakdown"].metrics["volume_ratio"], 1.3)

    def test_volume_contraction_stabilization_triggers(self):
        candles = flat_base()
        candles.append(candle(99, 9.9, 10.08, 9.82, 10.02, 600))
        patterns = analyze_patterns(candles)
        self.assertTrue(patterns["volume_contraction_stabilization"].matched)
        self.assertFalse(patterns["volume_breakdown"].matched)

    def test_false_breakout_reversal_triggers(self):
        candles = flat_base()
        candles.append(candle(99, 10.15, 10.55, 9.95, 10.05, 1200))
        patterns = analyze_patterns(candles)
        self.assertTrue(patterns["false_breakout_reversal"].matched)

    def test_pullback_near_ma25_triggers_with_contracted_volume(self):
        candles = flat_base(price=10.2)
        candles.append(candle(99, 10.03, 10.18, 9.98, 10.08, 650))
        patterns = analyze_patterns(candles, ma25=10.05, atr=0.20)
        self.assertTrue(patterns["pullback_near_ma25"].matched)
        self.assertTrue(patterns["pullback_near_ma25"].metrics["volume_contracts"])

    def test_pullback_near_ma25_does_not_trigger_when_far_from_ma25(self):
        candles = flat_base(price=10.8)
        candles.append(candle(99, 10.75, 10.9, 10.70, 10.84, 650))
        patterns = analyze_patterns(candles, ma25=10.05, atr=0.20)
        self.assertFalse(patterns["pullback_near_ma25"].matched)

    def test_break_below_ma7_triggers_with_volume_expansion(self):
        candles = flat_base(price=10.2)
        candles.append(candle(99, 10.08, 10.10, 9.82, 9.90, 1600))
        patterns = analyze_patterns(candles, ma7=10.05)
        self.assertTrue(patterns["break_below_ma7"].matched)
        self.assertTrue(patterns["break_below_ma7"].metrics["close_below_ma7"])

    def test_break_below_ma7_does_not_trigger_without_volume(self):
        candles = flat_base(price=10.2)
        candles.append(candle(99, 10.08, 10.10, 9.82, 9.90, 900))
        patterns = analyze_patterns(candles, ma7=10.05)
        self.assertFalse(patterns["break_below_ma7"].matched)


if __name__ == "__main__":
    unittest.main()
