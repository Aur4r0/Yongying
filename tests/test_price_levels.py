import unittest

from yongying.models import Candle, IndicatorSnapshot
from yongying.price_levels import generate_price_levels, recent_resistance, recent_support


def candle(index: int, open_: float, high: float, low: float, close: float, volume: float = 1000) -> Candle:
    return Candle(index, open_, high, low, close, volume)


def sample_candles() -> list[Candle]:
    candles = []
    for index in range(24):
        base = 3.20 + index * 0.005
        candles.append(candle(index, base, base + 0.04, base - 0.04, base + 0.01))
    candles.append(candle(99, 3.38, 3.42, 3.34, 3.40, 1600))
    return candles


def snapshot() -> IndicatorSnapshot:
    return IndicatorSnapshot(
        close=3.40,
        ma7=3.34,
        ma25=3.27,
        boll_mid=3.30,
        boll_upper=3.45,
        boll_lower=3.15,
        rsi14=72.0,
        macd=0.05,
        macd_signal=0.04,
        macd_hist=0.01,
        atr14=0.05,
        volume=1600,
        volume_ma20=1000,
    )


class PriceLevelTests(unittest.TestCase):
    def test_support_and_resistance(self):
        candles = sample_candles()
        self.assertLess(recent_support(candles), recent_resistance(candles))

    def test_short_levels_are_ordered_downward(self):
        levels = generate_price_levels(sample_candles(), snapshot(), direction="SHORT")
        self.assertEqual(levels.direction, "SHORT")
        self.assertLess(levels.entry_range[0], levels.entry_range[1])
        self.assertGreater(levels.stop_loss, 3.40)
        self.assertEqual(levels.take_profits, sorted(levels.take_profits, reverse=True))
        self.assertTrue(all(tp < 3.40 for tp in levels.take_profits))
        self.assertGreaterEqual(len(levels.take_profits), 5)

    def test_long_levels_are_ordered_upward(self):
        levels = generate_price_levels(sample_candles(), snapshot(), direction="LONG")
        self.assertEqual(levels.direction, "LONG")
        self.assertLess(levels.entry_range[0], levels.entry_range[1])
        self.assertLess(levels.stop_loss, 3.40)
        self.assertEqual(levels.take_profits, sorted(levels.take_profits))
        self.assertTrue(all(tp > 3.40 for tp in levels.take_profits))
        self.assertGreaterEqual(len(levels.take_profits), 5)

    def test_wait_direction_rejected(self):
        with self.assertRaises(ValueError):
            generate_price_levels(sample_candles(), snapshot(), direction="WAIT")


if __name__ == "__main__":
    unittest.main()
