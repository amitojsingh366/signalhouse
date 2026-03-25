"""Screenshot parsing via Claude API vision — extracts holdings from brokerage screenshots."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


def _detect_media_type(data: bytes) -> str:
    """Detect image media type from file magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:3] == b"GIF":
        return "image/gif"
    return "image/png"  # fallback


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


def _call_claude_vision(
    image_data: bytes, api_key: str, media_type: str
) -> str:
    """Synchronous Claude API call — run via asyncio.to_thread."""
    client = anthropic.Anthropic(api_key=api_key)
    b64_image = base64.b64encode(image_data).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": PARSE_PROMPT,
                    },
                ],
            }
        ],
    )
    return message.content[0].text.strip()


async def parse_holdings_screenshot(
    image_data: bytes, api_key: str, media_type: str = "image/png"
) -> list[dict[str, Any]]:
    """Parse a brokerage screenshot into structured holdings data using Claude vision.

    Args:
        image_data: Raw image bytes (PNG, JPG, etc.)
        api_key: Anthropic API key
        media_type: MIME type hint (overridden by magic byte detection)

    Returns:
        List of dicts with keys: symbol, quantity, market_value_cad
    """
    # Detect actual image type from bytes — Discord content_type can be wrong
    media_type = _detect_media_type(image_data)

    try:
        response_text = await asyncio.to_thread(
            _call_claude_vision, image_data, api_key, media_type
        )
    except anthropic.APIError:
        logger.exception("Claude API error during screenshot parsing")
        return []

    # Handle markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        holdings = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response as JSON: %s", response_text)
        return []

    if not isinstance(holdings, list):
        logger.error("Expected list from Claude, got: %s", type(holdings))
        return []

    # Validate each entry
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
