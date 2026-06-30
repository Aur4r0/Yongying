import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

from yongying.scanner import ScanResult


def load_script_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_okx_scanner.py"
    spec = importlib.util.spec_from_file_location("run_okx_scanner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OkxScannerScriptTests(unittest.TestCase):
    def test_parser_defaults_to_okx_live_scanner_settings(self):
        module = load_script_module()
        args = module.build_parser().parse_args([])

        self.assertEqual(args.symbol, "ORDI/USDT")
        self.assertEqual(args.timeframe, "15m")
        self.assertEqual(args.cache_path, "data/okx-klines.sqlite")
        self.assertEqual(args.signal_log_path, "data/okx-signals.sqlite")
        self.assertEqual(args.interval, 60.0)
        self.assertEqual(args.iterations, 0)
        self.assertTrue(args.emit_wait)

    def test_run_invokes_scanner_with_okx_live_cache_settings(self):
        module = load_script_module()
        calls = []

        def fake_scan_once(state, **kwargs):
            calls.append(kwargs)
            return ScanResult(
                symbol=kwargs["symbol"],
                timeframe=kwargs["timeframe"],
                analyzed=False,
                emitted=False,
                reason="no_new_closed_candle",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = str(Path(tmpdir) / "nested" / "okx.sqlite")
            signal_log_path = str(Path(tmpdir) / "signals" / "okx-signals.sqlite")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = module.run(
                    [
                        "--iterations",
                        "1",
                        "--cache-path",
                        cache_path,
                        "--signal-log-path",
                        signal_log_path,
                        "--symbol",
                        "ETH/USDT",
                    ],
                    scan_once_fn=fake_scan_once,
                    sleep=lambda seconds: None,
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(Path(cache_path).parent.exists())
            self.assertTrue(Path(signal_log_path).parent.exists())

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["symbol"], "ETH/USDT")
        self.assertEqual(calls[0]["source"], "live")
        self.assertEqual(calls[0]["exchange"], "okx")
        self.assertEqual(calls[0]["cache_path"], cache_path)
        self.assertEqual(calls[0]["signal_log_path"], signal_log_path)
        self.assertTrue(calls[0]["emit_wait"])
        self.assertIn("[ETH/USDT 15m] no_new_closed_candle", output.getvalue())


if __name__ == "__main__":
    unittest.main()
