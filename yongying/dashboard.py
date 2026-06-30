from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .kline_cache import KlineCache
from .live_feed import closed_candles
from .models import Candle
from .signal_engine import analyze_candles
from .templates.signal_cn import render_signal_cn


@dataclass(frozen=True)
class DashboardConfig:
    cache_path: str
    exchange: str = "okx"
    market: str = "futures"
    symbol: str = "ORDI/USDT"
    timeframe: str = "15m"
    limit: int = 180


def _candle_dict(candle: Candle) -> dict[str, float | int]:
    return {
        "timestamp": candle.timestamp,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def build_dashboard_state(config: DashboardConfig) -> dict[str, Any]:
    cache = KlineCache(config.cache_path)
    candles = cache.load_candles(
        exchange=config.exchange,
        market=config.market,
        symbol=config.symbol,
        timeframe=config.timeframe,
        limit=config.limit,
    )
    closed = closed_candles(candles)
    payload: dict[str, Any] = {
        "ok": True,
        "version": __version__,
        "cache_path": str(config.cache_path),
        "exchange": config.exchange,
        "market": config.market,
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "limit": config.limit,
        "loaded_count": len(candles),
        "closed_count": len(closed),
        "latest_timestamp": candles[-1].timestamp if candles else None,
        "latest_closed_timestamp": closed[-1].timestamp if closed else None,
        "candles": [_candle_dict(candle) for candle in candles],
        "signal_text": None,
        "analysis": None,
        "reason": "insufficient_closed_candles",
    }
    if len(closed) >= 60:
        analysis = analyze_candles(closed, symbol=config.symbol, timeframe=config.timeframe, source="cache")
        payload["analysis"] = analysis.to_dict()
        payload["signal_text"] = render_signal_cn(analysis)
        payload["reason"] = "ok"
    elif not candles:
        payload["reason"] = "no_cached_candles"
    return payload


def _json_bytes(payload: dict[str, Any], status: int = 200) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2 if status >= 400 else None).encode("utf-8")


def render_dashboard_html(state: dict[str, Any]) -> str:
    candles = state["candles"][-80:]
    chart_data = json.dumps(candles, ensure_ascii=False)
    signal_text = state.get("signal_text") or f"等待更多缓存 K 线：{state.get('reason')}"
    analysis = state.get("analysis") or {}
    plan = analysis.get("aggressive_plan") or analysis.get("plan") or {}
    direction = plan.get("direction", "WAIT")
    last_price = analysis.get("last_price")
    last_price_text = f"{last_price:.4f}" if isinstance(last_price, (int, float)) else "等待缓存"
    status = "OK" if state.get("reason") == "ok" else "WAIT"

    rows = []
    for candle in candles[-24:]:
        rows.append(
            "<tr>"
            f"<td>{candle['timestamp']}</td>"
            f"<td>{candle['open']:.4f}</td>"
            f"<td>{candle['high']:.4f}</td>"
            f"<td>{candle['low']:.4f}</td>"
            f"<td>{candle['close']:.4f}</td>"
            f"<td>{candle['volume']:.2f}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Yongying Dashboard</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #fff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dde5;
      --green: #178a5a;
      --red: #c2413f;
      --blue: #2563eb;
      --amber: #a16207;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }}
    main {{ width: min(1180px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 36px; }}
    header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; margin-bottom: 16px; }}
    h1 {{ margin: 0; font-size: 28px; line-height: 1.2; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    p {{ margin: 4px 0 0; color: var(--muted); line-height: 1.6; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }}
    .metric, .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    .metric {{ padding: 14px; min-height: 98px; }}
    .metric small {{ color: var(--muted); text-transform: uppercase; font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 24px; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr); gap: 14px; }}
    .panel {{ padding: 16px; min-width: 0; }}
    canvas {{ width: 100%; height: 420px; display: block; border: 1px solid var(--line); border-radius: 8px; background: #fbfcfe; }}
    pre {{ margin: 0; padding: 12px; background: #f1f5f9; border: 1px solid var(--line); border-radius: 8px; white-space: pre-wrap; font: 13px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ color: var(--muted); background: #f8fafc; }}
    code {{ background: #eef2f7; border-radius: 5px; padding: 2px 5px; }}
    @media (max-width: 900px) {{ .grid, .layout {{ grid-template-columns: 1fr; }} header {{ align-items: flex-start; flex-direction: column; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Yongying 本地监控 Dashboard</h1>
        <p>读取 SQLite K 线缓存，不触发交易所请求，不下单。</p>
      </div>
      <p><code>{html.escape(str(state["cache_path"]))}</code></p>
    </header>
    <section class="grid">
      <div class="metric"><small>Status</small><strong>{html.escape(status)}</strong><p>{html.escape(str(state["reason"]))}</p></div>
      <div class="metric"><small>Pair</small><strong>{html.escape(str(state["symbol"]))}</strong><p>{html.escape(str(state["exchange"]))} / {html.escape(str(state["timeframe"]))}</p></div>
      <div class="metric"><small>Last Price</small><strong>{html.escape(last_price_text)}</strong><p>Direction: {html.escape(str(direction))}</p></div>
      <div class="metric"><small>Candles</small><strong>{state["closed_count"]}</strong><p>loaded: {state["loaded_count"]}</p></div>
    </section>
    <section class="layout">
      <article class="panel">
        <h2>K 线缓存</h2>
        <canvas id="chart"></canvas>
        <table>
          <thead><tr><th>timestamp</th><th>open</th><th>high</th><th>low</th><th>close</th><th>volume</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </article>
      <aside class="panel">
        <h2>当前信号</h2>
        <pre>{html.escape(str(signal_text))}</pre>
      </aside>
    </section>
  </main>
  <script>
    const candles = {chart_data};
    const canvas = document.getElementById("chart");
    const ctx = canvas.getContext("2d");
    function draw() {{
      const ratio = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.floor(rect.width * ratio);
      canvas.height = Math.floor(rect.height * ratio);
      ctx.scale(ratio, ratio);
      const w = rect.width;
      const h = rect.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#fbfcfe";
      ctx.fillRect(0, 0, w, h);
      if (!candles.length) {{
        ctx.fillStyle = "#667085";
        ctx.fillText("No cached candles yet", 24, 40);
        return;
      }}
      const pad = {{ left: 48, right: 36, top: 24, bottom: 46 }};
      const lows = candles.map(c => c.low);
      const highs = candles.map(c => c.high);
      const min = Math.min(...lows);
      const max = Math.max(...highs);
      const span = max - min || 1;
      const low = min - span * 0.1;
      const high = max + span * 0.1;
      const xStep = (w - pad.left - pad.right) / candles.length;
      const y = v => pad.top + (high - v) / (high - low) * (h - pad.top - pad.bottom);
      ctx.strokeStyle = "#d7dde5";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i += 1) {{
        const yy = pad.top + (h - pad.top - pad.bottom) * i / 4;
        ctx.beginPath();
        ctx.moveTo(pad.left, yy);
        ctx.lineTo(w - pad.right, yy);
        ctx.stroke();
      }}
      candles.forEach((c, i) => {{
        const x = pad.left + xStep * i + xStep / 2;
        const color = c.close >= c.open ? "#178a5a" : "#c2413f";
        const top = y(Math.max(c.open, c.close));
        const bottom = y(Math.min(c.open, c.close));
        const bodyW = Math.max(5, Math.min(18, xStep * 0.55));
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(x, y(c.high));
        ctx.lineTo(x, y(c.low));
        ctx.stroke();
        ctx.fillRect(x - bodyW / 2, top, bodyW, Math.max(3, bottom - top));
      }});
    }}
    draw();
    window.addEventListener("resize", draw);
  </script>
</body>
</html>"""


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], config: DashboardConfig):
        super().__init__(server_address, DashboardHandler)
        self.config = config


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = f"YongyingDashboard/{__version__}"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        config = self._config_from_params(params)

        if parsed.path == "/health":
            self._send_json({"ok": True, "version": __version__})
            return
        if parsed.path == "/api/state":
            try:
                self._send_json(build_dashboard_state(config))
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path in {"/", "/index.html"}:
            try:
                self._send_html(render_dashboard_html(build_dashboard_state(config)))
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _config_from_params(self, params: dict[str, list[str]]) -> DashboardConfig:
        base = self.server.config  # type: ignore[attr-defined]
        return DashboardConfig(
            cache_path=_first(params, "cache_path", base.cache_path),
            exchange=_first(params, "exchange", base.exchange),
            market=_first(params, "market", base.market),
            symbol=_first(params, "symbol", base.symbol),
            timeframe=_first(params, "timeframe", base.timeframe),
            limit=int(_first(params, "limit", str(base.limit))),
        )

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = _json_bytes(payload, int(status))
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, text: str, status: int = HTTPStatus.OK) -> None:
        body = text.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _first(params: dict[str, list[str]], key: str, default: str) -> str:
    values = params.get(key)
    if not values:
        return default
    return values[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yongying local dashboard for cached klines")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--cache-path", default="data/okx-klines.sqlite")
    parser.add_argument("--exchange", default="okx")
    parser.add_argument("--market", default="futures")
    parser.add_argument("--symbol", default="ORDI/USDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--limit", type=int, default=180)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    Path(args.cache_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    config = DashboardConfig(
        cache_path=args.cache_path,
        exchange=args.exchange,
        market=args.market,
        symbol=args.symbol,
        timeframe=args.timeframe,
        limit=args.limit,
    )
    server = DashboardServer((args.host, args.port), config)
    print(f"Yongying dashboard listening on http://{args.host}:{args.port}")
    print(f"Reading cache: {args.cache_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
