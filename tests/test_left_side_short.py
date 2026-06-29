import unittest

from yongying.models import Candle, IndicatorSnapshot
from yongying.strategy.left_side_short import analyze_left_side_short


def candle(index: int, open_: float, high: float, low: float, close: float, volume: float = 1000) -> Candle:
    return Candle(index, open_, high, low, close, volume)


def base_candles(count: int = 24) -> list[Candle]:
    candles = []
    price = 10.0
    for index in range(count):
        price += 0.02
        candles.append(candle(index, price, price + 0.12, price - 0.12, price + 0.03, 1000))
    return candles


def snapshot(close: float, rsi: float = 76.0) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        close=close,
        ma7=10.50,
        ma25=10.00,
        boll_mid=10.20,
        boll_upper=10.80,
        boll_lower=9.60,
        rsi14=rsi,
        macd=0.1,
        macd_signal=0.08,
        macd_hist=0.02,
        atr14=0.25,
        volume=1600,
        volume_ma20=1000,
    )


class LeftSideShortTests(unittest.TestCase):
    def test_left_side_short_candidate_from_rejection(self):
        candles = base_candles()
        candles.append(candle(98, 10.50, 10.90, 10.40, 10.85, 1100))
        candles.append(candle(99, 10.92, 11.80, 10.35, 10.45, 1700))
        result = analyze_left_side_short(candles, snapshot(close=10.45))
        self.assertEqual(result.state, "left_side_short_candidate")
        self.assertGreaterEqual(result.score, 70)
        self.assertTrue(result.metrics["long_upper_shadow"])
        self.assertTrue(result.metrics["bearish_engulfing"])

    def test_watch_top_when_only_overheated_near_band(self):
        candles = base_candles()
        candles.append(candle(99, 10.70, 10.86, 10.64, 10.78, 1000))
        result = analyze_left_side_short(candles, snapshot(close=10.78, rsi=72.0))
        self.assertIn(result.state, {"watch_top", "no_short"})
        self.assertLess(result.score, 70)

    def test_no_short_without_top_evidence(self):
        candles = base_candles()
        candles.append(candle(99, 10.05, 10.18, 9.95, 10.12, 900))
        result = analyze_left_side_short(candles, snapshot(close=10.12, rsi=55.0))
        self.assertEqual(result.state, "no_short")
        self.assertLess(result.score, 50)


if __name__ == "__main__":
    unittest.main()
