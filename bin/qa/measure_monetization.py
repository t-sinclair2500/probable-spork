import json
import re
from urllib.parse import parse_qs, urlparse

from pathlib import Path


def _urls(text: str) -> list[str]:
    """Extract URLs from text."""
    return re.findall(r"https?://\S+", text or "")


def evaluate(slug: str, thresholds: dict) -> dict:
    """Evaluate monetization compliance and disclosure requirements."""
    meta_p = Path("videos") / f"{slug}.metadata.json"
    if not meta_p.exists():
        return {"error": "metadata_missing"}

    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        desc = meta.get("description", "")

        # Disclosure check
        disclosure_ok = True
        if thresholds.get("require_disclosure", True):
            disclosure_terms = ["#ad", "affiliate", "sponsored", "promotion", "partner"]
            disclosure_ok = any(term in desc.lower() for term in disclosure_terms)

        # Link analysis
        links = _urls(desc)
        max_links = int(thresholds.get("max_links", 20))
        link_count_ok = len(links) <= max_links

        # UTM tracking check
        utm_ok = True
        if thresholds.get("require_utm", True) and links:
            for u in links:
                try:
                    q = parse_qs(urlparse(u).query)
                    if "utm_source" not in q or "utm_medium" not in q:
                        utm_ok = False
                        break
                except Exception:
                    utm_ok = False
                    break

        return {
            "disclosure_ok": disclosure_ok,
            "utm_ok": utm_ok,
            "link_count": len(links),
            "link_count_ok": link_count_ok,
            "links": links[:5],  # Include first 5 links for debugging
        }
    except Exception as e:
        return {"error": f"Failed to parse metadata: {str(e)}"}
