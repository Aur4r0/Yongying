from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from . import __version__
from .market_data import load_candles
from .signal_engine import analyze_candles


app = FastAPI(
    title="Yongying Signal MVP",
    version=__version__,
    description="Research-only strategy signal API based on Yongying strategy notes.",
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/analyze")
def analyze(
    symbol: str = Query(default="ORDI/USDT"),
    timeframe: str = Query(default="15m"),
    source: str = Query(default="demo", pattern="^(demo|live)$"),
    exchange: str | None = Query(default=None),
    limit: int = Query(default=180, ge=60, le=1000),
) -> dict:
    try:
        candles = load_candles(
            symbol=symbol,
            timeframe=timeframe,
            source=source,  # type: ignore[arg-type]
            limit=limit,
            exchange=exchange,
        )
        result = analyze_candles(candles, symbol=symbol, timeframe=timeframe, source=source)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

