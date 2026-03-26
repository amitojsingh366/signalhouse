"""Screenshot parsing via Ollama vision (qwen2.5vl:3b) — extracts holdings from brokerage screenshots."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PARSE_PROMPT = """Extract all stock/ETF holdings from this brokerage screenshot.

Return ONLY a JSON array with this exact format, no other text:
[
  {"symbol": "AMD", "quantity": 0.9008, "market_value_cad": 33.80},
  {"symbol": "IBIT", "quantity": 34.7669, "market_value_cad": 979.04}
]

Rules:
- Use the stock ticker symbol (e.g. "AMD" not "Advanced Micro Devices")
- quantity should be the number of shares (can be fractional)
- market_value_cad should be the total market value in CAD for that position
- If you see a currency other than CAD, still extract the values as shown
- Include ALL holdings visible in the screenshot
- If you cannot identify the holdings, return an empty array: []"""


async def parse_holdings_screenshot(
    image_data: bytes, ollama_url: str, media_type: str = "image/png"
) -> list[dict[str, Any]]:
    b64_image = base64.b64encode(image_data).decode("utf-8")

    payload = {
        "model": "qwen2.5vl:3b",
        "prompt": PARSE_PROMPT,
        "images": [b64_image],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{ollama_url}/api/generate", json=payload)
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPError:
        logger.exception("Ollama API error during screenshot parsing")
        return []

    response_text = result.get("response", "").strip()

    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        holdings = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse Ollama response as JSON: %s", response_text)
        return []

    if not isinstance(holdings, list):
        logger.error("Expected list from Ollama, got: %s", type(holdings))
        return []

    valid = []
    for h in holdings:
        if (
            isinstance(h, dict)
            and "symbol" in h
            and "quantity" in h
            and "market_value_cad" in h
        ):
            valid.append({
                "symbol": str(h["symbol"]).upper(),
                "quantity": float(h["quantity"]),
                "market_value_cad": float(h["market_value_cad"]),
            })
        else:
            logger.warning("Skipping invalid holding entry: %s", h)

    logger.info("Parsed %d holdings from screenshot", len(valid))
    return valid
