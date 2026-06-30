# AGENTS.md

本文件约束本仓库内的后续开发行为。适用范围：仓库根目录及所有子目录。

## 项目结构

- `yongying/market_data.py`：行情来源统一入口。`demo` 必须保持离线、确定性；`live` 默认只接公开 K 线 adapter。
- `yongying/kline_cache.py`：SQLite K 线缓存与增量更新。只存公开 OHLCV，不存 API key、账户、订单或资金数据；测试必须使用临时数据库和 mock fetcher。
- `yongying/exchanges/binance.py`：Binance U 本位合约 K 线 REST adapter。只允许公开 `/fapi/v1/klines`，不得加入账户、下单、资金或私钥接口。
- `yongying/exchanges/okx.py`：OKX 公开 K 线 REST adapter。只允许公开 `/api/v5/market/candles`，默认 futures/swap 映射到 `*-USDT-SWAP`；不得加入账户、下单、资金或私钥接口。
- `yongying/indicators.py`：技术指标。核心实现不得依赖 pandas、TA-Lib 或网络。
- `yongying/patterns.py`：K 线形态识别。只返回结构化 pattern 结果，不做交易决策。
- `yongying/price_levels.py`：价格位生成。负责 entry、take profits、stop loss 和参考位，不判断是否交易。
- `yongying/strategy/`：策略规则模块。
  - `breakout_accumulation.py`：拉升/蓄势识别。
  - `wash_distribution.py`：洗盘 vs 出货识别。
  - `market_structure.py`：SMS/BMS 结构识别。
  - `left_side_short.py`：左侧摸顶试空识别。
  - `pullback_long.py`：回踩 MA25 后的稳健做多观察。
  - `breakdown_short.py`：跌破 MA7 后的右侧追空观察。
  - `followup_signals.py`：兼容导出层，不放新策略逻辑。
- `yongying/signal_engine.py`：组合指标、规则、分数和计划。新增策略必须从这里接入。
- `yongying/risk_policy.py`：把信号转为主计划、激进计划和稳健计划，包括入场区间、止盈、止损和失效条件。
- `yongying/ai_writer.py`：中文 memo 渲染。不得在这里发明价格或指标。
- `yongying/templates/signal_cn.py`：目标格式中文信号渲染。只能使用结构化计划字段。
- `yongying/cli.py`：命令行入口。
- `yongying/live_feed.py`：K 线轮询与新收盘 candle 判断。测试必须使用 demo/mock loader。
- `yongying/scanner.py`：常驻扫描器。只分析新收盘 candle，只输出/推送信号文本，不下单。
- `yongying/notifier.py`：可选推送 adapter。token 只能来自环境变量，测试必须使用 mock transport。
- `yongying/simple_server.py`：无外部依赖 HTTP API。
- `yongying/api.py`：可选 FastAPI API。
- `yongying/dashboard.py`：本地缓存 Dashboard。只能读取 SQLite K 线缓存并渲染页面/JSON，不得主动拉 live 数据、保存 API key、查询账户或下单。
- `scripts/run_okx_scanner.py`：OKX 实时监控启动脚本。默认只能调用公开 K 线、SQLite 缓存和 scanner，不得加入账户、下单、资金或 API key 逻辑。
- `tests/`：标准库 `unittest` 测试。
- `prompts/`：未来 LLM 写作提示词。
- `策略(1).docx`：本地原始策略资料，默认不得提交到 GitHub。

## 运行命令

```bash
python3 -m yongying.cli --symbol ORDI/USDT --timeframe 15m
python3 -m yongying.cli --symbol ORDI/USDT --timeframe 15m --json
python3 -m yongying.scanner --symbol ORDI/USDT --timeframe 15m --iterations 1
python3 -m yongying.simple_server --port 8765
```

可选依赖安装后才使用：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[api,live]"
uvicorn yongying.api:app --reload --port 8765
```

## 测试命令

每次改动后至少运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

修改包结构、导入路径或 API 文件时再运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall yongying tests
```

修改 HTTP 服务时，用本地接口验证：

```bash
curl -s http://127.0.0.1:8765/health
curl -s 'http://127.0.0.1:8765/analyze?symbol=ORDI/USDT&timeframe=15m&source=demo'
```

## 代码风格

- Python 版本保持 `>=3.10`。
- 核心模块优先使用标准库；新增运行时依赖必须放进 `pyproject.toml` 的 optional extras，并说明为什么核心不能用标准库完成。
- 使用类型标注和小函数；策略规则返回 `RuleResult`，最终输出走 `AnalysisResult.to_dict()`。
- 新增策略模块必须输出：`score`、`confidence`、`state`、`reasons`、`warnings`、`metrics`。
- 规则判断必须基于 candle、indicator 或明确输入字段；不能把自然语言判断硬编码成结论。
- `demo` 数据必须可重复，且 OHLC 合法：`low <= open/close <= high`。
- 中文 memo 和信号模板只渲染结构化结果，不在 `ai_writer.py` 或 `templates/` 中重新推理行情。
- `plan` 字段是兼容字段；新增计划结构必须优先通过 `aggressive_plan` / `conservative_plan` 扩展，不要删除旧字段。
- 面向交易的文本必须保留“研究输出/非投资建议”语义。

## 禁止事项

- 禁止实现真实下单、自动交易、交易所私钥管理或资金划转。
- 禁止把 `策略(1).docx`、`.env`、API key、交易所 token、账户信息提交到仓库。
- 禁止在代码、测试、README 示例中写入真实 Telegram token 或 chat id。
- 禁止让 `live` 数据成为测试或默认运行的必要条件。
- 禁止在核心分析链路里做网络请求；网络只能出现在 `market_data.fetch_live_candles` 或 `yongying/exchanges/` 的公开行情 adapter。
- 禁止为了让测试通过而降低测试断言、删除风险提示或跳过异常路径。
- 禁止在策略里使用未来数据；任何 rolling/window 计算只能看当前 candle 及之前数据。
- 禁止输出确定性收益承诺、胜率承诺或“必涨/必跌”措辞。
- 禁止把重构、格式化、依赖升级和策略行为变更混在一个提交里。

## 完成标准

- 相关代码已实现，且没有留下未接入的死代码入口。
- `unittest` 全部通过；涉及导入/API 时 `compileall` 通过。
- CLI demo 能输出中文 memo；如果改 API，`/health` 和 `/analyze` 能返回 JSON。
- 新增或修改策略时，同步补充测试，至少覆盖一个正向样例和一个不触发/风险样例。
- 输出 JSON 字段保持向后兼容；破坏兼容时必须更新 README 并说明迁移方式。
- `git status` 中不得出现误加入的本地资料、缓存、虚拟环境或密钥文件。

## Review 标准

- 先看行为风险：是否可能变成自动下单、泄露资料、隐藏实盘风险或给出投资承诺。
- 检查数据边界：空数据、少于 60 根 candle、异常 OHLC、零成交量、极端波动是否处理合理。
- 检查时序正确性：指标、区间高低点、SMS/BMS 不能使用未来 candle。
- 检查规则证据：每个方向性结论必须能从 `reasons`、`warnings`、`metrics` 追溯。
- 检查风险计划：有方向信号时必须包含确认条件、失效条件和止损参考；证据不足时必须 `WAIT`。
- 检查测试是否覆盖新增规则的触发和不触发路径。
- 检查 README/命令是否仍然能按当前代码运行。
