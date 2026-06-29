from __future__ import annotations

import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable


TELEGRAM_TOKEN_ENV = "YONGYING_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "YONGYING_TELEGRAM_CHAT_ID"

Transport = Callable[[str, bytes, dict[str, str], float], tuple[int, str]]


@dataclass(frozen=True)
class NotifyResult:
    provider: str
    enabled: bool
    sent: bool
    reason: str
    status_code: int | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "enabled": self.enabled,
            "sent": self.sent,
            "reason": self.reason,
            "status_code": self.status_code,
            "dry_run": self.dry_run,
        }


def _urllib_transport(url: str, data: bytes, headers: dict[str, str], timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.getcode(), body


def send_telegram_message(
    text: str,
    token: str | None = None,
    chat_id: str | None = None,
    dry_run: bool = False,
    timeout: float = 10.0,
    transport: Transport | None = None,
) -> NotifyResult:
    message = text.strip()
    if not message:
        return NotifyResult(provider="telegram", enabled=False, sent=False, reason="empty_text", dry_run=dry_run)

    bot_token = (token if token is not None else os.getenv(TELEGRAM_TOKEN_ENV, "")).strip()
    target_chat_id = (chat_id if chat_id is not None else os.getenv(TELEGRAM_CHAT_ID_ENV, "")).strip()
    if not bot_token or not target_chat_id:
        return NotifyResult(provider="telegram", enabled=False, sent=False, reason="missing_credentials", dry_run=dry_run)

    if dry_run:
        return NotifyResult(provider="telegram", enabled=True, sent=False, reason="dry_run", dry_run=True)

    payload = urllib.parse.urlencode(
        {
            "chat_id": target_chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    send = transport or _urllib_transport
    try:
        status_code, _body = send(url, payload, headers, timeout)
    except Exception as exc:  # pragma: no cover - exact urllib errors vary by platform
        return NotifyResult(
            provider="telegram",
            enabled=True,
            sent=False,
            reason=f"transport_error:{exc.__class__.__name__}",
            dry_run=dry_run,
        )

    if 200 <= status_code < 300:
        return NotifyResult(provider="telegram", enabled=True, sent=True, reason="sent", status_code=status_code, dry_run=dry_run)
    return NotifyResult(provider="telegram", enabled=True, sent=False, reason="http_error", status_code=status_code, dry_run=dry_run)


def send_notification(
    provider: str,
    text: str,
    dry_run: bool = False,
    transport: Transport | None = None,
) -> NotifyResult:
    if provider == "none":
        return NotifyResult(provider="none", enabled=False, sent=False, reason="disabled", dry_run=dry_run)
    if provider == "telegram":
        return send_telegram_message(text, dry_run=dry_run, transport=transport)
    return NotifyResult(provider=provider, enabled=False, sent=False, reason="unsupported_provider", dry_run=dry_run)
