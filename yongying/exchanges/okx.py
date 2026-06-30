from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ..models import Candle
from .binance import (
    EmptyKlineResponseError,
    ExchangeRateLimitError,
    ExchangeRequestError,
    InvalidLimitError,
    InvalidSymbolError,
    UnsupportedMarketError,
    UnsupportedTimeframeError,
)


OKX_CANDLES_URL = "https://www.okx.com/api/v5/market/candles"
SUPPORTED_TIMEFRAMES = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "1w": "1W",
    "1M": "1M",
}

JsonTransport = Callable[[str, float], Any]


def _split_project_symbol(symbol: str) -> tuple[str, str]:
    raw = symbol.strip().upper()
    if not raw:
        raise InvalidSymbolError("Symbol cannot be empty")
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    raw = raw.replace("_", "-")

    if "/" in raw:
        parts = raw.split("/")
    else:
        parts = raw.split("-")

    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise InvalidSymbolError(f"Invalid project symbol format: {symbol}")
    return parts[0], parts[1]


def to_okx_inst_id(symbol: str, market: str = "futures") -> str:
    raw = symbol.strip().upper().replace("_", "-")
    if raw.count("-") >= 2 and raw.endswith("-SWAP"):
        return raw

    base, quote = _split_project_symbol(symbol)
    market_name = market.strip().lower()
    if market_name in {"futures", "future", "swap", "perpetual", "perp"}:
        return f"{base}-{quote}-SWAP"
    if market_name == "spot":
        return f"{base}-{quote}"
    raise UnsupportedMarketError("Only OKX spot and USDT swap klines are implemented")


def validate_timeframe(timeframe: str) -> str:
    interval = timeframe.strip()
    if interval not in SUPPORTED_TIMEFRAMES:
        supported = ", ".join(sorted(SUPPORTED_TIMEFRAMES))
        raise UnsupportedTimeframeError(f"Unsupported OKX timeframe '{timeframe}'. Supported: {supported}")
    return SUPPORTED_TIMEFRAMES[interval]


def validate_limit(limit: int) -> int:
    if limit < 1 or limit > 300:
        raise InvalidLimitError("OKX kline limit must be between 1 and 300")
    return limit


def build_candles_url(
    symbol: str,
    timeframe: str,
    limit: int,
    market: str = "futures",
    start_time: int | None = None,
    end_time: int | None = None,
) -> str:
    values: dict[str, int | str] = {
        "instId": to_okx_inst_id(symbol, market=market),
        "bar": validate_timeframe(timeframe),
        "limit": validate_limit(limit),
    }
    if start_time is not None:
        values["before"] = int(start_time) - 1
    if end_time is not None:
        values["after"] = int(end_time) + 1
    params = urllib.parse.urlencode(values)
    return f"{OKX_CANDLES_URL}?{params}"


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
        raise ExchangeRequestError("OKX kline response must be an object")
    code = str(payload.get("code"))
    if code == "0":
        return
    message = payload.get("msg") or payload.get("message") or "Exchange returned an error"
    if code in {"50011"}:
        raise ExchangeRateLimitError(f"OKX rate limit: {message}")
    if code in {"51000", "51001"}:
        raise InvalidSymbolError(f"OKX rejected symbol or parameters: {message}")
    raise ExchangeRequestError(f"OKX error {code}: {message}")


def _request_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "Yongying/0.1 market-data"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def okx_candles_to_ohlcv(payload: Any) -> list[list[float]]:
    _raise_for_exchange_error(payload)
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise ExchangeRequestError("OKX kline data must be a list")
    if not rows:
        raise EmptyKlineResponseError("OKX returned no klines")

    ohlcv: list[list[float]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ExchangeRequestError(f"Malformed OKX kline row at index {index}")
        try:
            volume = row[6] if len(row) > 6 and row[6] not in {None, ""} else row[5]
            ohlcv.append(
                [
                    int(row[0]),
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(volume),
                ]
            )
        except (TypeError, ValueError) as exc:
            raise ExchangeRequestError(f"Non-numeric OKX kline row at index {index}") from exc

    return sorted(ohlcv, key=lambda item: item[0])


def okx_candles_to_candles(payload: Any) -> list[Candle]:
    return [Candle.from_ohlcv(row) for row in okx_candles_to_ohlcv(payload)]


def fetch_okx_candles(
    symbol: str,
    timeframe: str = "15m",
    limit: int = 200,
    market: str = "futures",
    timeout: float = 10.0,
    start_time: int | None = None,
    end_time: int | None = None,
    transport: JsonTransport | None = None,
) -> list[Candle]:
    url = build_candles_url(
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
            raise ExchangeRateLimitError(f"OKX rate limit HTTP {exc.code}: {message}") from exc
        raise ExchangeRequestError(f"OKX HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise ExchangeRequestError(f"OKX network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ExchangeRequestError("OKX returned invalid JSON") from exc
    except TimeoutError as exc:
        raise ExchangeRequestError("OKX request timed out") from exc
    except OSError as exc:
        raise ExchangeRequestError(f"OKX network error: {exc}") from exc

    return okx_candles_to_candles(payload)
