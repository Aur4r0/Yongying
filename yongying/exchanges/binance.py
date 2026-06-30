from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ..models import Candle


BINANCE_FUTURES_KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
SUPPORTED_TIMEFRAMES = {
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
}

JsonTransport = Callable[[str, float], Any]


class MarketDataError(RuntimeError):
    """Base exception for market-data fetching failures."""


class InvalidSymbolError(MarketDataError):
    """Raised when a symbol cannot be normalized or is rejected by the exchange."""


class UnsupportedTimeframeError(MarketDataError):
    """Raised when an interval is not supported by the adapter."""


class UnsupportedMarketError(MarketDataError):
    """Raised when the requested market type is not implemented."""


class InvalidLimitError(MarketDataError):
    """Raised when the requested candle limit is outside exchange bounds."""


class EmptyKlineResponseError(MarketDataError):
    """Raised when the exchange returns no klines."""


class ExchangeRateLimitError(MarketDataError):
    """Raised when the exchange rate-limits the request."""


class ExchangeRequestError(MarketDataError):
    """Raised for network, HTTP, or malformed response failures."""


def to_binance_symbol(symbol: str) -> str:
    raw = symbol.strip().upper()
    if not raw:
        raise InvalidSymbolError("Symbol cannot be empty")

    if ":" in raw:
        raw = raw.split(":", 1)[0]

    if "/" in raw:
        parts = raw.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise InvalidSymbolError(f"Invalid project symbol format: {symbol}")
        raw = "".join(parts)

    normalized = raw.replace("-", "").replace("_", "")
    if not normalized.isalnum() or len(normalized) < 6:
        raise InvalidSymbolError(f"Invalid Binance symbol: {symbol}")
    return normalized


def validate_timeframe(timeframe: str) -> str:
    interval = timeframe.strip()
    if interval not in SUPPORTED_TIMEFRAMES:
        supported = ", ".join(sorted(SUPPORTED_TIMEFRAMES))
        raise UnsupportedTimeframeError(f"Unsupported Binance timeframe '{timeframe}'. Supported: {supported}")
    return interval


def validate_limit(limit: int) -> int:
    if limit < 1 or limit > 1500:
        raise InvalidLimitError("Binance kline limit must be between 1 and 1500")
    return limit


def build_klines_url(
    symbol: str,
    timeframe: str,
    limit: int,
    market: str = "futures",
    start_time: int | None = None,
    end_time: int | None = None,
) -> str:
    if market != "futures":
        raise UnsupportedMarketError("Only Binance U-margined futures klines are implemented")
    values: dict[str, int | str] = {
        "symbol": to_binance_symbol(symbol),
        "interval": validate_timeframe(timeframe),
        "limit": validate_limit(limit),
    }
    if start_time is not None:
        values["startTime"] = int(start_time)
    if end_time is not None:
        values["endTime"] = int(end_time)
    params = urllib.parse.urlencode(values)
    return f"{BINANCE_FUTURES_KLINES_URL}?{params}"


def _extract_error_message(payload: str) -> str:
    if not payload:
        return ""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload[:200]
    if isinstance(parsed, dict):
        code = parsed.get("code")
        message = parsed.get("msg") or parsed.get("message") or ""
        if code is not None:
            return f"{code}: {message}".strip()
        return str(message)
    return payload[:200]


def _raise_for_exchange_error(payload: Any) -> None:
    if not isinstance(payload, dict) or "code" not in payload:
        return
    code = payload.get("code")
    message = payload.get("msg") or payload.get("message") or "Exchange returned an error"
    if code == -1121:
        raise InvalidSymbolError(f"Binance rejected symbol: {message}")
    if code in {-1003, -1015}:
        raise ExchangeRateLimitError(f"Binance rate limit: {message}")
    raise ExchangeRequestError(f"Binance error {code}: {message}")


def _request_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "Yongying/0.1 market-data"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def binance_klines_to_ohlcv(rows: Any) -> list[list[float]]:
    _raise_for_exchange_error(rows)
    if not isinstance(rows, list):
        raise ExchangeRequestError("Binance kline response must be a list")
    if not rows:
        raise EmptyKlineResponseError("Binance returned no klines")

    ohlcv: list[list[float]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ExchangeRequestError(f"Malformed Binance kline row at index {index}")
        try:
            ohlcv.append(
                [
                    int(row[0]),
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(row[5]),
                ]
            )
        except (TypeError, ValueError) as exc:
            raise ExchangeRequestError(f"Non-numeric Binance kline row at index {index}") from exc
    return ohlcv


def binance_klines_to_candles(rows: Any) -> list[Candle]:
    return [Candle.from_ohlcv(row) for row in binance_klines_to_ohlcv(rows)]


def fetch_binance_klines(
    symbol: str,
    timeframe: str = "15m",
    limit: int = 200,
    market: str = "futures",
    timeout: float = 10.0,
    start_time: int | None = None,
    end_time: int | None = None,
    transport: JsonTransport | None = None,
) -> list[Candle]:
    url = build_klines_url(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        market=market,
        start_time=start_time,
        end_time=end_time,
    )
    request = transport or _request_json
    try:
        payload = request(url, timeout)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        finally:
            exc.close()
        message = _extract_error_message(body)
        if exc.code in {418, 429}:
            raise ExchangeRateLimitError(f"Binance rate limit HTTP {exc.code}: {message}") from exc
        if "-1121" in message:
            raise InvalidSymbolError(f"Binance rejected symbol: {message}") from exc
        raise ExchangeRequestError(f"Binance HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise ExchangeRequestError(f"Binance network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ExchangeRequestError("Binance returned invalid JSON") from exc
    except TimeoutError as exc:
        raise ExchangeRequestError("Binance request timed out") from exc
    except OSError as exc:
        raise ExchangeRequestError(f"Binance network error: {exc}") from exc

    return binance_klines_to_candles(payload)
