from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Direction = Literal["LONG", "SHORT", "WAIT"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_ohlcv(cls, row: list[float] | tuple[float, ...]) -> "Candle":
        return cls(
            timestamp=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )


@dataclass
class IndicatorSnapshot:
    close: float
    ma7: float | None
    ma25: float | None
    boll_mid: float | None
    boll_upper: float | None
    boll_lower: float | None
    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None
    atr14: float | None
    volume: float
    volume_ma20: float | None


@dataclass
class RuleResult:
    name: str
    score: float
    confidence: Confidence
    state: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalPlan:
    direction: Direction
    risk_level: Literal["low", "medium", "high"]
    entry_range: tuple[float, float] | None
    take_profits: list[float]
    stop_loss: float | None
    invalidation: list[str]
    confirmation: list[str]
    position_note: str


@dataclass
class AnalysisResult:
    symbol: str
    timeframe: str
    source: str
    last_price: float
    aggregate_score: float
    plan: SignalPlan
    indicators: IndicatorSnapshot
    rules: list[RuleResult]
    memo_cn: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

