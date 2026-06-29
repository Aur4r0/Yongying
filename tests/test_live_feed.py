import unittest

from yongying.live_feed import LiveFeedState, closed_candles, iter_closed_candle_polls, poll_closed_candles
from yongying.models import Candle


def candle(index: int) -> Candle:
    price = 3.0 + index * 0.01
    return Candle(index, price, price + 0.02, price - 0.02, price + 0.01, 1000)


def candles_with_last_closed(timestamp: int) -> list[Candle]:
    candles = [candle(index) for index in range(5)]
    candles[-2] = Candle(timestamp, 3.1, 3.2, 3.0, 3.15, 1200)
    candles[-1] = Candle(timestamp + 1, 3.15, 3.22, 3.12, 3.18, 1300)
    return candles


class LiveFeedTests(unittest.TestCase):
    def test_closed_candles_excludes_latest_forming_candle(self):
        candles = candles_with_last_closed(1000)
        closed = closed_candles(candles)
        self.assertEqual(len(closed), 4)
        self.assertEqual(closed[-1].timestamp, 1000)

    def test_poll_closed_candles_detects_only_new_closed_timestamp(self):
        state = LiveFeedState()

        def loader(**kwargs):
            return candles_with_last_closed(1000)

        first = poll_closed_candles(state, loader=loader)
        second = poll_closed_candles(state, loader=loader)
        self.assertTrue(first.is_new_closed_candle)
        self.assertEqual(first.reason, "new_closed_candle")
        self.assertFalse(second.is_new_closed_candle)
        self.assertEqual(second.reason, "no_new_closed_candle")

    def test_iter_closed_candle_polls_uses_mock_sleep(self):
        state = LiveFeedState()
        timestamps = [1000, 2000]
        sleeps = []

        def loader(**kwargs):
            return candles_with_last_closed(timestamps.pop(0))

        results = list(
            iter_closed_candle_polls(
                state,
                iterations=2,
                interval=15,
                loader=loader,
                sleep=sleeps.append,
            )
        )

        self.assertEqual([result.closed_timestamp for result in results], [1000, 2000])
        self.assertEqual(sleeps, [15])


if __name__ == "__main__":
    unittest.main()
