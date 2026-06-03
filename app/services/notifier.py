from __future__ import annotations

import httpx
import structlog
from flask import current_app

logger = structlog.get_logger(__name__)

_SEVERITY_EMOJI = {
    "low": "⚠️",
    "medium": "🔶",
    "high": "🚨",
    "none": "✅",
}


def notify_anomaly(scenario_name: str, result_id: int, summary: str, severity: str) -> None:
    """Send Telegram + email notifications for a detected anomaly."""
    emoji = _SEVERITY_EMOJI.get(severity, "⚠️")
    telegram_text = (
        f"{emoji} *HA Anomaly Detected*\n"
        f"*Scenario:* {scenario_name}\n"
        f"*Severity:* {severity.upper()}\n"
        f"*Summary:* {summary}\n"
        f"View: http://192.168.0.107:8104/analysis/{result_id}"
    )
    email_subject = f"HA Anomaly [{severity.upper()}]: {scenario_name}"
    email_body = (
        f"Home Assistant Anomaly Detected\n"
        f"{'=' * 40}\n\n"
        f"Scenario: {scenario_name}\n"
        f"Severity: {severity.upper()}\n"
        f"Summary: {summary}\n\n"
        f"View full analysis:\n"
        f"http://192.168.0.107:8104/analysis/{result_id}\n"
    )

    _send_telegram(telegram_text)
    _send_email(email_subject, email_body)


def _send_telegram(text: str) -> None:
    token = current_app.config["TELEGRAM_BOT_TOKEN"]
    chat_id = current_app.config["TELEGRAM_CHAT_ID"]
    if not token or not chat_id:
        logger.warning("telegram_not_configured")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        resp.raise_for_status()
    logger.info("telegram_sent")


def _send_email(subject: str, body: str) -> None:
    cfg = current_app.config
    api_key = cfg.get("HOVER_MAIL_API_KEY", "")
    if not api_key:
        logger.warning("hover_mail_not_configured")
        return
    url = f"{cfg['HOVER_MAIL_URL']}/send-mail"
    payload = {"to": [cfg["MAIL_TO"]], "subject": subject, "body": body}
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload, headers={"X-Api-Key": api_key})
        resp.raise_for_status()
    logger.info("email_sent_via_hover_mail", to=cfg["MAIL_TO"])
