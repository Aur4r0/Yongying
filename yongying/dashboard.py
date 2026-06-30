from __future__ import annotations

import argparse
import html
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
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
    signal_log_path: str = "data/okx-signals.sqlite"
    exchange: str = "okx"
    market: str = "futures"
    symbol: str = "ORDI/USDT"
    timeframe: str = "15m"
    limit: int = 180
    signal_limit: int = 20


def _candle_dict(candle: Candle) -> dict[str, float | int]:
    return {
        "timestamp": candle.timestamp,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def _loads_json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _loads_json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_reasons(analysis: dict[str, Any], limit: int = 3) -> list[str]:
    reasons: list[str] = []
    rules = analysis.get("rules")
    if not isinstance(rules, list):
        return reasons
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_reasons = rule.get("reasons")
        if not isinstance(rule_reasons, list):
            continue
        for reason in rule_reasons:
            if isinstance(reason, str) and reason:
                reasons.append(reason)
                if len(reasons) >= limit:
                    return reasons
    return reasons


def _entry_range(low: float | None, high: float | None) -> dict[str, float] | None:
    if low is None and high is None:
        return None
    entry: dict[str, float] = {}
    if low is not None:
        entry["low"] = float(low)
    if high is not None:
        entry["high"] = float(high)
    return entry


def _signal_row_dict(row: sqlite3.Row) -> dict[str, Any]:
    analysis = _loads_json_dict(row["analysis_json"])
    take_profits = [float(item) for item in _loads_json_list(row["take_profits_json"]) if isinstance(item, (int, float))]
    return {
        "id": int(row["id"]),
        "created_at": int(row["created_at"]),
        "time": datetime.fromtimestamp(int(row["created_at"]) / 1000).strftime("%Y-%m-%d %H:%M:%S"),
        "exchange": str(row["exchange"]),
        "market": str(row["market"]),
        "symbol": str(row["symbol"]),
        "timeframe": str(row["timeframe"]),
        "closed_timestamp": row["closed_timestamp"],
        "direction": str(row["display_direction"]),
        "price": float(row["last_price"]),
        "entry": _entry_range(row["entry_low"], row["entry_high"]),
        "take_profits": take_profits,
        "stop_loss": row["stop_loss"],
        "reason": str(row["reason"]),
        "reasons": _extract_reasons(analysis),
    }


def load_signal_history(config: DashboardConfig) -> dict[str, Any]:
    path = Path(config.signal_log_path)
    if not path.exists():
        return {
            "status": "missing",
            "message": f"signal log not found: {path}",
            "path": str(path),
            "entries": [],
        }
    if config.signal_limit <= 0:
        return {
            "status": "error",
            "message": "signal_limit must be positive",
            "path": str(path),
            "entries": [],
        }
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    id, created_at, exchange, market, symbol, timeframe,
                    closed_timestamp, display_direction, last_price,
                    entry_low, entry_high, take_profits_json, stop_loss,
                    reason, analysis_json
                FROM signals
                WHERE exchange = ? AND market = ? AND symbol = ? AND timeframe = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    config.exchange.strip().upper(),
                    config.market.strip().upper(),
                    config.symbol,
                    config.timeframe,
                    config.signal_limit,
                ),
            ).fetchall()
    except sqlite3.Error as exc:
        return {
            "status": "error",
            "message": f"signal log unavailable: {exc}",
            "path": str(path),
            "entries": [],
        }
    entries = [_signal_row_dict(row) for row in rows]
    return {
        "status": "ok" if entries else "empty",
        "message": "ok" if entries else "no signal records",
        "path": str(path),
        "entries": entries,
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
        "signal_log_path": str(config.signal_log_path),
        "exchange": config.exchange,
        "market": config.market,
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "limit": config.limit,
        "signal_limit": config.signal_limit,
        "loaded_count": len(candles),
        "closed_count": len(closed),
        "latest_timestamp": candles[-1].timestamp if candles else None,
        "latest_closed_timestamp": closed[-1].timestamp if closed else None,
        "candles": [_candle_dict(candle) for candle in candles],
        "signal_text": None,
        "analysis": None,
        "signal_history": load_signal_history(config),
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
    signal_history = state.get("signal_history") or {"entries": [], "status": "missing", "message": "no signal history"}
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

    def fmt_optional_price(value: Any) -> str:
        return f"{float(value):.4f}" if isinstance(value, (int, float)) else "等待确认"

    def fmt_entry(entry: Any) -> str:
        if not isinstance(entry, dict) or not entry:
            return "等待确认"
        low = entry.get("low")
        high = entry.get("high")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            return f"{low:.4f} ~ {high:.4f}"
        if isinstance(low, (int, float)):
            return f"{low:.4f}"
        if isinstance(high, (int, float)):
            return f"{high:.4f}"
        return "等待确认"

    def fmt_take_profits(values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "等待确认"
        formatted = [f"{float(value):.4f}" for value in values[:5] if isinstance(value, (int, float))]
        return " / ".join(formatted) if formatted else "等待确认"

    history_entries = signal_history.get("entries") if isinstance(signal_history, dict) else []
    history_rows: list[str] = []
    if isinstance(history_entries, list):
        for entry in history_entries:
            if not isinstance(entry, dict):
                continue
            reasons = entry.get("reasons")
            reason_items = "；".join(str(item) for item in reasons[:3]) if isinstance(reasons, list) and reasons else ""
            reason_text = str(entry.get("reason") or "")
            if reason_items:
                reason_text = f"{reason_text}：{reason_items}" if reason_text else reason_items
            history_rows.append(
                "<tr>"
                f"<td>{html.escape(str(entry.get('time') or entry.get('created_at') or ''))}</td>"
                f"<td>{html.escape(str(entry.get('direction') or 'WAIT'))}</td>"
                f"<td>{html.escape(fmt_optional_price(entry.get('price')))}</td>"
                f"<td>{html.escape(fmt_entry(entry.get('entry')))}</td>"
                f"<td>{html.escape(fmt_take_profits(entry.get('take_profits')))}</td>"
                f"<td>{html.escape(fmt_optional_price(entry.get('stop_loss')))}</td>"
                f"<td>{html.escape(reason_text or '无额外原因')}</td>"
                "</tr>"
            )
    history_status = str(signal_history.get("status", "missing")) if isinstance(signal_history, dict) else "missing"
    history_message = str(signal_history.get("message", "no signal history")) if isinstance(signal_history, dict) else "no signal history"
    if not history_rows:
        history_rows.append(
            "<tr>"
            f"<td colspan=\"7\">暂无最近信号记录：{html.escape(history_message)}</td>"
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
    .history {{ margin-top: 14px; }}
    .history td:last-child, .history th:last-child {{ text-align: left; white-space: normal; min-width: 220px; }}
    .history-meta {{ color: var(--muted); font-size: 13px; }}
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
    <section class="panel history">
      <h2>最近信号记录</h2>
      <p class="history-meta">读取 {html.escape(str(state.get("signal_log_path")))}，状态：{html.escape(history_status)}</p>
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>方向</th>
            <th>价格</th>
            <th>Entry</th>
            <th>TP</th>
            <th>SL</th>
            <th>Reason / Reasons</th>
          </tr>
        </thead>
        <tbody>{''.join(history_rows)}</tbody>
      </table>
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
            signal_log_path=_first(params, "signal_log_path", base.signal_log_path),
            exchange=_first(params, "exchange", base.exchange),
            market=_first(params, "market", base.market),
            symbol=_first(params, "symbol", base.symbol),
            timeframe=_first(params, "timeframe", base.timeframe),
            limit=int(_first(params, "limit", str(base.limit))),
            signal_limit=int(_first(params, "signal_limit", str(base.signal_limit))),
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
    parser.add_argument("--signal-log-path", default="data/okx-signals.sqlite")
    parser.add_argument("--exchange", default="okx")
    parser.add_argument("--market", default="futures")
    parser.add_argument("--symbol", default="ORDI/USDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--limit", type=int, default=180)
    parser.add_argument("--signal-limit", type=int, default=20)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    Path(args.cache_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    config = DashboardConfig(
        cache_path=args.cache_path,
        signal_log_path=args.signal_log_path,
        exchange=args.exchange,
        market=args.market,
        symbol=args.symbol,
        timeframe=args.timeframe,
        limit=args.limit,
        signal_limit=args.signal_limit,
    )
    server = DashboardServer((args.host, args.port), config)
    print(f"Yongying dashboard listening on http://{args.host}:{args.port}")
    print(f"Reading cache: {args.cache_path}")
    print(f"Reading signal log: {args.signal_log_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
