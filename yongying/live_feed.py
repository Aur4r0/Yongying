from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

from .market_data import load_candles
from .models import Candle


Loader = Callable[..., list[Candle]]
Sleeper = Callable[[float], None]


@dataclass
class LiveFeedState:
    last_closed_timestamp: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class FeedPollResult:
    symbol: str
    timeframe: str
    source: str
    loaded_count: int
    closed_count: int
    closed_timestamp: int | None
    closed_candles: list[Candle]
    is_new_closed_candle: bool
    reason: str


def stream_key(symbol: str, timeframe: str) -> str:
    return f"{symbol}:{timeframe}"


def closed_candles(candles: list[Candle]) -> list[Candle]:
    if len(candles) <= 1:
        return candles
    return candles[:-1]


def poll_closed_candles(
    state: LiveFeedState,
    symbol: str = "ORDI/USDT",
    timeframe: str = "15m",
    source: str = "demo",
    exchange: str | None = None,
    limit: int = 180,
    loader: Loader = load_candles,
) -> FeedPollResult:
    candles = loader(symbol=symbol, timeframe=timeframe, source=source, limit=limit, exchange=exchange)
    closed = closed_candles(candles)
    if not closed:
        return FeedPollResult(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            loaded_count=len(candles),
            closed_count=0,
            closed_timestamp=None,
            closed_candles=[],
            is_new_closed_candle=False,
            reason="no_closed_candles",
        )

    key = stream_key(symbol, timeframe)
    closed_timestamp = closed[-1].timestamp
    if state.last_closed_timestamp.get(key) == closed_timestamp:
        return FeedPollResult(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            loaded_count=len(candles),
            closed_count=len(closed),
            closed_timestamp=closed_timestamp,
            closed_candles=closed,
            is_new_closed_candle=False,
            reason="no_new_closed_candle",
        )

    state.last_closed_timestamp[key] = closed_timestamp
    return FeedPollResult(
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        loaded_count=len(candles),
        closed_count=len(closed),
        closed_timestamp=closed_timestamp,
        closed_candles=closed,
        is_new_closed_candle=True,
        reason="new_closed_candle",
    )


def iter_closed_candle_polls(
    state: LiveFeedState,
    symbol: str = "ORDI/USDT",
    timeframe: str = "15m",
    source: str = "demo",
    exchange: str | None = None,
    limit: int = 180,
    interval: float = 900.0,
    iterations: int = 0,
    loader: Loader = load_candles,
    sleep: Sleeper = time.sleep,
) -> Iterator[FeedPollResult]:
    count = 0
    while True:
        yield poll_closed_candles(
            state,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            exchange=exchange,
            limit=limit,
            loader=loader,
        )
        count += 1
        if iterations and count >= iterations:
            break
        sleep(interval)
