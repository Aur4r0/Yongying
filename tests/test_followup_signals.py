import unittest

from yongying.models import Candle, IndicatorSnapshot
from yongying.strategy.followup_signals import (
    analyze_breakdown_short_signal,
    analyze_pullback_long_signal,
)


def candle(index: int, open_: float, high: float, low: float, close: float, volume: float = 1000) -> Candle:
    return Candle(index, open_, high, low, close, volume)


def base_candles(count: int = 24, price: float = 3.30, volume: float = 1000) -> list[Candle]:
    candles = []
    for index in range(count):
        drift = (index % 4) * 0.003
        candles.append(candle(index, price + drift, price + drift + 0.03, price + drift - 0.03, price + drift + 0.005, volume))
    return candles


def snapshot(close: float = 3.30) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        close=close,
        ma7=3.31,
        ma25=3.28,
        boll_mid=3.30,
        boll_upper=3.45,
        boll_lower=3.15,
        rsi14=52.0,
        macd=0.01,
        macd_signal=0.01,
        macd_hist=0.0,
        atr14=0.04,
        volume=700,
        volume_ma20=1000,
    )


class FollowupSignalTests(unittest.TestCase):
    def test_pullback_long_candidate(self):
        candles = base_candles()
        candles.append(candle(99, 3.27, 3.31, 3.265, 3.295, 650))
        result = analyze_pullback_long_signal(candles, snapshot(close=3.295))
        self.assertEqual(result.state, "pullback_long_candidate")
        self.assertGreaterEqual(result.score, 70)
        self.assertTrue(result.metrics["stabilizes"])

    def test_pullback_long_not_triggered_when_volume_expands(self):
        candles = base_candles()
        candles.append(candle(99, 3.27, 3.31, 3.265, 3.295, 1600))
        result = analyze_pullback_long_signal(candles, snapshot(close=3.295))
        self.assertNotEqual(result.state, "pullback_long_candidate")

    def test_breakdown_short_candidate(self):
        candles = base_candles()
        candles.append(candle(99, 3.29, 3.30, 3.20, 3.22, 1800))
        result = analyze_breakdown_short_signal(candles, snapshot(close=3.22))
        self.assertEqual(result.state, "breakdown_short_candidate")
        self.assertGreaterEqual(result.score, 70)
        self.assertTrue(result.metrics["close_below_ma7"])

    def test_breakdown_short_not_triggered_without_volume(self):
        candles = base_candles()
        candles.append(candle(99, 3.29, 3.30, 3.20, 3.22, 800))
        result = analyze_breakdown_short_signal(candles, snapshot(close=3.22))
        self.assertNotEqual(result.state, "breakdown_short_candidate")


if __name__ == "__main__":
    unittest.main()
