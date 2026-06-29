import unittest

from yongying.models import Candle, IndicatorSnapshot
from yongying.strategy.breakout_accumulation import analyze_breakout_accumulation
from yongying.strategy.market_structure import analyze_market_structure
from yongying.strategy.wash_distribution import analyze_wash_distribution


def candle(index: int, open_: float, high: float, low: float, close: float, volume: float = 1000) -> Candle:
    return Candle(index, open_, high, low, close, volume)


def snapshot(close: float = 10.0, ma25: float = 10.0) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        close=close,
        ma7=10.1,
        ma25=ma25,
        boll_mid=10.0,
        boll_upper=10.5,
        boll_lower=9.5,
        rsi14=55.0,
        macd=0.0,
        macd_signal=0.0,
        macd_hist=0.0,
        atr14=0.2,
        volume=1000,
        volume_ma20=1000,
    )


def compressed_base(count: int = 20) -> list[Candle]:
    return [candle(index, 10.0, 10.1, 9.9, 10.02, 1000) for index in range(count)]


def context_base(count: int = 60) -> list[Candle]:
    return [candle(index, 10.0, 10.2, 9.8, 10.05, 1000) for index in range(count)]


class CoreStrategyTests(unittest.TestCase):
    def test_breakout_accumulation_candidate(self):
        candles = compressed_base()
        candles.extend(
            [
                candle(20, 10.02, 10.15, 9.98, 10.08, 1100),
                candle(21, 10.09, 10.25, 10.02, 10.18, 1200),
                candle(22, 10.35, 10.60, 10.30, 10.55, 2600),
            ]
        )
        result = analyze_breakout_accumulation(candles)
        self.assertEqual(result.state, "breakout_candidate")
        self.assertTrue(result.metrics["has_fvg_up"])
        self.assertTrue(result.metrics["broke_range"])

    def test_breakout_accumulation_watch_without_breakout(self):
        candles = compressed_base()
        candles.extend(
            [
                candle(20, 10.02, 10.15, 9.98, 10.08, 1000),
                candle(21, 10.05, 10.12, 9.96, 10.02, 800),
            ]
        )
        result = analyze_breakout_accumulation(candles)
        self.assertNotEqual(result.state, "breakout_candidate")
        self.assertFalse(result.metrics["broke_range"])

    def test_wash_distribution_wash_candidate(self):
        candles = context_base()
        candles.append(candle(99, 10.0, 10.15, 9.75, 10.08, 600))
        result = analyze_wash_distribution(candles, snapshot(close=10.08, ma25=10.0))
        self.assertEqual(result.state, "wash_candidate")
        self.assertGreater(result.metrics["wash_score"], result.metrics["distribution_score"])

    def test_wash_distribution_distribution_risk(self):
        candles = context_base()
        candles.append(candle(99, 10.1, 10.6, 9.4, 9.5, 1700))
        result = analyze_wash_distribution(candles, snapshot(close=9.5, ma25=10.0))
        self.assertEqual(result.state, "distribution_risk")
        self.assertGreater(result.metrics["distribution_score"], result.metrics["wash_score"])

    def test_wash_distribution_neutral_without_edge(self):
        candles = context_base()
        candles.append(candle(99, 10.0, 10.15, 9.95, 10.05, 1000))
        result = analyze_wash_distribution(candles, snapshot(close=10.05, ma25=10.0))
        self.assertEqual(result.state, "neutral")

    def test_market_structure_bullish_bms(self):
        candles = [candle(index, 10.2, 10.6, 10.2, 10.3) for index in range(30)]
        candles[5] = candle(5, 10.4, 11.0, 10.3, 10.7)
        candles[10] = candle(10, 9.4, 9.8, 9.0, 9.5)
        candles[15] = candle(15, 11.2, 12.0, 11.0, 11.6)
        candles[20] = candle(20, 10.0, 10.4, 9.8, 10.1)
        candles[29] = candle(29, 12.0, 12.5, 11.9, 12.3)
        result = analyze_market_structure(candles)
        self.assertEqual(result.state, "bullish_bms")
        self.assertTrue(result.metrics["higher_low"])
        self.assertTrue(result.metrics["broke_last_high"])

    def test_market_structure_bearish_bms(self):
        candles = [candle(index, 10.2, 10.6, 10.2, 10.3) for index in range(30)]
        candles[5] = candle(5, 11.2, 12.0, 11.0, 11.6)
        candles[10] = candle(10, 10.0, 10.4, 9.8, 10.1)
        candles[15] = candle(15, 10.6, 11.0, 10.4, 10.7)
        candles[20] = candle(20, 9.7, 10.1, 9.5, 9.8)
        candles[29] = candle(29, 9.4, 9.5, 9.0, 9.2)
        result = analyze_market_structure(candles)
        self.assertEqual(result.state, "bearish_bms")
        self.assertTrue(result.metrics["lower_high"])
        self.assertTrue(result.metrics["broke_last_low"])

    def test_market_structure_unclear_without_pivots(self):
        candles = [candle(index, 10.0, 10.1, 9.9, 10.02) for index in range(30)]
        result = analyze_market_structure(candles)
        self.assertEqual(result.state, "unclear")


if __name__ == "__main__":
    unittest.main()
