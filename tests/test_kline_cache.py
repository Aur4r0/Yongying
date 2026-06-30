import tempfile
import unittest
from pathlib import Path

from yongying.kline_cache import KlineCache, check_candle_continuity, timeframe_to_milliseconds, update_cached_candles
from yongying.models import Candle


def candle(index: int, timestamp: int | None = None) -> Candle:
    ts = 1_700_000_000_000 + index * 60_000 if timestamp is None else timestamp
    price = 3.0 + index * 0.01
    return Candle(ts, price, price + 0.02, price - 0.02, price + 0.01, 1000 + index)


class KlineCacheTests(unittest.TestCase):
    def test_timeframe_to_milliseconds(self):
        self.assertEqual(timeframe_to_milliseconds("1m"), 60_000)
        self.assertEqual(timeframe_to_milliseconds("15m"), 900_000)
        self.assertEqual(timeframe_to_milliseconds("4h"), 14_400_000)
        with self.assertRaises(ValueError):
            timeframe_to_milliseconds("bad")

    def test_save_load_and_dedupe_candles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = KlineCache(Path(tmpdir) / "klines.sqlite")
            candles = [candle(0), candle(1), candle(1), candle(2)]
            stored = cache.save_candles("binance", "futures", "ORDI/USDT", "1m", candles)
            loaded = cache.load_candles("BINANCE", "FUTURES", "ORDI/USDT", "1m")

        self.assertEqual(stored, 3)
        self.assertEqual([item.timestamp for item in loaded], [candle(0).timestamp, candle(1).timestamp, candle(2).timestamp])
        self.assertEqual(loaded[-1].close, candle(2).close)

    def test_load_limit_returns_latest_candles_in_ascending_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = KlineCache(Path(tmpdir) / "klines.sqlite")
            cache.save_candles("binance", "futures", "ORDI/USDT", "1m", [candle(i) for i in range(5)])
            loaded = cache.load_candles("binance", "futures", "ORDI/USDT", "1m", limit=2)

        self.assertEqual([item.timestamp for item in loaded], [candle(3).timestamp, candle(4).timestamp])

    def test_continuity_report_detects_gap(self):
        candles = [candle(0), candle(1), candle(3)]
        report = check_candle_continuity(candles, "1m")

        self.assertFalse(report.is_continuous)
        self.assertEqual(len(report.gaps), 1)
        self.assertEqual(report.gaps[0].missing_count, 1)

    def test_update_cached_candles_fetches_from_next_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "klines.sqlite"
            cache = KlineCache(cache_path)
            cache.save_candles("binance", "futures", "ORDI/USDT", "1m", [candle(0), candle(1)])
            calls = []

            def fetcher(**kwargs):
                calls.append(kwargs)
                return [candle(2), candle(3)]

            result = update_cached_candles(
                cache_path=cache_path,
                exchange="binance",
                market="futures",
                symbol="ORDI/USDT",
                timeframe="1m",
                limit=200,
                fetcher=fetcher,
            )
            loaded = cache.load_candles("binance", "futures", "ORDI/USDT", "1m")

        self.assertEqual(calls[0]["start_time"], candle(2).timestamp)
        self.assertEqual(result.fetched_count, 2)
        self.assertEqual(result.stored_count, 2)
        self.assertEqual(result.cached_count, 4)
        self.assertTrue(result.continuity.is_continuous)
        self.assertEqual([item.timestamp for item in loaded], [candle(i).timestamp for i in range(4)])

    def test_update_cached_candles_without_existing_cache_fetches_without_start_time(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "klines.sqlite"
            calls = []

            def fetcher(**kwargs):
                calls.append(kwargs)
                return [candle(0), candle(1)]

            result = update_cached_candles(
                cache_path=cache_path,
                exchange="binance",
                market="futures",
                symbol="ORDI/USDT",
                timeframe="1m",
                fetcher=fetcher,
            )

        self.assertIsNone(calls[0]["start_time"])
        self.assertIsNone(result.latest_before)
        self.assertEqual(result.latest_after, candle(1).timestamp)


if __name__ == "__main__":
    unittest.main()
