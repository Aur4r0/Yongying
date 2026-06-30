from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .models import Candle


Fetcher = Callable[..., list[Candle]]


@dataclass(frozen=True)
class CandleGap:
    previous_timestamp: int
    next_timestamp: int
    missing_count: int


@dataclass(frozen=True)
class ContinuityReport:
    timeframe: str
    expected_interval_ms: int
    candle_count: int
    is_continuous: bool
    gaps: list[CandleGap] = field(default_factory=list)


@dataclass(frozen=True)
class CacheUpdateResult:
    exchange: str
    market: str
    symbol: str
    timeframe: str
    fetched_count: int
    stored_count: int
    cached_count: int
    latest_before: int | None
    latest_after: int | None
    continuity: ContinuityReport


def timeframe_to_milliseconds(timeframe: str) -> int:
    units = {
        "m": 60_000,
        "h": 60 * 60_000,
        "d": 24 * 60 * 60_000,
        "w": 7 * 24 * 60 * 60_000,
    }
    if len(timeframe) < 2:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    value_text = timeframe[:-1]
    unit = timeframe[-1]
    if unit not in units or not value_text.isdigit():
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    value = int(value_text)
    if value <= 0:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return value * units[unit]


def _normalize_key(value: str) -> str:
    return value.strip().upper()


def _dedupe_candles(candles: list[Candle]) -> list[Candle]:
    by_timestamp = {candle.timestamp: candle for candle in candles}
    return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]


def check_candle_continuity(candles: list[Candle], timeframe: str) -> ContinuityReport:
    interval_ms = timeframe_to_milliseconds(timeframe)
    ordered = _dedupe_candles(candles)
    gaps: list[CandleGap] = []
    for previous, current in zip(ordered, ordered[1:]):
        delta = current.timestamp - previous.timestamp
        if delta != interval_ms:
            missing_count = max((delta // interval_ms) - 1, 0) if delta > interval_ms else 0
            gaps.append(
                CandleGap(
                    previous_timestamp=previous.timestamp,
                    next_timestamp=current.timestamp,
                    missing_count=missing_count,
                )
            )
    return ContinuityReport(
        timeframe=timeframe,
        expected_interval_ms=interval_ms,
        candle_count=len(ordered),
        is_continuous=not gaps,
        gaps=gaps,
    )


class KlineCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.parent:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    exchange TEXT NOT NULL,
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (exchange, market, symbol, timeframe, timestamp)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_candles_lookup
                ON candles (exchange, market, symbol, timeframe, timestamp)
                """
            )

    def save_candles(
        self,
        exchange: str,
        market: str,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
    ) -> int:
        rows = [
            (
                _normalize_key(exchange),
                _normalize_key(market),
                _normalize_key(symbol),
                timeframe,
                candle.timestamp,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            )
            for candle in _dedupe_candles(candles)
        ]
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO candles (
                    exchange, market, symbol, timeframe, timestamp,
                    open, high, low, close, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def load_candles(
        self,
        exchange: str,
        market: str,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
    ) -> list[Candle]:
        where = [
            "exchange = ?",
            "market = ?",
            "symbol = ?",
            "timeframe = ?",
        ]
        params: list[object] = [
            _normalize_key(exchange),
            _normalize_key(market),
            _normalize_key(symbol),
            timeframe,
        ]
        if start_timestamp is not None:
            where.append("timestamp >= ?")
            params.append(start_timestamp)
        if end_timestamp is not None:
            where.append("timestamp <= ?")
            params.append(end_timestamp)

        limit_clause = ""
        if limit is not None:
            if limit <= 0:
                raise ValueError("limit must be positive")
            limit_clause = " LIMIT ?"
            params.append(limit)

        query = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE {' AND '.join(where)}
            ORDER BY timestamp DESC
            {limit_clause}
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        candles = [Candle.from_ohlcv(row) for row in rows]
        return list(reversed(candles))

    def latest_timestamp(
        self,
        exchange: str,
        market: str,
        symbol: str,
        timeframe: str,
    ) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(timestamp)
                FROM candles
                WHERE exchange = ? AND market = ? AND symbol = ? AND timeframe = ?
                """,
                (_normalize_key(exchange), _normalize_key(market), _normalize_key(symbol), timeframe),
            ).fetchone()
        value = row[0] if row else None
        return int(value) if value is not None else None


def update_cached_candles(
    cache_path: str | Path,
    exchange: str,
    market: str,
    symbol: str,
    timeframe: str,
    limit: int = 200,
    fetcher: Fetcher | None = None,
) -> CacheUpdateResult:
    cache = KlineCache(cache_path)
    latest_before = cache.latest_timestamp(exchange, market, symbol, timeframe)
    start_time = None
    if latest_before is not None:
        start_time = latest_before + timeframe_to_milliseconds(timeframe)

    if fetcher is None:
        from .market_data import fetch_live_candles

        fetcher = fetch_live_candles

    fetched = fetcher(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        exchange_id=exchange,
        market=market,
        start_time=start_time,
    )
    stored_count = cache.save_candles(exchange, market, symbol, timeframe, fetched)
    cached = cache.load_candles(exchange, market, symbol, timeframe)
    latest_after = cache.latest_timestamp(exchange, market, symbol, timeframe)
    continuity = check_candle_continuity(cached, timeframe)
    return CacheUpdateResult(
        exchange=exchange,
        market=market,
        symbol=symbol,
        timeframe=timeframe,
        fetched_count=len(fetched),
        stored_count=stored_count,
        cached_count=len(cached),
        latest_before=latest_before,
        latest_after=latest_after,
        continuity=continuity,
    )
