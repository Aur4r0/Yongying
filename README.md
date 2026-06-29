# Yongying MVP

Yongying is a first-version research MVP for turning the strategy notes in
`策略(1).docx` into a runnable signal-analysis service.

This version is intentionally conservative:

- It does not place orders.
- It can run entirely offline with deterministic demo candles.
- Live market data is optional through `ccxt`.
- The core strategy engine uses plain Python so it can be tested without heavy
  dependencies.

## What It Does

The MVP converts the strategy document into deterministic rule modules:

1. Breakout accumulation: range compression, volume expansion, consecutive green
   candles, and upward FVG/imbalance.
2. Wash vs distribution: volume, support break, candle shadows, and high/low
   position.
3. SMS/BMS market structure: lower-high/lower-low and higher-low/higher-high
   structure checks.
4. Left-side short: BOLL upper-band tests, overheated RSI, long upper shadow,
   bearish engulfing, stalling, and distance from MA25.
5. Follow-up entries: pullback-long near MA25 and breakdown-short below MA7.

The output includes:

- Structured JSON signal data.
- Rule scores and evidence.
- A primary plan plus aggressive/conservative plans.
- A Chinese signal template similar to the target trading-desk note.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[api,live]"
```

Run the offline demo:

```bash
python3 -m yongying.cli --symbol ORDI/USDT --timeframe 15m
python3 -m yongying.cli --symbol ORDI/USDT --timeframe 15m --json
```

Run the scanner once, or leave `--iterations 0` running:

```bash
python3 -m yongying.scanner --symbol ORDI/USDT --timeframe 15m --iterations 1
python3 -m yongying.scanner --symbol ORDI/USDT --timeframe 15m --iterations 0 --interval 900
```

`scanner.py` uses `live_feed.py` to poll candles and analyze only newly closed
candles. The default `demo` source stays deterministic for tests.

Telegram push is optional and sends signal text only. Credentials must come from
environment variables:

```bash
export YONGYING_TELEGRAM_BOT_TOKEN="mock-token"
export YONGYING_TELEGRAM_CHAT_ID="mock-chat"
python3 -m yongying.scanner --iterations 1 --notify telegram --notify-dry-run
```

Run the dependency-free API:

```bash
python3 -m yongying.simple_server --port 8765
```

Then open:

```text
http://127.0.0.1:8765/analyze?symbol=ORDI/USDT&timeframe=15m&source=demo
```

Run the FastAPI version after installing the `api` extra:

```bash
uvicorn yongying.api:app --reload --port 8765
```

Then open:

```text
http://127.0.0.1:8765/analyze?symbol=ORDI/USDT&timeframe=15m&source=demo
```

For live data, install the `live` extra and use:

```text
http://127.0.0.1:8765/analyze?symbol=ORDI/USDT&timeframe=15m&source=live&exchange=binance
```

## Run Tests

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall yongying tests
```

## Project Layout

```text
yongying/
  simple_server.py       Dependency-free HTTP API
  api.py                 Optional FastAPI app
  cli.py                 Local command-line runner
  live_feed.py           Polling and new closed-candle detection
  scanner.py             Closed-candle signal scanner
  notifier.py            Optional Telegram text push
  market_data.py         Demo/live candle loading
  indicators.py          MA, BOLL, RSI, MACD, ATR
  patterns.py            Candle pattern detection
  price_levels.py        Entry, take-profit, and stop-loss levels
  signal_engine.py       Orchestrates all rules
  risk_policy.py         Converts evidence into primary/aggressive/conservative plans
  ai_writer.py           Chinese memo renderer
  templates/
    signal_cn.py         Target-format Chinese signal renderer
  strategy/
    breakout_accumulation.py
    wash_distribution.py
    market_structure.py
    left_side_short.py
    pullback_long.py
    breakdown_short.py
    followup_signals.py  Compatibility exports for older imports
```

## Current Signal Format

The default CLI output uses the target-format Chinese signal template:

```text
⚠️ 激进者：左侧轻仓试空（极轻仓）

PAIR $ORDI/USDT
💎 SHORT（左侧摸顶，极轻仓）
Cross (3x)

✔️ Entry Target（开仓范围）：
...

☑️ Take Profits：
...

❌ STOP LOSS：...

✅ 稳健者：观望，等待确认
...
```

`--json` returns the full structured payload, including:

- `plan`: backward-compatible primary plan.
- `aggressive_plan`: aggressive research plan.
- `conservative_plan`: conservative watch plan.
- `rules`: all rule evidence and metrics.

## Current Limits

- No order execution.
- No key management.
- Telegram integration only pushes signal text from environment-provided
  credentials.
- No guaranteed live-data availability unless `ccxt` is installed and the
  exchange endpoint is reachable.
- Signals are research outputs; they need backtesting before production use.

## Next Step Ideas

- Store signal history in SQLite.
- Add vectorbt/backtesting validation.
- Add OpenAI or local LLM as an optional writer after the rule engine has
  produced structured evidence.
- Build a small web dashboard.
