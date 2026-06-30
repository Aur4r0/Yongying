import tempfile
import unittest
from pathlib import Path

from yongying.dashboard import DashboardConfig, build_dashboard_state, render_dashboard_html
from yongying.kline_cache import KlineCache
from yongying.market_data import generate_demo_candles
from yongying.signal_engine import analyze_candles
from yongying.signal_log import SignalLog
from yongying.templates.signal_cn import render_signal_cn


class DashboardTests(unittest.TestCase):
    def test_empty_cache_reports_no_cached_candles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = build_dashboard_state(
                DashboardConfig(
                    cache_path=str(Path(tmpdir) / "klines.sqlite"),
                    signal_log_path=str(Path(tmpdir) / "missing-signals.sqlite"),
                )
            )

        self.assertTrue(state["ok"])
        self.assertEqual(state["reason"], "no_cached_candles")
        self.assertEqual(state["loaded_count"], 0)
        self.assertIsNone(state["signal_text"])
        self.assertEqual(state["signal_history"]["status"], "missing")

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
        self.assertIn("最近信号记录", html)
        self.assertIn("PAIR $ORDI/USDT", html)

    def test_signal_history_reads_latest_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "klines.sqlite"
            signal_log_path = Path(tmpdir) / "signals.sqlite"
            candles = generate_demo_candles(bars=80)
            KlineCache(cache_path).save_candles("okx", "futures", "ORDI/USDT", "15m", candles)

            log = SignalLog(signal_log_path)
            analysis = analyze_candles(candles, symbol="ORDI/USDT", timeframe="15m", source="cache")
            log.save_analysis(
                analysis,
                signal_text=render_signal_cn(analysis),
                exchange="okx",
                market="futures",
                closed_timestamp=candles[-1].timestamp,
                reason="analyzed",
                created_at=1_700_000_000_000,
            )

            state = build_dashboard_state(
                DashboardConfig(cache_path=str(cache_path), signal_log_path=str(signal_log_path), limit=80)
            )

        self.assertEqual(state["signal_history"]["status"], "ok")
        self.assertEqual(len(state["signal_history"]["entries"]), 1)
        entry = state["signal_history"]["entries"][0]
        self.assertEqual(entry["symbol"], "ORDI/USDT")
        self.assertIn(entry["direction"], {"LONG", "SHORT", "WAIT"})
        self.assertIsInstance(entry["price"], float)
        self.assertIn("reason", entry)
        self.assertIn("reasons", entry)

    def test_signal_history_empty_database_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "klines.sqlite"
            signal_log_path = Path(tmpdir) / "signals.sqlite"
            SignalLog(signal_log_path)

            state = build_dashboard_state(
                DashboardConfig(cache_path=str(cache_path), signal_log_path=str(signal_log_path))
            )
            html = render_dashboard_html(state)

        self.assertEqual(state["signal_history"]["status"], "empty")
        self.assertIn("暂无最近信号记录", html)

    def test_signal_history_missing_database_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = build_dashboard_state(
                DashboardConfig(
                    cache_path=str(Path(tmpdir) / "klines.sqlite"),
                    signal_log_path=str(Path(tmpdir) / "missing-signals.sqlite"),
                )
            )
            html = render_dashboard_html(state)

        self.assertEqual(state["signal_history"]["status"], "missing")
        self.assertIn("signal log not found", state["signal_history"]["message"])
        self.assertIn("暂无最近信号记录", html)


if __name__ == "__main__":
    unittest.main()
