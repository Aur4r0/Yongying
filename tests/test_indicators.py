import unittest

from yongying.indicators import indicator_snapshot
from yongying.market_data import generate_demo_candles


class IndicatorTests(unittest.TestCase):
    def test_snapshot_has_core_values(self):
        candles = generate_demo_candles(bars=140)
        snapshot = indicator_snapshot(candles)
        self.assertGreater(snapshot.close, 0)
        self.assertIsNotNone(snapshot.ma7)
        self.assertIsNotNone(snapshot.ma25)
        self.assertIsNotNone(snapshot.boll_upper)
        self.assertIsNotNone(snapshot.rsi14)
        self.assertIsNotNone(snapshot.atr14)


if __name__ == "__main__":
    unittest.main()

