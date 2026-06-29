from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__
from .market_data import load_candles
from .signal_engine import analyze_candles


def _first(params: dict[str, list[str]], key: str, default: str) -> str:
    values = params.get(key)
    if not values:
        return default
    return values[0]


def _json_bytes(payload: dict, status: int = 200) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2 if status >= 400 else None).encode("utf-8")


class YongyingHandler(BaseHTTPRequestHandler):
    server_version = f"YongyingHTTP/{__version__}"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/health":
            self._send_json({"ok": True, "version": __version__})
            return

        if parsed.path == "/analyze":
            try:
                symbol = _first(params, "symbol", "ORDI/USDT")
                timeframe = _first(params, "timeframe", "15m")
                source = _first(params, "source", "demo")
                exchange = params.get("exchange", [None])[0]
                limit = int(_first(params, "limit", "180"))
                if source not in {"demo", "live"}:
                    raise ValueError("source must be 'demo' or 'live'")
                candles = load_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    source=source,  # type: ignore[arg-type]
                    limit=limit,
                    exchange=exchange,
                )
                result = analyze_candles(candles, symbol=symbol, timeframe=timeframe, source=source)
                self._send_json(result.to_dict())
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = _json_bytes(payload, int(status))
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dependency-free Yongying HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), YongyingHandler)
    print(f"Yongying HTTP API listening on http://{args.host}:{args.port}")
    print(f"Try: http://{args.host}:{args.port}/analyze?symbol=ORDI/USDT&timeframe=15m&source=demo")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
