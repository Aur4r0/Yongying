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
)
from yongying.exchanges.okx import (
    build_candles_url,
    fetch_okx_candles,
    okx_candles_to_candles,
    to_okx_inst_id,
)
from yongying.market_data import load_candles
from yongying.models import Candle


OKX_PAYLOAD = {
    "code": "0",
    "msg": "",
    "data": [
        ["1700000900000", "3.40", "3.44", "3.36", "3.41", "20", "2.0", "6.82", "0"],
        ["1700000000000", "3.38", "3.42", "3.33", "3.40", "10", "1.0", "3.40", "1"],
    ],
}


class OkxMarketDataTests(unittest.TestCase):
    def test_symbol_format_conversion(self):
        self.assertEqual(to_okx_inst_id("ORDI/USDT"), "ORDI-USDT-SWAP")
        self.assertEqual(to_okx_inst_id("ordi/usdt"), "ORDI-USDT-SWAP")
        self.assertEqual(to_okx_inst_id("ORDI-USDT-SWAP"), "ORDI-USDT-SWAP")
        self.assertEqual(to_okx_inst_id("ORDI/USDT", market="spot"), "ORDI-USDT")
        with self.assertRaises(InvalidSymbolError):
            to_okx_inst_id("ORDI/")

    def test_timeframe_and_query_params(self):
        url = build_candles_url(
            symbol="ORDI/USDT",
            timeframe="1h",
            limit=200,
            start_time=1700000000000,
            end_time=1700000900000,
        )
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "www.okx.com")
        self.assertEqual(parsed.path, "/api/v5/market/candles")
        self.assertEqual(params["instId"], ["ORDI-USDT-SWAP"])
        self.assertEqual(params["bar"], ["1H"])
        self.assertEqual(params["limit"], ["200"])
        self.assertEqual(params["before"], ["1699999999999"])
        self.assertEqual(params["after"], ["1700000900001"])
        with self.assertRaises(UnsupportedTimeframeError):
            build_candles_url(symbol="ORDI/USDT", timeframe="2x", limit=200)

    def test_okx_response_converts_to_ascending_candles(self):
        candles = okx_candles_to_candles(OKX_PAYLOAD)
        self.assertEqual(
            candles,
            [
                Candle(
                    timestamp=1700000000000,
                    open=3.38,
                    high=3.42,
                    low=3.33,
                    close=3.4,
                    volume=1.0,
                ),
                Candle(
                    timestamp=1700000900000,
                    open=3.4,
                    high=3.44,
                    low=3.36,
                    close=3.41,
                    volume=2.0,
                ),
            ],
        )

    def test_fetch_okx_candles_uses_mock_transport(self):
        observed = {}

        def transport(url, timeout):
            observed["url"] = url
            observed["timeout"] = timeout
            return OKX_PAYLOAD

        candles = fetch_okx_candles("ORDI/USDT", timeframe="15m", limit=200, transport=transport, timeout=3.0)
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[-1].close, 3.41)
        self.assertIn("bar=15m", observed["url"])
        self.assertEqual(observed["timeout"], 3.0)

    def test_empty_response_raises_clear_error(self):
        with self.assertRaises(EmptyKlineResponseError):
            fetch_okx_candles("ORDI/USDT", transport=lambda url, timeout: {"code": "0", "msg": "", "data": []})

    def test_network_exception_raises_clear_error(self):
        def transport(url, timeout):
            raise urllib.error.URLError("temporary DNS failure")

        with self.assertRaisesRegex(ExchangeRequestError, "network error"):
            fetch_okx_candles("ORDI/USDT", transport=transport)

    def test_rate_limit_http_error_raises_clear_error(self):
        def transport(url, timeout):
            raise urllib.error.HTTPError(
                url,
                429,
                "Too Many Requests",
                {},
                io.BytesIO(b'{"code":"50011","msg":"Too many requests"}'),
            )

        with self.assertRaisesRegex(ExchangeRateLimitError, "rate limit"):
            fetch_okx_candles("ORDI/USDT", transport=transport)

    def test_load_candles_live_okx_routes_to_adapter(self):
        with patch("yongying.market_data.fetch_okx_candles") as fetcher:
            fetcher.return_value = [Candle(1700000000000, 3.38, 3.42, 3.33, 3.4, 1.0)]
            candles = load_candles(
                symbol="ORDI/USDT",
                timeframe="15m",
                source="live",
                exchange="okx",
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


if __name__ == "__main__":
    unittest.main()
