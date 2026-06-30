import tempfile
import unittest
from pathlib import Path

from yongying.dashboard import DashboardConfig, build_dashboard_state, render_dashboard_html
from yongying.kline_cache import KlineCache
from yongying.market_data import generate_demo_candles


class DashboardTests(unittest.TestCase):
    def test_empty_cache_reports_no_cached_candles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = build_dashboard_state(DashboardConfig(cache_path=str(Path(tmpdir) / "klines.sqlite")))

        self.assertTrue(state["ok"])
        self.assertEqual(state["reason"], "no_cached_candles")
        self.assertEqual(state["loaded_count"], 0)
        self.assertIsNone(state["signal_text"])

    def test_cached_candles_generate_signal_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "klines.sqlite"
            cache = KlineCache(cache_path)
            cache.save_candles("okx", "futures", "ORDI/USDT", "15m", generate_demo_candles(bars=80))

            state = build_dashboard_state(DashboardConfig(cache_path=str(cache_path), limit=80))

        self.assertEqual(state["reason"], "ok")
        self.assertEqual(state["loaded_count"], 80)
        self.assertEqual(state["closed_count"], 79)
        self.assertIsNotNone(state["analysis"])
        self.assertIn("PAIR $ORDI/USDT", state["signal_text"])

    def test_render_dashboard_html_contains_chart_and_signal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "klines.sqlite"
            cache = KlineCache(cache_path)
            cache.save_candles("okx", "futures", "ORDI/USDT", "15m", generate_demo_candles(bars=80))
            state = build_dashboard_state(DashboardConfig(cache_path=str(cache_path), limit=80))

        html = render_dashboard_html(state)

        self.assertIn("Yongying 本地监控 Dashboard", html)
        self.assertIn("canvas", html)
        self.assertIn("当前信号", html)
        self.assertIn("PAIR $ORDI/USDT", html)


if __name__ == "__main__":
    unittest.main()
