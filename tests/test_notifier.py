import os
import unittest
import urllib.parse
from unittest.mock import patch

from yongying.notifier import NotifyResult, send_notification, send_telegram_message


class NotifierTests(unittest.TestCase):
    def test_telegram_without_credentials_skips_safely(self):
        def raising_transport(url, data, headers, timeout):
            raise AssertionError("transport should not be called")

        with patch.dict(os.environ, {}, clear=True):
            result = send_telegram_message("signal", transport=raising_transport)

        self.assertEqual(result, NotifyResult(provider="telegram", enabled=False, sent=False, reason="missing_credentials"))

    def test_telegram_dry_run_does_not_call_transport(self):
        def raising_transport(url, data, headers, timeout):
            raise AssertionError("transport should not be called")

        result = send_telegram_message(
            "signal",
            token="mock-token",
            chat_id="mock-chat",
            dry_run=True,
            transport=raising_transport,
        )

        self.assertTrue(result.enabled)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "dry_run")
        self.assertTrue(result.dry_run)

    def test_telegram_with_mock_transport_sends_text_only(self):
        observed = {}

        def mock_transport(url, data, headers, timeout):
            observed["url"] = url
            observed["data"] = data
            observed["headers"] = headers
            observed["timeout"] = timeout
            return 200, '{"ok":true}'

        result = send_telegram_message(
            "PAIR $ORDI/USDT\nSHORT",
            token="mock-token",
            chat_id="mock-chat",
            transport=mock_transport,
        )

        payload = urllib.parse.parse_qs(observed["data"].decode("utf-8"))
        self.assertTrue(result.sent)
        self.assertEqual(result.reason, "sent")
        self.assertIn("/sendMessage", observed["url"])
        self.assertEqual(payload["chat_id"], ["mock-chat"])
        self.assertEqual(payload["text"], ["PAIR $ORDI/USDT\nSHORT"])

    def test_send_notification_rejects_unknown_provider(self):
        result = send_notification("exchange", "signal")

        self.assertFalse(result.enabled)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "unsupported_provider")


if __name__ == "__main__":
    unittest.main()
