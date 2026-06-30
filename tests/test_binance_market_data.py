import io
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

from yongying.exchanges.binance import (
    EmptyKlineResponseError,
    ExchangeRateLimitError,
    ExchangeRequestError,
    InvalidSymbolError,
    UnsupportedTimeframeError,
    binance_klines_to_candles,
    build_klines_url,
    fetch_binance_klines,
    to_binance_symbol,
)
from yongying.market_data import load_candles
from yongying.models import Candle


BINANCE_ROW = [
    1700000000000,
    "3.3800",
    "3.4200",
    "3.3300",
    "3.4000",
    "12345.67",
    1700000899999,
    "0",
    42,
    "0",
    "0",
    "0",
]


class BinanceMarketDataTests(unittest.TestCase):
    def test_symbol_format_conversion(self):
        self.assertEqual(to_binance_symbol("ORDI/USDT"), "ORDIUSDT")
        self.assertEqual(to_binance_symbol("ordi/usdt"), "ORDIUSDT")
        self.assertEqual(to_binance_symbol("ORDIUSDT"), "ORDIUSDT")
        with self.assertRaises(InvalidSymbolError):
            to_binance_symbol("ORDI/")

    def test_timeframe_and_query_params(self):
        url = build_klines_url(
            symbol="ORDI/USDT",
            timeframe="15m",
            limit=200,
            start_time=1700000000000,
            end_time=1700000900000,
        )
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "fapi.binance.com")
        self.assertEqual(parsed.path, "/fapi/v1/klines")
        self.assertEqual(params["symbol"], ["ORDIUSDT"])
        self.assertEqual(params["interval"], ["15m"])
        self.assertEqual(params["limit"], ["200"])
        self.assertEqual(params["startTime"], ["1700000000000"])
        self.assertEqual(params["endTime"], ["1700000900000"])
        with self.assertRaises(UnsupportedTimeframeError):
            build_klines_url(symbol="ORDI/USDT", timeframe="2x", limit=200)

    def test_binance_response_converts_to_candle(self):
        candles = binance_klines_to_candles([BINANCE_ROW])
        self.assertEqual(
            candles,
            [
                Candle(
                    timestamp=1700000000000,
                    open=3.38,
                    high=3.42,
                    low=3.33,
                    close=3.4,
                    volume=12345.67,
                )
            ],
        )

    def test_fetch_binance_klines_uses_mock_transport(self):
        observed = {}

        def transport(url, timeout):
            observed["url"] = url
            observed["timeout"] = timeout
            return [BINANCE_ROW]

        candles = fetch_binance_klines("ORDI/USDT", timeframe="1h", limit=200, transport=transport, timeout=3.0)
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].close, 3.4)
        self.assertIn("interval=1h", observed["url"])
        self.assertEqual(observed["timeout"], 3.0)

    def test_empty_response_raises_clear_error(self):
        with self.assertRaises(EmptyKlineResponseError):
            fetch_binance_klines("ORDI/USDT", transport=lambda url, timeout: [])

    def test_network_exception_raises_clear_error(self):
        def transport(url, timeout):
            raise urllib.error.URLError("temporary DNS failure")

        with self.assertRaisesRegex(ExchangeRequestError, "network error"):
            fetch_binance_klines("ORDI/USDT", transport=transport)

    def test_rate_limit_http_error_raises_clear_error(self):
        def transport(url, timeout):
            raise urllib.error.HTTPError(
                url,
                429,
                "Too Many Requests",
                {},
                io.BytesIO(b'{"code":-1003,"msg":"Too many requests"}'),
            )

        with self.assertRaisesRegex(ExchangeRateLimitError, "rate limit"):
            fetch_binance_klines("ORDI/USDT", transport=transport)

    def test_load_candles_live_binance_routes_to_adapter(self):
        with patch("yongying.market_data.fetch_binance_klines") as fetcher:
            fetcher.return_value = [Candle(1700000000000, 3.38, 3.42, 3.33, 3.4, 12345.67)]
            candles = load_candles(
                symbol="ORDI/USDT",
                timeframe="15m",
                source="live",
                exchange="binance",
                limit=200,
            )
        self.assertEqual(candles[0].close, 3.4)
        fetcher.assert_called_once_with(
            symbol="ORDI/USDT",
            timeframe="15m",
            limit=200,
            market="futures",
            start_time=None,
            end_time=None,
        )

    def test_demo_source_stays_offline(self):
        candles = load_candles(symbol="ORDI/USDT", timeframe="15m", source="demo", limit=10)
        self.assertEqual(len(candles), 10)
        self.assertTrue(all(c.low <= c.open <= c.high and c.low <= c.close <= c.high for c in candles))


if __name__ == "__main__":
    unittest.main()
