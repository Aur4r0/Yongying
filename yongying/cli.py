from __future__ import annotations

import argparse
import json

from .market_data import load_candles
from .signal_engine import analyze_candles
from .templates.signal_cn import render_signal_cn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yongying MVP signal analyzer")
    parser.add_argument("--symbol", default="ORDI/USDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--source", choices=["demo", "live"], default="demo")
    parser.add_argument("--exchange", default=None)
    parser.add_argument("--limit", type=int, default=180)
    parser.add_argument("--json", action="store_true", help="Print full JSON instead of Chinese memo")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    candles = load_candles(
        symbol=args.symbol,
        timeframe=args.timeframe,
        source=args.source,
        limit=args.limit,
        exchange=args.exchange,
    )
    result = analyze_candles(candles, symbol=args.symbol, timeframe=args.timeframe, source=args.source)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_signal_cn(result))


if __name__ == "__main__":
    main()
