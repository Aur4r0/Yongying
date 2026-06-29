import unittest

from yongying.market_data import generate_demo_candles
from yongying.signal_engine import analyze_candles


class SignalEngineTests(unittest.TestCase):
    def test_demo_generates_analysis(self):
        candles = generate_demo_candles(bars=140)
        result = analyze_candles(candles, symbol="ORDI/USDT", timeframe="15m")
        self.assertEqual(result.symbol, "ORDI/USDT")
        self.assertGreaterEqual(result.aggregate_score, 0)
        self.assertLessEqual(result.aggregate_score, 100)
        self.assertEqual(len(result.rules), 3)
        self.assertIn("PAIR ORDI/USDT", result.memo_cn)

    def test_breakout_rule_present(self):
        candles = generate_demo_candles(bars=140)
        result = analyze_candles(candles, symbol="ORDI/USDT", timeframe="15m")
        rules = {rule.name: rule for rule in result.rules}
        self.assertIn("breakout_accumulation", rules)
        self.assertGreaterEqual(rules["breakout_accumulation"].score, 50)


if __name__ == "__main__":
    unittest.main()

