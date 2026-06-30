from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import AnalysisResult, SignalPlan


@dataclass(frozen=True)
class SignalLogEntry:
    id: int
    created_at: int
    exchange: str
    market: str
    source: str
    symbol: str
    timeframe: str
    closed_timestamp: int | None
    primary_direction: str
    aggressive_direction: str | None
    conservative_direction: str | None
    display_direction: str
    last_price: float
    aggregate_score: float
    entry_low: float | None
    entry_high: float | None
    take_profits: list[float]
    stop_loss: float | None
    reason: str
    signal_text: str
    analysis: dict[str, Any]


def _normalize_key(value: str) -> str:
    return value.strip().upper()


def _plan_direction(plan: SignalPlan | None) -> str | None:
    return plan.direction if plan is not None else None


def _display_plan(result: AnalysisResult) -> SignalPlan:
    if result.aggressive_plan and result.aggressive_plan.direction != "WAIT":
        return result.aggressive_plan
    if result.conservative_plan and result.conservative_plan.direction != "WAIT":
        return result.conservative_plan
    if result.aggressive_plan:
        return result.aggressive_plan
    return result.plan


def _entry_bounds(plan: SignalPlan) -> tuple[float | None, float | None]:
    if plan.entry_range is None:
        return None, None
    return float(plan.entry_range[0]), float(plan.entry_range[1])


class SignalLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.parent:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at INTEGER NOT NULL,
                    exchange TEXT NOT NULL,
                    market TEXT NOT NULL,
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    closed_timestamp INTEGER,
                    primary_direction TEXT NOT NULL,
                    aggressive_direction TEXT,
                    conservative_direction TEXT,
                    display_direction TEXT NOT NULL,
                    last_price REAL NOT NULL,
                    aggregate_score REAL NOT NULL,
                    entry_low REAL,
                    entry_high REAL,
                    take_profits_json TEXT NOT NULL,
                    stop_loss REAL,
                    reason TEXT NOT NULL,
                    signal_text TEXT NOT NULL,
                    analysis_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signals_lookup
                ON signals (exchange, market, symbol, timeframe, closed_timestamp)
                """
            )

    def save_analysis(
        self,
        result: AnalysisResult,
        signal_text: str,
        exchange: str,
        market: str,
        closed_timestamp: int | None,
        reason: str,
        created_at: int | None = None,
    ) -> int:
        display_plan = _display_plan(result)
        entry_low, entry_high = _entry_bounds(display_plan)
        analysis = result.to_dict()
        row = (
            int(time.time() * 1000) if created_at is None else int(created_at),
            _normalize_key(exchange),
            _normalize_key(market),
            result.source,
            result.symbol,
            result.timeframe,
            closed_timestamp,
            result.plan.direction,
            _plan_direction(result.aggressive_plan),
            _plan_direction(result.conservative_plan),
            display_plan.direction,
            result.last_price,
            result.aggregate_score,
            entry_low,
            entry_high,
            json.dumps(display_plan.take_profits, ensure_ascii=False),
            display_plan.stop_loss,
            reason,
            signal_text,
            json.dumps(analysis, ensure_ascii=False),
        )
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO signals (
                    created_at, exchange, market, source, symbol, timeframe,
                    closed_timestamp, primary_direction, aggressive_direction,
                    conservative_direction, display_direction, last_price,
                    aggregate_score, entry_low, entry_high, take_profits_json,
                    stop_loss, reason, signal_text, analysis_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            return int(cursor.lastrowid)

    def latest(
        self,
        exchange: str | None = None,
        market: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int = 20,
    ) -> list[SignalLogEntry]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        where: list[str] = []
        params: list[object] = []
        if exchange is not None:
            where.append("exchange = ?")
            params.append(_normalize_key(exchange))
        if market is not None:
            where.append("market = ?")
            params.append(_normalize_key(market))
        if symbol is not None:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe is not None:
            where.append("timeframe = ?")
            params.append(timeframe)
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM signals
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_entry(row) for row in rows]


def _row_to_entry(row: sqlite3.Row) -> SignalLogEntry:
    return SignalLogEntry(
        id=int(row["id"]),
        created_at=int(row["created_at"]),
        exchange=str(row["exchange"]),
        market=str(row["market"]),
        source=str(row["source"]),
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"]),
        closed_timestamp=row["closed_timestamp"],
        primary_direction=str(row["primary_direction"]),
        aggressive_direction=row["aggressive_direction"],
        conservative_direction=row["conservative_direction"],
        display_direction=str(row["display_direction"]),
        last_price=float(row["last_price"]),
        aggregate_score=float(row["aggregate_score"]),
        entry_low=row["entry_low"],
        entry_high=row["entry_high"],
        take_profits=[float(item) for item in json.loads(row["take_profits_json"])],
        stop_loss=row["stop_loss"],
        reason=str(row["reason"]),
        signal_text=str(row["signal_text"]),
        analysis=json.loads(row["analysis_json"]),
    )
