# Yongying MVP

Yongying is a first-version research MVP for turning the strategy notes in
`策略(1).docx` into a runnable signal-analysis service.

This version is intentionally conservative:

- It does not place orders.
- It can run entirely offline with deterministic demo candles.
- Live Binance U-margined futures and OKX swap klines are optional through
  public REST.
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
python3 -m yongying.scanner --source live --exchange binance --symbol ORDI/USDT --timeframe 15m --cache-path data/klines.sqlite --iterations 0 --interval 60
python3 -m yongying.scanner --source live --exchange okx --symbol ORDI/USDT --timeframe 15m --cache-path data/okx-klines.sqlite --iterations 0 --interval 60
```

`scanner.py` uses `live_feed.py` to poll candles and analyze only newly closed
candles. The default `demo` source stays deterministic for tests. When
`--cache-path` is provided with `--source live`, the scanner first updates the
SQLite kline cache incrementally, then reads the latest local candles for
closed-candle analysis.

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

For live Binance kline data, use:

```text
http://127.0.0.1:8765/analyze?symbol=ORDI/USDT&timeframe=15m&source=live&exchange=binance
```

For live OKX kline data, use:

```text
http://127.0.0.1:8765/analyze?symbol=ORDI/USDT&timeframe=15m&source=live&exchange=okx
```

## Market Data

The unified candle loader returns the existing `Candle` model:

```python
from yongying.market_data import load_candles

demo_candles = load_candles(
    symbol="ORDI/USDT",
    timeframe="15m",
    source="demo",
    limit=200,
)

binance_candles = load_candles(
    symbol="ORDI/USDT",
    timeframe="15m",
    source="live",
    exchange="binance",
    limit=200,
)

okx_candles = load_candles(
    symbol="ORDI/USDT",
    timeframe="15m",
    source="live",
    exchange="okx",
    limit=200,
)
```

`source="demo"` is deterministic and offline. `source="live"` with
`exchange="binance"` calls the public Binance U-margined futures endpoint:
`https://fapi.binance.com/fapi/v1/klines`. `exchange="okx"` calls the public
OKX candles endpoint: `https://www.okx.com/api/v5/market/candles`; the default
`market="futures"` maps `ORDI/USDT` to `ORDI-USDT-SWAP`. Live market data does
not use or store API keys, and it does not expose account, order, balance, or
funding endpoints.

### Market Data Cache

Use the SQLite cache when a scanner needs repeated kline reads without
refetching the same history every cycle:

```python
from yongying.kline_cache import KlineCache, update_cached_candles

result = update_cached_candles(
    cache_path="data/klines.sqlite",
    exchange="binance",
    market="futures",
    symbol="ORDI/USDT",
    timeframe="15m",
    limit=200,
)

cache = KlineCache("data/klines.sqlite")
cached_candles = cache.load_candles(
    exchange="binance",
    market="futures",
    symbol="ORDI/USDT",
    timeframe="15m",
    limit=200,
)
```

Rows are keyed by `exchange + market + symbol + timeframe + timestamp`, so
duplicate candles are replaced rather than appended. `update_cached_candles`
passes `start_time` after the latest cached timestamp to the fetcher when
possible and returns a continuity report for gaps. Scanner cache mode refreshes
the latest cached candle as a one-candle overlap, because public REST responses
can include the still-forming candle whose OHLCV may change before close.

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
  kline_cache.py         SQLite kline cache and incremental update helpers
  exchanges/
    binance.py           Binance U-margined futures kline REST adapter
    okx.py               OKX public swap/spot kline REST adapter
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
- Binance live data uses public kline REST only; no account or order APIs.
- Telegram integration only pushes signal text from environment-provided
  credentials.
- No guaranteed live-data availability when the exchange endpoint is unreachable,
  rate-limited, or rejects the symbol/timeframe.
- Signals are research outputs; they need backtesting before production use.

## Next Step Ideas

- Store signal history in SQLite.
- Add vectorbt/backtesting validation.
- Add OpenAI or local LLM as an optional writer after the rule engine has
  produced structured evidence.
- Build a small web dashboard.
