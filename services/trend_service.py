import xml.etree.ElementTree as ET

import requests

from utils.logger import get_logger

logger = get_logger("trend_service")

TRENDS_URL = "https://trends.google.com/trending/rss?geo=US"
FALLBACK_TRENDS = "AI, Economic Shifts, Digital Detox, Sustainable Living, Wellness"


def get_live_trends() -> str:
    try:
        response = requests.get(
            TRENDS_URL,
            timeout=2,
            headers={"User-Agent": "Mozilla/5.0 StockAutomation/1.0"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        titles = []
        for item in root.findall(".//item/title"):
            text = (item.text or "").strip()
            if text:
                titles.append(text)
            if len(titles) == 5:
                break
        if titles:
            return ", ".join(titles)
    except Exception as e:
        logger.warning(f"Google Trends indisponibil, folosesc fallback: {e}")
    return FALLBACK_TRENDS
