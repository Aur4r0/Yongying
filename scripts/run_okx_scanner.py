from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Callable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from yongying.notifier import send_notification
from yongying.scanner import ScanResult, ScannerState, scan_once


Sleeper = Callable[[float], None]
ScanOnce = Callable[..., ScanResult]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Yongying live scanner with OKX klines and SQLite cache")
    parser.add_argument("--symbol", default="ORDI/USDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--limit", type=int, default=180)
    parser.add_argument("--cache-path", default="data/okx-klines.sqlite")
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--iterations", type=int, default=0, help="Use 0 for an endless loop")
    parser.add_argument("--market", default="futures")
    parser.add_argument("--emit-wait", dest="emit_wait", action="store_true", default=True)
    parser.add_argument("--no-emit-wait", dest="emit_wait", action="store_false")
    parser.add_argument("--notify", choices=["none", "telegram"], default="none")
    parser.add_argument("--notify-dry-run", action="store_true")
    return parser


def _ensure_cache_parent(cache_path: str) -> None:
    parent = Path(cache_path).expanduser().parent
    if str(parent) and str(parent) != ".":
        parent.mkdir(parents=True, exist_ok=True)


def _cache_summary(result: ScanResult) -> str:
    if result.cache_update is None:
        return ""
    update = result.cache_update
    return f" cache=fetched:{update.fetched_count} stored:{update.stored_count} cached:{update.cached_count}"


def run(argv: Sequence[str] | None = None, scan_once_fn: ScanOnce = scan_once, sleep: Sleeper = time.sleep) -> int:
    args = build_parser().parse_args(argv)
    _ensure_cache_parent(args.cache_path)

    state = ScannerState()
    notifier = None
    if args.notify != "none":
        notifier = lambda text: send_notification(args.notify, text, dry_run=args.notify_dry_run)

    print(
        "[okx-scanner] "
        f"symbol={args.symbol} timeframe={args.timeframe} cache={args.cache_path} "
        f"interval={args.interval}s iterations={args.iterations or 'endless'}"
    )

    iteration = 0
    while True:
        result = scan_once_fn(
            state,
            symbol=args.symbol,
            timeframe=args.timeframe,
            source="live",
            exchange="okx",
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
            print(f"[{args.symbol} {args.timeframe}] {result.reason}{_cache_summary(result)}")

        iteration += 1
        if args.iterations and iteration >= args.iterations:
            break
        sleep(args.interval)

    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
