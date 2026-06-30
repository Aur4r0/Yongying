from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .kline_cache import CacheUpdateResult, KlineCache, update_cached_candles
from .live_feed import LiveFeedState, poll_closed_candles
from .market_data import fetch_live_candles, load_candles
from .models import AnalysisResult, Candle
from .notifier import NotifyResult, send_notification
from .signal_engine import analyze_candles
from .templates.signal_cn import render_signal_cn


Loader = Callable[..., list[Candle]]
Fetcher = Callable[..., list[Candle]]
Analyzer = Callable[[list[Candle], str, str, str], AnalysisResult]
Renderer = Callable[[AnalysisResult], str]
Notifier = Callable[[str], NotifyResult]


@dataclass
class ScannerState:
    feed: LiveFeedState = field(default_factory=LiveFeedState)
    emitted_signal_keys: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    timeframe: str
    analyzed: bool
    emitted: bool
    reason: str
    closed_timestamp: int | None = None
    text: str | None = None
    analysis: AnalysisResult | None = None
    notify_result: NotifyResult | None = None
    cache_update: CacheUpdateResult | None = None


def _active_signal(result: AnalysisResult) -> bool:
    aggressive = result.aggressive_plan or result.plan
    return aggressive.direction != "WAIT" or result.plan.direction != "WAIT"


def _signal_key(result: AnalysisResult) -> str:
    aggressive = result.aggressive_plan or result.plan
    return "|".join(
        [
            result.symbol,
            result.timeframe,
            aggressive.direction,
            str(aggressive.entry_range),
            str(aggressive.take_profits),
            str(aggressive.stop_loss),
        ]
    )


def scan_once(
    state: ScannerState,
    symbol: str = "ORDI/USDT",
    timeframe: str = "15m",
    source: str = "demo",
    exchange: str | None = None,
    market: str = "futures",
    limit: int = 180,
    emit_wait: bool = False,
    loader: Loader = load_candles,
    cache_path: str | Path | None = None,
    cache_fetcher: Fetcher = fetch_live_candles,
    analyzer: Analyzer = analyze_candles,
    renderer: Renderer = render_signal_cn,
    notifier: Notifier | None = None,
) -> ScanResult:
    cache_update = None
    effective_loader = loader
    if cache_path is not None and source == "live":
        effective_exchange = exchange or "binance"
        cache_update = update_cached_candles(
            cache_path=cache_path,
            exchange=effective_exchange,
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            fetcher=cache_fetcher,
            refresh_latest=True,
        )
        cache = KlineCache(cache_path)

        def load_from_cache(**kwargs) -> list[Candle]:
            return cache.load_candles(
                exchange=effective_exchange,
                market=market,
                symbol=kwargs.get("symbol", symbol),
                timeframe=kwargs.get("timeframe", timeframe),
                limit=kwargs.get("limit", limit),
            )

        effective_loader = load_from_cache

    feed_result = poll_closed_candles(
        state.feed,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        exchange=exchange,
        limit=limit,
        loader=effective_loader,
    )
    closed = feed_result.closed_candles
    if len(closed) < 60:
        return ScanResult(
            symbol=symbol,
            timeframe=timeframe,
            analyzed=False,
            emitted=False,
            reason="insufficient_closed_candles",
            cache_update=cache_update,
        )

    closed_timestamp = feed_result.closed_timestamp
    if not feed_result.is_new_closed_candle:
        return ScanResult(
            symbol=symbol,
            timeframe=timeframe,
            analyzed=False,
            emitted=False,
            reason=feed_result.reason,
            closed_timestamp=closed_timestamp,
            cache_update=cache_update,
        )

    analysis = analyzer(closed, symbol, timeframe, source)
    active = _active_signal(analysis)
    if not active and not emit_wait:
        return ScanResult(
            symbol=symbol,
            timeframe=timeframe,
            analyzed=True,
            emitted=False,
            reason="no_active_signal",
            closed_timestamp=closed_timestamp,
            analysis=analysis,
            cache_update=cache_update,
        )

    signal_key = _signal_key(analysis)
    if signal_key in state.emitted_signal_keys:
        return ScanResult(
            symbol=symbol,
            timeframe=timeframe,
            analyzed=True,
            emitted=False,
            reason="duplicate_signal",
            closed_timestamp=closed_timestamp,
            analysis=analysis,
            cache_update=cache_update,
        )

    state.emitted_signal_keys.add(signal_key)
    text = renderer(analysis)
    notify_result = notifier(text) if notifier else None
    return ScanResult(
        symbol=symbol,
        timeframe=timeframe,
        analyzed=True,
        emitted=True,
        reason="emitted",
        closed_timestamp=closed_timestamp,
        text=text,
        analysis=analysis,
        notify_result=notify_result,
        cache_update=cache_update,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yongying research signal scanner")
    parser.add_argument("--symbol", default="ORDI/USDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--source", choices=["demo", "live"], default="demo")
    parser.add_argument("--exchange", default=None)
    parser.add_argument("--market", default="futures")
    parser.add_argument("--limit", type=int, default=180)
    parser.add_argument("--cache-path", default=None, help="SQLite kline cache path for live scanner runs")
    parser.add_argument("--interval", type=float, default=900.0)
    parser.add_argument("--iterations", type=int, default=1, help="Use 0 for an endless loop")
    parser.add_argument("--emit-wait", action="store_true")
    parser.add_argument("--notify", choices=["none", "telegram"], default="none")
    parser.add_argument("--notify-dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    state = ScannerState()
    iteration = 0
    notifier = None
    if args.notify != "none":
        notifier = lambda text: send_notification(args.notify, text, dry_run=args.notify_dry_run)

    while True:
        result = scan_once(
            state,
            symbol=args.symbol,
            timeframe=args.timeframe,
            source=args.source,
            exchange=args.exchange,
            market=args.market,
            limit=args.limit,
            cache_path=args.cache_path,
            emit_wait=args.emit_wait,
            notifier=notifier,
        )
        if result.emitted and result.text:
            print(result.text)
            if result.notify_result:
                print(f"[notify:{result.notify_result.provider}] {result.notify_result.reason}")
        else:
            print(f"[{args.symbol} {args.timeframe}] {result.reason}")

        iteration += 1
        if args.iterations and iteration >= args.iterations:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
