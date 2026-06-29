import unittest

from yongying.models import AnalysisResult, Candle, IndicatorSnapshot, SignalPlan
from yongying.notifier import NotifyResult
from yongying.scanner import ScannerState, scan_once


def candle(index: int) -> Candle:
    price = 3.0 + index * 0.001
    return Candle(index, price, price + 0.02, price - 0.02, price + 0.01, 1000)


def candles_with_closed_timestamp(timestamp: int) -> list[Candle]:
    candles = [candle(index) for index in range(61)]
    candles[-2] = Candle(timestamp, 3.1, 3.2, 3.0, 3.15, 1200)
    candles[-1] = Candle(timestamp + 1, 3.15, 3.22, 3.12, 3.18, 1300)
    return candles


def active_analysis(candles: list[Candle], symbol: str, timeframe: str, source: str) -> AnalysisResult:
    plan = SignalPlan(
        direction="SHORT",
        risk_level="high",
        entry_range=(3.1, 3.2),
        take_profits=[3.0, 2.9, 2.8, 2.7, 2.6],
        stop_loss=3.3,
        confirmation=["test confirmation"],
        invalidation=["test invalidation"],
        position_note="test",
        leverage="Cross (3x)",
    )
    indicators = IndicatorSnapshot(
        close=3.15,
        ma7=3.1,
        ma25=3.0,
        boll_mid=3.05,
        boll_upper=3.3,
        boll_lower=2.8,
        rsi14=70,
        macd=0,
        macd_signal=0,
        macd_hist=0,
        atr14=0.1,
        volume=1000,
        volume_ma20=900,
    )
    return AnalysisResult(
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        last_price=3.15,
        aggregate_score=50,
        plan=plan,
        indicators=indicators,
        rules=[],
        memo_cn="memo",
        aggressive_plan=plan,
        conservative_plan=SignalPlan(
            direction="WAIT",
            risk_level="medium",
            entry_range=None,
            take_profits=[],
            stop_loss=None,
            confirmation=["wait"],
            invalidation=["invalid"],
            position_note="wait",
        ),
    )


class ScannerTests(unittest.TestCase):
    def test_scan_once_uses_closed_candle_and_emits_once(self):
        state = ScannerState()

        def loader(**kwargs):
            return candles_with_closed_timestamp(1000)

        observed_lengths = []

        def analyzer(candles, symbol, timeframe, source):
            observed_lengths.append(len(candles))
            self.assertEqual(candles[-1].timestamp, 1000)
            return active_analysis(candles, symbol, timeframe, source)

        first = scan_once(state, loader=loader, analyzer=analyzer, renderer=lambda result: "signal")
        second = scan_once(state, loader=loader, analyzer=analyzer, renderer=lambda result: "signal")
        self.assertTrue(first.emitted)
        self.assertEqual(first.reason, "emitted")
        self.assertFalse(second.emitted)
        self.assertEqual(second.reason, "no_new_closed_candle")
        self.assertEqual(observed_lengths, [60])

    def test_scan_once_skips_duplicate_signal_on_new_candle(self):
        state = ScannerState()
        timestamps = [1000, 2000]

        def loader(**kwargs):
            return candles_with_closed_timestamp(timestamps.pop(0))

        first = scan_once(state, loader=loader, analyzer=active_analysis, renderer=lambda result: "signal")
        second = scan_once(state, loader=loader, analyzer=active_analysis, renderer=lambda result: "signal")
        self.assertTrue(first.emitted)
        self.assertFalse(second.emitted)
        self.assertEqual(second.reason, "duplicate_signal")

    def test_scan_once_notifies_only_after_signal_emit(self):
        state = ScannerState()

        def loader(**kwargs):
            return candles_with_closed_timestamp(1000)

        messages = []

        def notifier(text):
            messages.append(text)
            return NotifyResult(provider="telegram", enabled=True, sent=True, reason="sent", status_code=200)

        result = scan_once(
            state,
            loader=loader,
            analyzer=active_analysis,
            renderer=lambda analysis: "signal text",
            notifier=notifier,
        )

        self.assertTrue(result.emitted)
        self.assertEqual(messages, ["signal text"])
        self.assertIsNotNone(result.notify_result)
        self.assertTrue(result.notify_result.sent)


if __name__ == "__main__":
    unittest.main()
