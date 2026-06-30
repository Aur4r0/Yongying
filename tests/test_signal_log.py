import tempfile
import unittest
from pathlib import Path

from yongying.market_data import generate_demo_candles
from yongying.signal_engine import analyze_candles
from yongying.signal_log import SignalLog
from yongying.templates.signal_cn import render_signal_cn


class SignalLogTests(unittest.TestCase):
    def test_save_and_read_latest_signal(self):
        candles = generate_demo_candles(bars=80)
        analysis = analyze_candles(candles, symbol="ORDI/USDT", timeframe="15m", source="cache")
        signal_text = render_signal_cn(analysis)

        with tempfile.TemporaryDirectory() as tmpdir:
            log = SignalLog(Path(tmpdir) / "signals.sqlite")
            record_id = log.save_analysis(
                analysis,
                signal_text=signal_text,
                exchange="okx",
                market="futures",
                closed_timestamp=candles[-1].timestamp,
                reason="analyzed",
                created_at=1234567890,
            )
            entries = log.latest(exchange="OKX", market="FUTURES", symbol="ORDI/USDT", timeframe="15m")

        self.assertEqual(record_id, 1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].symbol, "ORDI/USDT")
        self.assertEqual(entries[0].exchange, "OKX")
        self.assertEqual(entries[0].market, "FUTURES")
        self.assertIn(entries[0].display_direction, {"LONG", "SHORT", "WAIT"})
        self.assertIn("PAIR $ORDI/USDT", entries[0].signal_text)
        self.assertEqual(entries[0].analysis["symbol"], "ORDI/USDT")

    def test_latest_requires_positive_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = SignalLog(Path(tmpdir) / "signals.sqlite")
            with self.assertRaises(ValueError):
                log.latest(limit=0)


if __name__ == "__main__":
    unittest.main()
