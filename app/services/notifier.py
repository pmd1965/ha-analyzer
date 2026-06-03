from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage

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
    if not cfg.get("MAIL_PASSWORD"):
        logger.warning("email_not_configured")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = cfg["MAIL_TO"]
    msg.set_content(body)
    with smtplib.SMTP(cfg["MAIL_SMTP_HOST"], cfg["MAIL_SMTP_PORT"]) as smtp:
        smtp.starttls()
        smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(msg)
    logger.info("email_sent", to=cfg["MAIL_TO"])
