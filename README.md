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

The MVP converts three parts of the strategy document into code:

1. Breakout accumulation: range compression, volume expansion, consecutive green
   candles, and upward FVG/imbalance.
2. Wash vs distribution: volume, support break, candle shadows, and high/low
   position.
3. SMS/BMS market structure: lower-high/lower-low and higher-low/higher-high
   structure checks.

The output includes:

- Structured JSON signal data.
- Rule scores and evidence.
- A Chinese strategy memo similar to a trading-desk note.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[api,live]"
```

Run the offline demo:

```bash
python -m yongying.cli --symbol ORDI/USDT --timeframe 15m
```

Run the dependency-free API:

```bash
python -m yongying.simple_server --port 8765
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
python -m unittest discover -s tests
```

## Project Layout

```text
yongying/
  simple_server.py       Dependency-free HTTP API
  api.py                 Optional FastAPI app
  cli.py                 Local command-line runner
  market_data.py         Demo/live candle loading
  indicators.py          MA, BOLL, RSI, MACD, ATR
  signal_engine.py       Orchestrates all rules
  risk_policy.py         Converts evidence into a research plan
  ai_writer.py           Chinese memo renderer
  strategy/
    breakout_accumulation.py
    wash_distribution.py
    market_structure.py
```

## Next Step Ideas

- Add real exchange adapters and candle caching.
- Store signal history in SQLite.
- Add vectorbt/backtesting validation.
- Add OpenAI or local LLM as an optional writer after the rule engine has
  produced structured evidence.
- Build a small web dashboard.
