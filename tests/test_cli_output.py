import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from yongying.cli import main


class CliOutputTests(unittest.TestCase):
    def test_cli_default_uses_signal_template(self):
        buffer = io.StringIO()
        with patch("sys.argv", ["yongying", "--symbol", "ORDI/USDT", "--timeframe", "15m"]):
            with redirect_stdout(buffer):
                main()
        text = buffer.getvalue()
        self.assertIn("PAIR $ORDI/USDT", text)
        self.assertIn("Entry Target", text)
        self.assertIn("Take Profits", text)
        self.assertIn("STOP LOSS", text)

    def test_cli_json_keeps_structured_output(self):
        buffer = io.StringIO()
        with patch("sys.argv", ["yongying", "--symbol", "ORDI/USDT", "--timeframe", "15m", "--json"]):
            with redirect_stdout(buffer):
                main()
        text = buffer.getvalue()
        self.assertIn('"symbol": "ORDI/USDT"', text)
        self.assertIn('"aggressive_plan"', text)
        self.assertIn('"conservative_plan"', text)


if __name__ == "__main__":
    unittest.main()
