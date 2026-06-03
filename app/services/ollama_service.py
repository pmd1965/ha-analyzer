from __future__ import annotations

import json

import httpx
import structlog
from flask import current_app

logger = structlog.get_logger(__name__)

# Fixed system prompt — provides physical grounding for anomaly detection in a UK home.
_SYSTEM_PROMPT_TEMPLATE = """\
You are a home environment monitoring AI for a residential property in the UK.
You receive time-series sensor data and must determine whether any anomalies are present.

An anomaly is something that is unusual, unexpected, or potentially problematic given:
- The current date and time (it is currently {current_datetime} UTC)
- Physical expectations (e.g. a room should warm up when heating is on; indoor temperature
  should not fall sharply below the outdoor temperature unless windows are open; an HVAC
  unit running continuously for more than 4 hours during mild weather (>10°C) is unusual)
- Normal daily patterns (early-morning temperature drops are expected; heating typically runs
  morning and evening in a UK home)

You must respond ONLY with a valid JSON object in exactly this schema — no preamble, no markdown:
{{
  "anomaly": <true|false>,
  "severity": "<none|low|medium|high>",
  "summary": "<one sentence — what you found>",
  "details": "<2-4 sentences — what is normal or abnormal and why>",
  "recommended_action": "<one sentence — what to check, or 'No action needed'>",
  "confidence": <0.0 to 1.0>
}}

Rules:
- anomaly=true only if something genuinely warrants attention
- Do not flag normal nightly temperature drops or standard HVAC cycling as anomalies
- If data is sparse (fewer than 3 readings per entity), note this and set confidence low
- severity="none" must always accompany anomaly=false
"""


def run_analysis_prompt(
    user_prompt: str,
    current_datetime: str,
) -> tuple[str, bool, str]:
    """
    Send the analysis prompt to Ollama.
    Returns (raw_response, anomaly_detected, severity).
    """
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(current_datetime=current_datetime)
    payload = {
        "model": current_app.config["OLLAMA_MODEL"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
    }

    url = f"{current_app.config['OLLAMA_URL']}/v1/chat/completions"
    timeout = current_app.config["OLLAMA_TIMEOUT"]

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info("ollama_response_received", length=len(content))
            return _parse_response(content)
    except httpx.HTTPError as exc:
        logger.error("ollama_http_error", error=str(exc))
        raise
    except Exception as exc:
        logger.error("ollama_call_failed", error=str(exc))
        raise


def _parse_response(content: str) -> tuple[str, bool, str]:
    """Parse JSON response. Returns (raw_content, anomaly_bool, severity_str)."""
    try:
        data = json.loads(content)
        anomaly = bool(data.get("anomaly", False))
        severity = str(data.get("severity", "none"))
        return content, anomaly, severity
    except json.JSONDecodeError:
        # Fallback: keyword scan
        lower = content.lower()
        anomaly = any(
            w in lower for w in ["anomaly", "unusual", "abnormal", "concern", "unexpected", "problem"]
        )
        severity = "low" if anomaly else "none"
        logger.warning("ollama_json_parse_failed", fallback_anomaly=anomaly)
        return content, anomaly, severity
